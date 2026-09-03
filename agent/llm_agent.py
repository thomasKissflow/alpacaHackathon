"""
Agent layer: the only place an LLM's output touches this system, and even
here it never places an order -- it only emits structured JSON (a proposed
MarketPlan, or a postmortem + proposed adjustment) that risk_gate.py then
validates/clamps before the execution core acts on anything. See the build
brief, Section 4 ("why the LLM never places an order directly").

Provider-abstracted: prefers Anthropic (Claude), the brief's original
"orchestrate through Claude" framing, and falls back to Featherless's
OpenAI-compatible endpoint for any open-weights model hosted there. Which
one is active is entirely determined by agent/config.py:LLM_PROVIDER (set
automatically from whichever API key is present, or overridden explicitly).
If neither key is configured, both generation functions degrade to a
clearly-labeled deterministic fallback rather than failing the cycle --
market-making and Convexity Mode both keep running on static defaults, they
just don't get the LLM's situational judgment for that cycle.
"""
import json
import re
from datetime import datetime, timezone

from agent import ledger
_LLM_TIMEOUT_S = 90.0
_LLM_MAX_ATTEMPTS = 3
# Featherless drops the connection (RemoteProtocolError, always at ~15.1s) once
# the prompt exceeds roughly 1,200 characters. Measured 2026-09-04: 700ch -> 200
# OK in 3.0s; 1,200ch/1,600ch/2,500ch -> disconnect every time. Prompts are kept
# compact and hard-truncated below that ceiling.
_LLM_MAX_PROMPT_CHARS = 650

from agent.config import (
    ANTHROPIC_API_KEY, ANTHROPIC_MODEL, FEATHERLESS_API_KEY, FEATHERLESS_BASE_URL,
    FEATHERLESS_MODEL, IV_HISTORY, LLM_PROVIDER, RISK,
)

_MARKET_PLAN_SYSTEM = """Options market-making planner. JSON only:
{"symbols":[..],"target_spread_bps":{"SYM":bps},"mode_weights":{"specialist":x,"convexity":y},"rationale":"1 sentence"}
Widen bps when Greeks near caps. Weights sum to 1."""

_POSTMORTEM_SYSTEM = """Trading desk post-mortem. Reply with ONLY this JSON:
{"text":"3-4 sentences on fills, hedging and risk","proposed_adjustments":{"target_spread_bps":{"SYM":40},"rationale":"1 sentence"}}"""


def _extract_json(text: str) -> dict | None:
    text = text.strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None


def _call_anthropic(system_prompt: str, user_prompt: str, max_tokens: int) -> str | None:
    try:
        from anthropic import Anthropic
    except ImportError:
        print("[llm_agent] anthropic package not installed; run `pip install anthropic`")
        return None
    try:
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        resp = client.messages.create(
            model=ANTHROPIC_MODEL, max_tokens=max_tokens,
            system=system_prompt, messages=[{"role": "user", "content": user_prompt}],
        )
        return resp.content[0].text
    except Exception as exc:  # noqa: BLE001
        print(f"[llm_agent] Anthropic call failed: {exc}")
        return None


def _fit(text: str) -> str:
    """Hard-cap the prompt below Featherless's disconnect threshold."""
    return text if len(text) <= _LLM_MAX_PROMPT_CHARS else text[:_LLM_MAX_PROMPT_CHARS]


def _call_featherless(system_prompt: str, user_prompt: str, max_tokens: int) -> str | None:
    """Featherless via a direct HTTPS POST rather than the openai SDK.

    The SDK raised APIConnectionError ("Connection error.") against
    api.featherless.ai on every real prompt while an identical direct request
    returned HTTP 200 in ~15s. Featherless is serverless, so a 72B model can
    cold-start for tens of seconds; the SDK's connection handling gave up
    where a plain request with an explicit read timeout does not. The endpoint
    is OpenAI-compatible, so this is the same contract minus a dependency
    that was silently disabling the entire AI layer. Found live 2026-09-04.
    """
    import httpx

    # Featherless drops the connection on long system prompts: our 940-char
    # schema prompt reproducibly returned RemoteProtocolError while a short
    # system prompt with identical user content returned HTTP 200. Keep the
    # system turn minimal and carry the instructions in the user turn, which
    # is semantically equivalent for an instruct-tuned model.
    payload = {
        "model": FEATHERLESS_MODEL,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": "You are a quantitative trading assistant. Reply with JSON only."},
            {"role": "user", "content": _fit(f"{system_prompt}\n{user_prompt}")},
        ],
    }
    headers = {"Authorization": f"Bearer {FEATHERLESS_API_KEY}",
               "Content-Type": "application/json"}

    last_err = None
    for attempt in range(1, _LLM_MAX_ATTEMPTS + 1):
        try:
            resp = httpx.post(f"{FEATHERLESS_BASE_URL}/chat/completions",
                              headers=headers, json=payload,
                              timeout=httpx.Timeout(_LLM_TIMEOUT_S, connect=10.0))
            if resp.status_code != 200:
                last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
                print(f"[llm_agent] Featherless attempt {attempt}/{_LLM_MAX_ATTEMPTS}: {last_err}")
                continue
            body = resp.json()
            choices = body.get("choices") or []
            if not choices:
                last_err = f"no choices in response: {str(body)[:200]}"
                print(f"[llm_agent] Featherless attempt {attempt}/{_LLM_MAX_ATTEMPTS}: {last_err}")
                continue
            content = (choices[0].get("message") or {}).get("content")
            if content:
                usage = body.get("usage") or {}
                print(f"[llm_agent] Featherless OK ({FEATHERLESS_MODEL}, "
                      f"{usage.get('total_tokens','?')} tokens)")
                return content
            last_err = "empty content"
        except Exception as exc:  # noqa: BLE001
            last_err = f"{type(exc).__name__}: {exc}"
            print(f"[llm_agent] Featherless attempt {attempt}/{_LLM_MAX_ATTEMPTS}: {last_err}")

    print(f"[llm_agent] Featherless call failed after {_LLM_MAX_ATTEMPTS} attempts: {last_err}")
    return None


