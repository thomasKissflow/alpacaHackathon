"""
LEARNING SCRIPT 2: How does the "risk gate" decide what's safe to trade?

This script doesn't touch Alpaca or the internet -- it uses a temporary,
throwaway database so you can run it as many times as you like without
affecting anything real. Run it with:

    source .venv/bin/activate
    python examples/02_risk_gate_demo.py

--------------------------------------------------------------------------
Background, in plain language:

The whole point of agent/risk_gate.py is this rule: the AI (the LLM) is
allowed to SUGGEST things, but a separate piece of plain, deterministic
Python code (no AI involved) has the final say on whether a trade actually
happens. This is a common and important pattern in AI trading systems --
you don't want a language model's occasional bad guess to blow up a real
account.

The risk gate checks things like:
  - Is this ONE trade too big relative to the whole account? (per-trade cap)
  - Are we already too exposed to this one stock? (concentration cap)
  - Has the account lost too much money today? (circuit breaker)
  - Is someone's emergency "kill switch" flipped on? (kill switch)

This script shows the SAME functions the real agent calls, with small,
easy-to-follow examples.
--------------------------------------------------------------------------
"""
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent import ledger  # noqa: E402

# Use a throwaway database just for this demo, so we never touch your real
# data/ledger.db. This is the same trick tests/conftest.py uses.
ledger.DB_PATH = Path(tempfile.mkdtemp()) / "demo_ledger.db"
ledger.init_db()

from agent import risk_gate  # noqa: E402
from agent.config import RISK  # noqa: E402
from agent.strategy import Leg, StrategyPlan  # noqa: E402


def section(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


section("Example 1: a trade that's small enough gets APPROVED")

# A pretend $100,000 account. RISK.max_risk_per_trade_pct (see
# agent/config.py) says any single Convexity Mode trade can risk at most
# 2% of the account -- that's $2,000 here.
account = {"equity": "100000", "buying_power": "50000"}
small_trade = StrategyPlan(
    strategy_type="iron_condor", underlying="SPY", expiration=date(2026, 10, 16),
    legs=[Leg("SPY261016P00440000", "sell"), Leg("SPY261016P00435000", "buy")],
    net_credit_estimate=1.50, max_loss_estimate=300.0,  # well under the $2,000 cap
    rationale="demo: small, safe trade",
)
decision = risk_gate.evaluate_convexity_plan(small_trade, account, open_strategies=[])
print(f"Max loss on this trade: ${small_trade.max_loss_estimate:.2f}")
print(f"Per-trade cap ({RISK.max_risk_per_trade_pct:.0%} of $100,000): ${100_000 * RISK.max_risk_per_trade_pct:.2f}")
print(f"--> Approved? {decision.approved}")


section("Example 2: a trade that's TOO BIG gets REJECTED")

big_trade = StrategyPlan(
    strategy_type="iron_condor", underlying="SPY", expiration=date(2026, 10, 16),
    legs=[Leg("SPY261016P00440000", "sell"), Leg("SPY261016P00435000", "buy")],
    net_credit_estimate=1.50, max_loss_estimate=5_000.0,  # way over the $2,000 cap
    rationale="demo: dangerously large trade",
)
decision = risk_gate.evaluate_convexity_plan(big_trade, account, open_strategies=[])
print(f"Max loss on this trade: ${big_trade.max_loss_estimate:.2f}")
print(f"Per-trade cap: ${100_000 * RISK.max_risk_per_trade_pct:.2f}")
print(f"--> Approved? {decision.approved}")
print(f"--> Reason(s): {decision.reasons}")


section("Example 3: the daily circuit breaker")

# Imagine the account started today at $100,000 and has now dropped to
# $97,000 -- a 3% loss. RISK.daily_loss_circuit_breaker_pct (see
# agent/config.py) sets the threshold for halting NEW trades for the rest
# of the day (existing positions can still be closed/hedged -- just no new
# risk gets added).
risk_gate.get_or_init_day_start_equity(100_000)
tripped, drawdown_pct = risk_gate.circuit_breaker_tripped(current_equity=97_000)
print(f"Circuit breaker threshold: {RISK.daily_loss_circuit_breaker_pct:.0%} daily drawdown")
print(f"Today's drawdown so far:   {drawdown_pct:.1%}")
print(f"--> Circuit breaker tripped? {tripped}")
if tripped:
    print("    (new trades are now blocked for the rest of the session; existing")
    print("     positions are still monitored/hedged/closed as needed)")


section("Example 4: the kill switch")

print(f"Kill switch engaged right now? {risk_gate.kill_switch_engaged()}")
print("\nIn real use you'd run:  python -m agent.kill_switch execute")
print("...which cancels every resting order and closes every position immediately.")
print("(We're NOT running that here -- this is just checking the current status.)")


section("Example 5: an LLM's suggestion getting clamped back to something safe")

# Pretend an LLM suggested something a little unreasonable: an absurdly wide
# quoting spread (9000 basis points = 90%!) and a symbol we've never
# approved trading. validate_market_plan() fixes both, rather than
# rejecting the whole plan outright.
llm_suggestion = {
    "symbols": ["SPY", "GME"],  # GME isn't in our approved basket
    "target_spread_bps": {"SPY": 9000},  # 90% spread width -- way too wide
    "mode_weights": {"specialist": 0.5, "convexity": 0.5},
    "rationale": "demo: an LLM being a bit too creative",
}
approved_plan = risk_gate.validate_market_plan(llm_suggestion, source="llm")
print("What the LLM suggested:", llm_suggestion)
print()
print("What actually gets used after the risk gate fixes it:", approved_plan)

print("\nDone! Open agent/risk_gate.py and agent/config.py to see the actual numbers")
print("and logic behind every check above.")
