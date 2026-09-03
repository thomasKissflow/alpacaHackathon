"""
Read-only preflight. Proves the agent can see the account and the options
market before anything places an order. Submits NOTHING.

    python3 preflight.py
"""
import sys
from datetime import datetime, timezone

from agent import clients
from alpaca.data.requests import OptionChainRequest
from agent.config import RISK, ALPACA_API_KEY, PAPER

FAIL = []

def check(label, fn):
    try:
        val = fn()
        print(f"  ✅ {label}: {val}")
        return val
    except Exception as e:
        print(f"  ❌ {label}: {type(e).__name__}: {e}")
        FAIL.append(label)
        return None

print("\n=== 1. Credentials ===")
print(f"  key prefix   : {ALPACA_API_KEY[:2]}… ({len(ALPACA_API_KEY)} chars)")
print(f"  paper mode   : {PAPER}")
if not PAPER:
    print("  🛑 ALPACA_PAPER_TRADE is not true. STOP.")
    sys.exit(1)

print("\n=== 2. Account ===")
acct = check("account reachable", lambda: clients.trading_client.get_account())
if acct:
    eq = float(acct.equity)
    print(f"     account id : {acct.id}")
    print(f"     equity     : ${eq:,.2f}")
    print(f"     buying pwr : ${float(acct.buying_power):,.2f}")
    print(f"     status     : {acct.status}")
    if abs(eq - 100_000) > 1:
        print(f"     ⚠️  equity is not $100,000 — hackathon requires exactly $100k start")

print("\n=== 3. Is this account CLEAN? (R4 eligibility) ===")
try:
    from alpaca.trading.requests import GetOrdersRequest
    from alpaca.trading.enums import QueryOrderStatus
    orders = clients.trading_client.get_orders(GetOrdersRequest(status=QueryOrderStatus.ALL, limit=500))
    n = len(orders)
    if n == 0:
        print("  ✅ 0 orders ever placed — CLEAN, safe to submit this account ID")
    else:
        print(f"  ⚠️  {n} historical order(s) found — this account is NOT fresh.")
        print("     Judges evaluate the whole history. A new account is needed before submitting.")
        for o in orders[:5]:
            print(f"       · {o.submitted_at}  {o.side} {o.qty} {o.symbol}  [{o.status}]")
except Exception as e:
    print(f"  ❌ could not list orders: {e}"); FAIL.append("order history")

print("\n=== 4. Market clock ===")
check("clock", lambda: (lambda c: f"open={c.is_open}  next_close={c.next_close}")(clients.trading_client.get_clock()))

print("\n=== 5. Options data on the free indicative feed ===")
print("    (this is the one that has never been proven for Convexity Mode)")
for sym in RISK.candidate_underlyings:
    try:
        chain = clients.option_data_client.get_option_chain(OptionChainRequest(underlying_symbol=sym))
        n = len(chain)
        with_greeks = sum(1 for c in chain.values()
                          if getattr(c, "greeks", None) and getattr(c.greeks, "delta", None) is not None)
        flag = "✅" if with_greeks else "❌"
        print(f"  {flag} {sym}: {n} contracts, {with_greeks} with greeks/IV")
        if not with_greeks:
            FAIL.append(f"{sym} greeks")
    except Exception as e:
        print(f"  ❌ {sym}: {type(e).__name__}: {e}")
        FAIL.append(f"{sym} chain")

print("\n" + "="*52)
if FAIL:
    print(f"🛑 {len(FAIL)} check(s) failed: {', '.join(FAIL)}")
    sys.exit(1)
print("✅ ALL PREFLIGHT CHECKS PASSED — safe to start the daemon")
print("   next:  python3 -m agent.daemon --once")
