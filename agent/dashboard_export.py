"""
Exports the ledger into a single JSON snapshot that the static dashboard
fetches -- zero backend needed at demo time. GitHub Pages (or
`python -m http.server`) just serves data/dashboard.json straight out of the
repo, and dashboard/app.js re-fetches it on an interval.
"""
import json
from datetime import datetime, timezone

from agent import ledger, risk_gate
from agent.config import DATA_DIR, RISK

OUT_PATH = DATA_DIR / "dashboard.json"


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
