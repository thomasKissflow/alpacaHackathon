"""
Convexity Mode: the fallback strategy that keeps the account active even in
a quiet week for Specialist Mode fills (build brief, Section 1). Screens the
candidate basket for IV-rank + trend, opens a defined-risk vertical/iron
condor when a signal fires, and manages exits via profit target / stop loss
/ expiry roll. Shares the same ledger and risk gate as Specialist Mode.
"""
from agent import ledger, risk_gate
from agent.config import RISK
from agent.execution import execute
from agent.logger import log_decision
from agent.monitor import run_monitor
from agent.reconcile import reconcile_convexity_positions
from agent.scanner import scan
from agent.strategy import build_plan


def run_convexity_cycle(account: dict, block_new_entries: bool = False,
                        block_reason: str = "") -> None:
    # 0. reconcile actual broker state against what the ledger believes is
    #    open -- BEFORE anything else, even before deciding whether the
    #    circuit breaker allows new entries. Paper multi-leg orders have a
    #    documented ~10% random partial-fill rate; a spread with a naked
    #    leg is unbounded risk and must be found and flattened first.
    reconcile_convexity_positions()

    # 1. manage existing positions next, always -- even if the circuit
    #    breaker or kill switch is engaged, closing/hedging is still allowed.
    for entry in run_monitor():
        log_decision({"stage": "monitor", "mode": "convexity", **entry})

    equity = float(account.get("equity", 0))
    tripped, drawdown_pct = risk_gate.circuit_breaker_tripped(equity)
    if tripped:
        log_decision({"stage": "circuit_breaker", "mode": "convexity", "action": "halt_new_entries",
                       "drawdown_pct": drawdown_pct})
        return
    if risk_gate.kill_switch_engaged():
        log_decision({"stage": "kill_switch", "mode": "convexity", "action": "halt_new_entries"})
        return

    # Scheduled-event rule. Existing positions are still monitored and closed
    # above; this only stops OPENING new short premium that would be held
    # across a known macro release. See agent/event_calendar.py.
    if block_new_entries:
        log_decision({"stage": "event_calendar", "mode": "convexity",
                      "action": "halt_new_entries", "reason": block_reason})
        ledger.log_risk_event("clamp", block_reason, mode="convexity",
                              details={"gate": "event_calendar"})
        return

    candidates = scan()
    log_decision({
        "stage": "scan", "mode": "convexity",
        "candidates": [
            {"symbol": c.symbol, "iv_rank": round(c.iv_rank, 1), "trend": c.trend} for c in candidates
        ],
    })

    open_positions = ledger.open_convexity_positions()
    if len(open_positions) >= RISK.max_concurrent_positions:
        log_decision({"stage": "entry", "mode": "convexity", "action": "skip",
                       "reason": "max concurrent positions reached"})
        return

    for candidate in candidates:
        plan = build_plan(candidate)
        if plan is None:
            log_decision({"stage": "entry", "mode": "convexity", "symbol": candidate.symbol, "action": "no_plan"})
            continue

        decision = risk_gate.evaluate_convexity_plan(plan, account, open_positions)
        if not decision.approved:
            log_decision({
                "stage": "entry", "mode": "convexity", "symbol": candidate.symbol, "action": "rejected",
                "reasons": decision.reasons, "rationale": plan.rationale,
            })
            continue

        record = execute(plan)
        log_decision({
            "stage": "entry", "mode": "convexity", "symbol": candidate.symbol, "action": "entered",
            "rationale": plan.rationale, "strategy_id": record["strategy_id"],
        })
        break  # one new entry per cycle keeps risk easy to reason about
