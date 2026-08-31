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
from agent.config import (
    ANTHROPIC_API_KEY, ANTHROPIC_MODEL, FEATHERLESS_API_KEY, FEATHERLESS_BASE_URL,
    FEATHERLESS_MODEL, IV_HISTORY, LLM_PROVIDER, RISK,
)

_MARKET_PLAN_SYSTEM = """You are the market-planning layer for an autonomous options trading system \
called "The Specialist". You NEVER place orders yourself -- a separate deterministic risk gate \
validates and clamps everything you propose before it reaches the market, so it is safe for you to \
be opinionated. Respond with ONLY a single JSON object, no prose, no markdown fences, matching \
exactly this schema:
{"symbols": ["SYM", ...], "target_spread_bps": {"SYM": number, ...}, \
"mode_weights": {"specialist": number, "convexity": number}, "rationale": "1-2 sentences"}
Guidance: choose a subset of the allowed basket to actively quote this cycle; widen target_spread_bps \
for a symbol when its IV rank is elevated or uncertain, tighten it when conditions are calm and liquid; \
mode_weights should shift toward convexity when specialist quotes aren't getting filled or portfolio \
Greeks are near their caps, and toward specialist otherwise. mode_weights must sum to 1."""

_POSTMORTEM_SYSTEM = """You are the daily post-mortem layer for an autonomous options trading system \
called "The Specialist". You write a short, honest natural-language debrief of the day's closed \
trades and hedges, then propose a MarketPlan adjustment for tomorrow. You never place orders. \
Respond with ONLY a single JSON object, no prose outside it, matching exactly this schema:
{"debrief": "3-6 sentences: what worked, what didn't, realized vs implied vol if relevant, hedge \
slippage if notable", "proposed_adjustments": {"target_spread_bps": {"SYM": number, ...}, \
"mode_weights": {"specialist": number, "convexity": number}, "rationale": "1-2 sentences"}}"""


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


def _call_featherless(system_prompt: str, user_prompt: str, max_tokens: int) -> str | None:
    try:
        from openai import OpenAI
    except ImportError:
        print("[llm_agent] openai package not installed; run `pip install openai`")
        return None
    try:
        client = OpenAI(api_key=FEATHERLESS_API_KEY, base_url=FEATHERLESS_BASE_URL)
        resp = client.chat.completions.create(
            model=FEATHERLESS_MODEL, max_tokens=max_tokens,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        )
        return resp.choices[0].message.content
    except Exception as exc:  # noqa: BLE001
        print(f"[llm_agent] Featherless call failed: {exc}")
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


def _build_market_plan_context(equity: float) -> str:
    greeks = ledger.portfolio_greeks_now()
    inventory = ledger.all_specialist_inventory()
    iv_hist = _read_iv_history()
    iv_summary = {}
    for sym, series in iv_hist.items():
        if series:
            iv_summary[sym] = round(series[-1]["iv"], 4)

    lines = [
        f"Timestamp: {datetime.now(timezone.utc).isoformat()}",
        f"Account equity: ${equity:,.2f}",
        f"Allowed specialist basket: {list(RISK.specialist_symbols)}",
        f"Allowed convexity basket: {list(RISK.candidate_underlyings)}",
        f"Current portfolio delta-dollars: ${greeks['delta_dollars']:,.0f} (cap +/-${RISK.max_net_delta_dollars:,.0f})",
        f"Current portfolio vega-dollars: ${greeks['vega_dollars']:,.0f} (cap +/-${RISK.max_net_vega_dollars:,.0f})",
        f"Current portfolio gamma exposure: {greeks['gamma']:,.1f} (cap +/-{RISK.max_net_gamma_shares_per_dollar:,.0f})",
        f"Most recent ATM IV per symbol: {iv_summary or 'no history yet'}",
        f"Current specialist inventory (nonzero only): {[(i['symbol'], i['qty']) for i in inventory] or 'flat'}",
    ]
    latest_postmortem = ledger.recent("postmortems", limit=1)
    if latest_postmortem:
        pm = latest_postmortem[0]
        lines.append(f"Yesterday's postmortem proposed adjustment: {pm['proposed_adjustments_json']}")
    return "\n".join(lines)


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
