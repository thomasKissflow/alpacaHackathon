"""
Position reconciliation: never assume the last run's order submission did
what it intended. Every Convexity Mode cycle, before anything else, this
compares actual broker-held positions against what the ledger believes is
open. This directly answers a documented Alpaca paper-trading behavior
(confirmed against docs.alpaca.markets/us/docs/paper-trading): multi-leg
orders experience a **random ~10% partial-fill rate**, which can leave a
defined-risk spread as a NAKED short option with unbounded loss -- on an
account traded unattended, overnight. Reconciliation is not defensive
polish here; it is what keeps the book safe while nobody is watching it.

Two failure modes handled:
  1. Naked leg: some legs of an "open" spread are actually held, others
     aren't. Flatten whatever IS held rather than trying to blind-complete
     the missing leg -- the safer default for an unattended account.
  2. Stale unfilled entry: NONE of the legs ever filled (the resting limit
     was never marketable). Cancel it and stop counting it as an open
     position, rather than let it linger against max_concurrent_positions
     forever (see docs/research.md §1.6 / T-048: paper orders only fill
     when marketable).
"""
from datetime import datetime, timezone

from agent import ledger
from agent.clients import trading_client

STALE_UNFILLED_MINUTES = 30


def _actual_qty(symbol: str) -> int:
    try:
        pos = trading_client.get_open_position(symbol)
        return int(float(pos.qty)) * (1 if pos.side == "long" else -1)
    except Exception:  # noqa: BLE001 - no position for this symbol is the expected case, not an error
        return 0


def _flatten_naked_legs(record: dict, present: list[str], actual: dict[str, int]) -> None:
    details = {"strategy_id": record["strategy_id"], "present": present, "actual": actual}
    ledger.log_risk_event(
        "reject",
        f"NAKED LEG on {record['underlying']} {record['strategy_type']} (strategy "
        f"{record['strategy_id']}): only {present} of the spread is held. Flattening now.",
        mode="convexity", details=details,
    )
    for sym in present:
        qty = actual[sym]
        try:
            order = trading_client.close_position(sym)
            ledger.log_order("convexity", sym, "sell" if qty > 0 else "buy", abs(qty), "market", None, "filled",
                              alpaca_order_id=str(getattr(order, "id", "")),
                              note=f"naked-leg flatten for strategy {record['strategy_id']}")
        except Exception as exc:  # noqa: BLE001 - keep trying the other leg even if one flatten fails
            ledger.log_risk_event("reject", f"naked-leg flatten failed for {sym}: {exc}", mode="convexity")
    ledger.close_convexity_position(record["strategy_id"], exit_pnl=None, close_reason="naked_leg_flattened")


def _handle_unfilled_entry(record: dict) -> None:
    try:
        live = trading_client.get_order_by_id(record["strategy_id"])
    except Exception:  # noqa: BLE001 - transient API hiccup, try again next cycle
        return
    if str(live.status) == "filled":
        return  # fully filled but the fill hasn't propagated to positions yet -- next cycle will see it

    submitted_at = getattr(live, "submitted_at", None) or getattr(live, "created_at", None)
    if submitted_at is None:
        return
    age_minutes = (datetime.now(timezone.utc) - submitted_at).total_seconds() / 60.0
    if age_minutes < STALE_UNFILLED_MINUTES:
        return

    try:
        trading_client.cancel_order_by_id(record["strategy_id"])
    except Exception as exc:  # noqa: BLE001 - may already be terminal; still record the finding below
        print(f"[reconcile] cancel_order_by_id({record['strategy_id']}) failed: {exc}")

    ledger.log_risk_event(
        "reject",
        f"{record['underlying']} {record['strategy_type']} entry never filled after "
        f"{age_minutes:.0f}min (non-marketable limit); cancelled.",
        mode="convexity", details={"strategy_id": record["strategy_id"]},
    )
    ledger.close_convexity_position(record["strategy_id"], exit_pnl=0.0, close_reason="entry_never_filled_cancelled")


def reconcile_convexity_positions() -> None:
    for record in ledger.open_convexity_positions():
        expected: dict[str, int] = {}
        for leg in record["legs"]:
            sign = -1 if leg["side"] == "sell" else 1
            expected[leg["symbol"]] = expected.get(leg["symbol"], 0) + sign * leg["ratio_qty"]

        actual = {sym: _actual_qty(sym) for sym in expected}
        present = [sym for sym, qty in actual.items() if qty != 0]
        missing = [sym for sym, exp in expected.items() if actual.get(sym, 0) == 0 and exp != 0]

        if present and missing:
            _flatten_naked_legs(record, present, actual)
        elif missing and not present:
            _handle_unfilled_entry(record)
