"""
LEARNING SCRIPT 3: A safe, read-only look at your connected Alpaca account.

This is the ONLY script in examples/ that talks to the internet / Alpaca.
It only ever READS data -- it never places, cancels, or modifies an order
or position. Safe to run any time. Run it with:

    source .venv/bin/activate
    python examples/03_check_account.py

Needs ALPACA_API_KEY / ALPACA_SECRET_KEY set in your .env file (see
.env.example and README "Setup" section) to do anything -- otherwise
it'll print a clear error telling you what's missing.
--------------------------------------------------------------------------
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.config import ALPACA_API_KEY, ALPACA_SECRET_KEY  # noqa: E402

if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
    print("No Alpaca keys found. Copy .env.example to .env and fill in")
    print("ALPACA_API_KEY / ALPACA_SECRET_KEY (see README 'Setup' section), then re-run this.")
    sys.exit(1)

from agent.clients import option_data_client, stock_data_client, trading_client  # noqa: E402
from alpaca.data.requests import OptionChainRequest, StockLatestQuoteRequest  # noqa: E402


def section(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


section("Your paper trading account")

account = trading_client.get_account()
print(f"Account ID:       {account.id}")
print(f"Status:            {account.status}")
print(f"Equity:            ${float(account.equity):,.2f}")
print(f"Cash:              ${float(account.cash):,.2f}")
print(f"Buying power:      ${float(account.buying_power):,.2f}")
print(f"Options level:     {account.options_trading_level}  (3 = spreads allowed, the max on Alpaca)")
print(f"Created:           {account.created_at}")

if float(account.equity) == 100_000:
    print("\n(Equity is exactly $100k -- looks like a fresh, untraded account, which is what")
    print(" the hackathon's competition account needs to be. See docs/setup-guide.md.)")
else:
    print(f"\n(Equity has moved away from $100k, so this account has some trading history --")
    print(" fine for a dev/sandbox account, but the actual competition account needs to stay")
    print(" untouched until it's genuinely trading for real. See docs/decisions.md D-013.)")


section("A live stock quote (SPY)")

quote = stock_data_client.get_stock_latest_quote(StockLatestQuoteRequest(symbol_or_symbols="SPY"))["SPY"]
print(f"SPY bid: ${quote.bid_price}   ask: ${quote.ask_price}")
print("(This is delayed/indicative data on Alpaca's free tier, not real-time SIP data --")
print(" see docs/research.md if you're curious why, and why that's fine for this project.)")


section("A live options chain (SPY) -- first 5 contracts with valid Greeks")

chain = option_data_client.get_option_chain(OptionChainRequest(underlying_symbol="SPY"))
print(f"Total contracts returned: {len(chain)}")
shown = 0
for occ_symbol, snapshot in chain.items():
    greeks = getattr(snapshot, "greeks", None)
    if greeks is None:
        continue  # Alpaca only computes Greeks when the contract has a real bid AND ask
    quote = getattr(snapshot, "latest_quote", None)
    print(f"  {occ_symbol}: bid={quote.bid_price} ask={quote.ask_price} delta={greeks.delta:.3f} iv={snapshot.implied_volatility:.3f}")
    shown += 1
    if shown >= 5:
        break

print("\nDone! This is exactly the data agent/specialist_mode.py and agent/scanner.py")
print("pull every cycle to decide what to quote. Try changing 'SPY' above to 'QQQ' or 'AAPL'.")
