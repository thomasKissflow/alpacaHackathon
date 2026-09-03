"""
Populates a SEPARATE, throwaway ledger (data/demo_ledger.db -- never
data/ledger.db, the real one the live agent reads and writes) with clearly
fake, illustrative data, and exports it to data/demo_dashboard.json, so you
can look at a fully-populated dashboard without needing live Alpaca keys or
waiting for the agent to actually trade.

Run it from the project root:

    source .venv/bin/activate
    python examples/seed_demo_dashboard.py

Then point the dashboard at the demo export to look at it:

    cp data/demo_dashboard.json data/dashboard.json   # ONLY if you want to view demo data
    python3 -m http.server 8934
    # open http://localhost:8934/dashboard/index.html

IMPORTANT: never copy demo_dashboard.json over dashboard.json while the real
agent is running or has real trades in data/ledger.db -- that would only
overwrite the dashboard's JSON export, not the ledger itself, but the next
real cycle will regenerate dashboard.json from the real ledger anyway and
overwrite your copy. This script used to write directly into data/ledger.db
and it silently corrupted real risk-gate calculations once real trading
started (fake positions counted toward real Greeks caps) -- that's exactly
why it's isolated to its own file now.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent import dashboard_export, ledger  # noqa: E402

ledger.DB_PATH = Path(__file__).resolve().parent.parent / "data" / "demo_ledger.db"
dashboard_export.OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "demo_dashboard.json"
ledger.init_db()

now = datetime.now(timezone.utc)

# --- a fake equity curve, gently trending up with noise ---------------------
equity = 100_000.0
for i in range(30):
    equity += (i % 5 - 2) * 45 + 10
    ledger.log_account_snapshot(
        equity, equity * 0.4, equity * 0.6,
        specialist_pnl=(equity - 100_000) * 0.7,
        convexity_pnl=(equity - 100_000) * 0.3,
        day_pnl=equity - 100_000,
    )

# --- a fake Specialist Mode inventory (options + the hedge shares) ---------
for sym, underlying, qty, delta_dollars, gamma, vega_dollars, theta_dollars in [
    ("SPY261016P00450000", "SPY", -2, -10800, -3.7, -85.9, 46.5),
    ("QQQ261016P00380000", "QQQ", 1, -1900, 4.1, 22.3, -12.1),
]:
    ledger.log_position_snapshot("specialist", sym, underlying, qty,
                                  delta_dollars, gamma, vega_dollars, theta_dollars,
                                  notional=abs(qty) * 900)
ledger.log_position_snapshot("specialist", "SPY", "SPY", 24,
                              delta_dollars=24 * 450, gamma=0, vega_dollars=0, theta_dollars=0,
                              notional=24 * 450)

# --- a fake order -> fill -> hedge sequence (what "one quote getting hit" looks like)
order_id = ledger.log_order("specialist", "SPY261016P00450000", "sell", 1, "limit", 9.15, "filled",
                             alpaca_order_id="demo-order-1")
fill_id = ledger.log_fill(order_id, "specialist", "SPY261016P00450000", "sell", 1, 9.10)
ledger.log_hedge(fill_id, "SPY", "buy", 53, 450.20, delta_before=0, delta_after=53)
ledger.log_order("specialist", "QQQ261016P00380000", "buy", 1, "limit", 6.40, "new", alpaca_order_id="demo-order-2")

# --- a fake risk-gate rejection and clamp, so that panel isn't empty --------
ledger.log_risk_event("clamp", "NVDA: clamped qty 3->1 by Greeks caps (delta room=1, vega room=6, gamma room=9)",
                       mode="specialist")
ledger.log_risk_event("reject", "TSLA: SPY notional cap reached ($5,200 >= $5,000 = 5% of equity)",
                       mode="specialist")

# --- a fake Convexity Mode position, one closed at a profit, one still open
ledger.open_convexity_position("demo-mleg-1", "iron_condor", "IWM", "2026-10-16",
                                [{"symbol": "IWM261016P00210000", "side": "sell", "ratio_qty": 1}],
                                entry_credit=1.85, max_loss_estimate=315.0)
ledger.close_convexity_position("demo-mleg-1", exit_pnl=92.5, close_reason="profit target hit ($92.50 >= $92.50)")
ledger.open_convexity_position("demo-mleg-2", "bull_put_spread", "QQQ", "2026-10-23",
                                [{"symbol": "QQQ261023P00370000", "side": "sell", "ratio_qty": 1}],
                                entry_credit=1.20, max_loss_estimate=380.0)

# --- a fake MarketPlan + postmortem (what the LLM layer produces) ----------
ledger.log_market_plan(
    {"symbols": ["SPY", "QQQ", "AAPL"], "target_spread_bps": {"SPY": 40}},
    {"symbols": ["SPY", "QQQ"], "target_spread_bps": {"SPY": 40, "QQQ": 35},
     "mode_weights": {"specialist": 0.65, "convexity": 0.35}, "rationale": "demo rationale text"},
    source="llm", was_clamped=False,
)
ledger.log_postmortem(
    now.date().isoformat(),
    "[DEMO DATA] Specialist Mode captured spread on a couple of fills today. Convexity Mode's IWM iron "
    "condor hit its profit target early. This is illustrative post-mortem text, not a real trading day.",
    {"target_spread_bps": {"AAPL": 55}, "mode_weights": {"specialist": 0.55, "convexity": 0.45},
     "rationale": "demo adjustment"},
)

dashboard_export.export()
print(f"Wrote demo data to {ledger.DB_PATH} and {dashboard_export.OUT_PATH}")
print("Now start the dashboard (see README) and open it in a browser.")