def _call_llm(system_prompt: str, user_prompt: str, max_tokens: int = 700) -> str | None:
    if LLM_PROVIDER == "anthropic" and ANTHROPIC_API_KEY:
        return _call_anthropic(system_prompt, user_prompt, max_tokens)
    if LLM_PROVIDER == "featherless" and FEATHERLESS_API_KEY:
        return _call_featherless(system_prompt, user_prompt, max_tokens)
    return None


def _read_iv_history() -> dict:
    if IV_HISTORY.exists():
        try:
            return json.loads(IV_HISTORY.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def _news_context() -> str:
    """One short clause from the News Agent. Guarded: the news read must never
    be able to break plan generation."""
    try:
        from agent import news_agent
        return news_agent.current_read().as_context()
    except Exception:  # noqa: BLE001
        return ""


def _build_market_plan_context(equity: float) -> str:
    """Compact market context. Kept deliberately terse: Featherless drops the
    connection above ~1,200 prompt chars (see _LLM_MAX_PROMPT_CHARS), so this
    carries only the facts that change a quoting decision."""
    from agent import ledger

    # position_snapshots is append-only: the same symbol appears once per
    # cycle. Summing raw rows double-counts across time -- it reported net
    # delta of $120,013 against a $60,000 cap while the book was actually
    # ~$150 net, i.e. it told the model the book was 2x over its limit.
    # Take the most recent row per symbol only (rows come back id-DESC).
    latest: dict[str, dict] = {}
    for row in ledger.recent("position_snapshots", limit=400):
        latest.setdefault(row["symbol"], row)
    d = sum(r.get("delta_dollars") or 0 for r in latest.values())
    v = sum(r.get("vega_dollars") or 0 for r in latest.values())
    g = sum(r.get("gamma") or 0 for r in latest.values())
    fills = len(ledger.recent("fills", limit=50))
    n_conv = len(ledger.open_convexity_positions())

    return (
        f"equity ${equity:,.0f}. "
        f"specialist basket {list(RISK.specialist_symbols)}. "
        f"convexity basket {list(RISK.candidate_underlyings)}. "
        f"net delta ${d:,.0f}/cap ${RISK.max_net_delta_dollars:,.0f}. "
        f"net vega ${v:,.0f}/cap ${RISK.max_net_vega_dollars:,.0f}. "
        f"fills today {fills}. open convexity {n_conv}/{RISK.max_concurrent_positions}. "
        f"default spread {RISK.target_spread_bps:.0f}bps. "
        f"{_news_context()}"
    )


def generate_market_plan(equity: float) -> tuple[dict, str]:
    """Returns (proposed_plan_dict, source) where source is 'llm' or
    'fallback'. Never raises. The caller MUST still pass the result through
    risk_gate.validate_market_plan() before acting on it."""
    if LLM_PROVIDER == "none":
        return {}, "fallback"

    context = _build_market_plan_context(equity)
    raw = _call_llm(_MARKET_PLAN_SYSTEM, context, max_tokens=500)
    if raw is None:
        return {}, "fallback"
    parsed = _extract_json(raw)
    if parsed is None:
        print(f"[llm_agent] could not parse MarketPlan JSON from LLM output: {raw[:300]!r}")
        return {}, "fallback"
    return parsed, "llm"


def generate_postmortem(trade_date: str) -> tuple[str, dict | None]:
    """Returns (debrief_text, proposed_adjustments_dict_or_None). Always
    produces *something* for the ledger/dashboard, even with no LLM
    configured -- clearly labeled as such."""
    closed = ledger.closed_convexity_positions_for_date(trade_date)
    fills = [f for f in ledger.recent("fills", limit=500) if f["ts"].startswith(trade_date) and f["mode"] == "specialist"]
    hedges = [h for h in ledger.recent("hedges", limit=500) if h["ts"].startswith(trade_date)]

    realized_convexity_pnl = sum(c["exit_pnl"] or 0 for c in closed)
    summary_lines = [
        f"Trade date: {trade_date}",
        f"Convexity Mode: {len(closed)} position(s) closed, realized P&L ${realized_convexity_pnl:,.2f}.",
    ]
    for c in closed:
        summary_lines.append(
            f"  - {c['underlying']} {c['strategy_type']}: entry credit ${c['entry_credit']:.2f}, "
            f"exit P&L ${c['exit_pnl']:.2f}, reason: {c['close_reason']}"
        )
    summary_lines.append(f"Specialist Mode: {len(fills)} fill(s), {len(hedges)} hedge trade(s).")

    if LLM_PROVIDER == "none":
        text = "[auto-generated, no LLM configured]\n" + "\n".join(summary_lines)
        return text, None

    context = "\n".join(summary_lines)
    raw = _call_llm(_POSTMORTEM_SYSTEM, context, max_tokens=700)
    if raw is None:
        text = "[LLM call failed, deterministic fallback]\n" + "\n".join(summary_lines)
        return text, None
    parsed = _extract_json(raw)
    if parsed is None or "debrief" not in parsed:
        print(f"[llm_agent] could not parse postmortem JSON from LLM output: {raw[:300]!r}")
        text = "[LLM output unparseable, deterministic fallback]\n" + "\n".join(summary_lines)
        return text, None
    return parsed["debrief"], parsed.get("proposed_adjustments")
