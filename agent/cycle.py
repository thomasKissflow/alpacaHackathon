"""
The one shared run_cycle() that both entry points call:

  agent/run.py     -- single cycle, for GitHub Actions cron (uses the Alpaca
                       CLI for account telemetry -- the hackathon's
                       CLI-or-MCP requirement)
  agent/daemon.py   -- run_cycle() in a tight loop, for local/VM long-running
                       operation, which is what Specialist Mode actually
                       needs (quote maintenance far more often than every
                       few hours)

Order each cycle: kill switch check -> account telemetry -> MarketPlan
(refresh via LLM on a slower cadence, else reuse the last approved one) ->
Specialist Mode (quote maintenance + hedging, gated by the circuit breaker) ->
Convexity Mode (scan/monitor/enter, same gating) -> daily postmortem (once
per day, near the close) -> dashboard export.
"""
import json
from datetime import datetime, timedelta, timezone

from agent import convexity_mode, dashboard_export, ledger, llm_agent, risk_gate, specialist_mode
from agent.clients import cli_get, trading_client
from agent.config import RISK

_POSTMORTEM_HOUR_UTC = 19  # ~15:00 ET -- after the last scheduled cron slot, before close


def _get_account() -> dict:
    try:
        return cli_get("account", "get")
    except Exception as exc:  # noqa: BLE001 - CLI unavailable locally is fine, fall back to the SDK
        print(f"[cycle] Alpaca CLI unavailable ({exc}), falling back to SDK for account telemetry")
        acct = trading_client.get_account()
        return {"equity": str(acct.equity), "cash": str(acct.cash), "buying_power": str(acct.buying_power)}


def _get_or_refresh_market_plan(equity: float) -> dict:
    latest = ledger.latest_market_plan()
    if latest:
        age = datetime.now(timezone.utc) - datetime.fromisoformat(latest["ts"])
        if age < timedelta(minutes=RISK.market_plan_refresh_minutes):
            return json.loads(latest["approved_json"])

    proposed, source = llm_agent.generate_market_plan(equity)
    return risk_gate.validate_market_plan(proposed, source)


def _maybe_run_postmortem() -> None:
    today = datetime.now(timezone.utc).date().isoformat()
    if ledger.postmortem_exists_for(today):
        return
    if datetime.now(timezone.utc).hour < _POSTMORTEM_HOUR_UTC:
        return
    text, adjustments = llm_agent.generate_postmortem(today)
    ledger.log_postmortem(today, text, adjustments)
    print(f"[cycle] postmortem written for {today}")


def run_cycle() -> None:
    if risk_gate.kill_switch_engaged():
        print("[cycle] kill switch engaged -- skipping cycle entirely (no new orders, no hedging)")
        return

    account = _get_account()
    equity = float(account.get("equity", 0))

    approved_plan = _get_or_refresh_market_plan(equity)

    tripped, drawdown_pct = risk_gate.circuit_breaker_tripped(equity)
    if tripped:
        print(f"[cycle] circuit breaker tripped ({drawdown_pct:.2%} drawdown) -- halting NEW entries this cycle")

    try:
        specialist_mode.run_specialist_cycle(approved_plan, halt_new_entries=tripped)
    except Exception as exc:  # noqa: BLE001 - one mode failing shouldn't kill the other
        print(f"[cycle] specialist mode cycle failed: {exc}")
        ledger.log_risk_event("reject", f"specialist cycle raised: {exc}", mode="specialist")

    try:
        convexity_mode.run_convexity_cycle(account)
    except Exception as exc:  # noqa: BLE001
        print(f"[cycle] convexity mode cycle failed: {exc}")
        ledger.log_risk_event("reject", f"convexity cycle raised: {exc}", mode="convexity")

    convexity_pnl_today = ledger.convexity_pnl_realized_today()
    day_start_equity = risk_gate.get_or_init_day_start_equity(equity)
    day_pnl = equity - day_start_equity
    # approximation: attribute whatever of today's equity change convexity's
    # realized P&L doesn't explain to Specialist Mode (fills + hedges +
    # unrealized marks). A fully accurate per-mode subledger would need
    # separate mark-to-market accounting; called out as a known simplification.
    specialist_pnl_today = day_pnl - convexity_pnl_today
    ledger.log_account_snapshot(
        equity=equity, cash=float(account.get("cash", 0)), buying_power=float(account.get("buying_power", 0)),
        specialist_pnl=specialist_pnl_today, convexity_pnl=convexity_pnl_today, day_pnl=day_pnl,
    )

    _maybe_run_postmortem()
    dashboard_export.export()
