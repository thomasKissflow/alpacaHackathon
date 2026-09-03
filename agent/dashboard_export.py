"""
Exports the ledger into a single JSON snapshot that the static dashboard
fetches -- zero backend needed at demo time. GitHub Pages (or
`python -m http.server`) just serves data/dashboard.json straight out of the
repo, and dashboard/app.js re-fetches it on an interval.
"""
import json
from collections import OrderedDict
from datetime import datetime, timezone

from agent import ledger, risk_gate
from agent.config import DATA_DIR, RISK

OUT_PATH = DATA_DIR / "dashboard.json"
CANDLE_BUCKET_MINUTES = 3


def _bucket_key(ts_iso: str, bucket_minutes: int) -> str:
    ts = datetime.fromisoformat(ts_iso)
    floored_minute = (ts.minute // bucket_minutes) * bucket_minutes
    return ts.replace(minute=floored_minute, second=0, microsecond=0).isoformat()


def _build_equity_candles(account_history: list[dict], bucket_minutes: int = CANDLE_BUCKET_MINUTES) -> list[dict]:
    """Real OHLC candles built from real equity snapshots bucketed by time --
    not fabricated data, just a richer view of the same account_history the
    line chart used. A bucket's open/close are literally the first/last
    equity reading Alpaca gave us in that window; high/low are the actual
    min/max readings. Sparse history just means fewer, wider candles."""
    buckets: OrderedDict[str, dict] = OrderedDict()
    for snap in account_history:
        key = _bucket_key(snap["ts"], bucket_minutes)
        eq = snap["equity"]
        b = buckets.get(key)
        if b is None:
            buckets[key] = {"t": key, "o": eq, "h": eq, "l": eq, "c": eq}
        else:
            b["h"] = max(b["h"], eq)
            b["l"] = min(b["l"], eq)
            b["c"] = eq
    return list(buckets.values())


def _build_activity_volume(fills: list[dict], hedges: list[dict], orders: list[dict],
                            bucket_minutes: int = CANDLE_BUCKET_MINUTES) -> list[dict]:
    """Real trade-activity count per time bucket (fills + hedges + new resting
    orders placed) -- an honest stand-in for share "volume" on an account
    that doesn't trade a single instrument, used to fill the volume-bars
    slot in the chart the same way a price chart would."""
    counts: dict[str, int] = {}
    for row in fills:
        counts[_bucket_key(row["ts"], bucket_minutes)] = counts.get(_bucket_key(row["ts"], bucket_minutes), 0) + 1
    for row in hedges:
        k = _bucket_key(row["ts"], bucket_minutes)
        counts[k] = counts.get(k, 0) + 1
    for row in orders:
        if row["status"] != "new":
            continue
        k = _bucket_key(row["ts"], bucket_minutes)
        counts[k] = counts.get(k, 0) + 1
    return [{"t": k, "v": v} for k, v in sorted(counts.items())]


def export() -> None:
    account_history = ledger.recent("account_snapshots", limit=500)
    account_history.reverse()

    latest_positions = {}
    for row in ledger.recent("position_snapshots", limit=2000):
        latest_positions.setdefault(row["symbol"], row)  # rows are DESC by id, so first hit = most recent
    inventory = [row for row in latest_positions.values() if row["qty"]]

    with ledger.get_conn() as conn:
        convexity_closed = [dict(r) for r in conn.execute(
            "SELECT * FROM convexity_positions WHERE status='closed' ORDER BY id DESC LIMIT 50"
        ).fetchall()]
    for c in convexity_closed:
        c["legs"] = json.loads(c.pop("legs_json"))

    all_orders = ledger.recent("orders", limit=150)
    working_orders = [o for o in all_orders if o["status"] in ("new", "partially_filled")]
    fills_for_volume = ledger.recent("fills", limit=300)
    hedges_for_volume = ledger.recent("hedges", limit=300)
    equity_candles = _build_equity_candles(account_history)
    activity_volume = _build_activity_volume(fills_for_volume, hedges_for_volume, all_orders)

    latest_plan = ledger.latest_market_plan()
    latest_plan_parsed = None
    if latest_plan:
        latest_plan_parsed = {
            **latest_plan,
            "approved": json.loads(latest_plan["approved_json"]),
            "proposed": json.loads(latest_plan["proposed_json"]),
        }

    snapshot = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "risk_config": {
            "max_net_delta_dollars": RISK.max_net_delta_dollars,
            "max_net_vega_dollars": RISK.max_net_vega_dollars,
            "max_net_gamma_shares_per_dollar": RISK.max_net_gamma_shares_per_dollar,
            "max_notional_pct_per_underlying": RISK.max_notional_pct_per_underlying,
            "daily_loss_circuit_breaker_pct": RISK.daily_loss_circuit_breaker_pct,
            "max_risk_per_trade_pct": RISK.max_risk_per_trade_pct,
        },
        "tickers": ledger.all_underlying_marks(),
        "account_history": account_history,
        "equity_candles": equity_candles,
        "activity_volume": activity_volume,
        "candle_bucket_minutes": CANDLE_BUCKET_MINUTES,
        "inventory": inventory,
        "working_orders": working_orders,
        "quote_feed": all_orders,
        "fills": ledger.recent("fills", limit=100),
        "hedges": ledger.recent("hedges", limit=100),
        "risk_events": ledger.recent("risk_events", limit=100),
        "postmortems": ledger.recent("postmortems", limit=30),
        "market_plans": ledger.recent("market_plans", limit=30),
        "latest_plan": latest_plan_parsed,
        "convexity_open": ledger.open_convexity_positions(),
        "convexity_closed": convexity_closed,
        "kill_switch_engaged": risk_gate.kill_switch_engaged(),
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(snapshot, indent=2, default=str))


if __name__ == "__main__":
    export()
