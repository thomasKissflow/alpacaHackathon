"""
LEARNING SCRIPT 1: What is an option "worth", and what do the Greeks mean?

This script doesn't touch Alpaca or the internet at all -- it's pure math,
safe to run as many times as you want. Run it with:

    source .venv/bin/activate
    python examples/01_pricing_demo.py

--------------------------------------------------------------------------
Background, in plain language:

An option is a contract that gives you the RIGHT (not obligation) to buy
(a "call") or sell (a "put") 100 shares of a stock at a fixed price (the
"strike") by a certain date (the "expiration"). Because it's a right, not
an obligation, it has its own price -- the "premium" -- and that price
depends on 5 things: the stock's current price, the strike, how much time
is left, interest rates, and how volatile the stock is expected to be.

The Black-Scholes formula is the classic way to compute a "fair" price for
an option given those 5 inputs. This project implements it from scratch in
agent/pricing.py (no external pricing library) -- this script just calls
that code and prints the results with explanations.

The "Greeks" are how much the option's price changes as each input changes:
  - delta: how much the option's price moves per $1 move in the stock.
           A delta of 0.50 means "if the stock goes up $1, this option
           gains about $0.50." Calls have positive delta (0 to 1), puts
           have negative delta (-1 to 0).
  - gamma: how much delta itself changes per $1 move in the stock. High
           gamma means delta changes fast -- the position gets riskier
           quickly as the stock moves.
  - vega:  how much the option's price changes if implied volatility moves
           by 1 percentage point (e.g. 20% -> 21%).
  - theta: how much value the option loses per day just from time passing
           ("time decay"), holding everything else constant.

This project uses delta to figure out how many shares of stock to buy or
sell to "hedge" an option position back toward flat risk -- see
agent/specialist_mode.py's _rebalance_hedge() function.
--------------------------------------------------------------------------
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.pricing import implied_volatility, price_and_greeks  # noqa: E402


def section(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


section("Example 1: price a call option")

# Imagine a stock trading at $450, and we want to price a CALL option with
# a $450 strike (this is "at-the-money" -- strike equals the current price)
# expiring in 30 days, assuming 20% annualized volatility and a 4.5%
# risk-free interest rate.
stock_price = 450.0
strike = 450.0
days_to_expiration = 30
time_in_years = days_to_expiration / 365.0
risk_free_rate = 0.045
volatility = 0.20  # 20% -- a typical value for a calm market

call = price_and_greeks(
    S=stock_price, K=strike, T=time_in_years, r=risk_free_rate,
    sigma=volatility, option_type="call",
)

print(f"Stock price:        ${stock_price:.2f}")
print(f"Strike price:       ${strike:.2f}")
print(f"Days to expiration: {days_to_expiration}")
print(f"Volatility:         {volatility:.0%}")
print()
print(f"--> Fair price of this call option: ${call.price:.2f} per share (x100 = ${call.price*100:.2f} per contract)")
print(f"--> Delta: {call.delta:.3f}  (if the stock moves +$1, this option gains about ${call.delta:.2f})")
print(f"--> Gamma: {call.gamma:.4f}  (delta itself would move by about this much per $1 stock move)")
print(f"--> Vega:  ${call.vega:.2f}  (if implied vol rises 1 point, e.g. 20%->21%, this option gains about ${call.vega:.2f})")
print(f"--> Theta: ${call.theta:.2f}  (this option loses about ${-call.theta:.2f} in value per day, all else equal)")


section("Example 2: the same strike, but a PUT instead of a call")

put = price_and_greeks(
    S=stock_price, K=strike, T=time_in_years, r=risk_free_rate,
    sigma=volatility, option_type="put",
)
print(f"--> Fair price of this put option: ${put.price:.2f} per share")
print(f"--> Delta: {put.delta:.3f}  (notice it's NEGATIVE -- puts gain value when the stock goes DOWN)")
print("\nNotice call.delta - put.delta should be close to 1.0 -- that's put-call parity, a sanity check:")
print(f"   {call.delta:.3f} - ({put.delta:.3f}) = {call.delta - put.delta:.3f}")


section("Example 3: what happens to price/delta as the stock moves?")

print(f"{'Stock price':>12} | {'Call price':>10} | {'Call delta':>10}")
for bump in (-20, -10, 0, 10, 20):
    s = stock_price + bump
    g = price_and_greeks(S=s, K=strike, T=time_in_years, r=risk_free_rate, sigma=volatility, option_type="call")
    print(f"{s:>12.2f} | {g.price:>10.2f} | {g.delta:>10.3f}")
print("\nNotice: as the stock price rises, the call's delta rises toward 1.0")
print("(it starts behaving more and more like just owning 100 shares outright).")


section("Example 4: implied volatility -- working BACKWARDS from a market price")

# In real trading you don't know the "true" volatility -- you only see the
# market's current bid/ask for the option. Implied volatility (IV) answers:
# "what volatility would make Black-Scholes agree with this market price?"
# This project solves for it from scratch with Newton-Raphson (no library) --
# see implied_volatility() in agent/pricing.py.
market_price = 9.30  # pretend this is the option's current mid-price in the market
solved_iv = implied_volatility(
    market_price=market_price, S=stock_price, K=strike, T=time_in_years,
    r=risk_free_rate, option_type="call",
)
print(f"If this call is trading at ${market_price:.2f} in the market,")
print(f"the implied volatility the market is pricing in is: {solved_iv:.1%}")
print("\nThe agent (agent/specialist_mode.py) does exactly this every cycle: it looks at the")
print("live bid/ask for each option it's watching, solves for IV, then uses that IV to compute")
print("a fresh theoretical price and Greeks -- which is what it quotes around.")

print("\nDone! Try changing stock_price, strike, days_to_expiration, or volatility above and")
print("re-running to build intuition for how they interact.")
