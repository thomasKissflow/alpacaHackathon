"""
Two ways into Alpaca, used deliberately for different jobs:

1. alpaca-py SDK  -> option chain data + typed multi-leg order construction.
   The typed request objects (OptionLegRequest, OrderClass.MLEG) are the most
   reliable way to build a 2-4 leg spread correctly.

2. Alpaca CLI (subprocess) -> account/position/order telemetry.
   This is what satisfies the hackathon's "MCP or CLI" core requirement, and
   it's genuinely the right tool here: Alpaca's own docs recommend the CLI
   for "long-running agent sessions, cron jobs and CI" -- exactly this
   scheduled-run agent. During interactive strategy development, point
   Claude/Cursor at the Alpaca MCP server instead (see README).

If you don't have the `alpaca` CLI installed locally, cli_get() will raise --
install it first (see README) or the GitHub Actions workflow will install it
for you on each scheduled run.
"""
import json
import subprocess

from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.requests import OptionLatestQuoteRequest, StockLatestQuoteRequest
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, QueryOrderStatus, TimeInForce
from alpaca.trading.requests import GetOrdersRequest, LimitOrderRequest, MarketOrderRequest

from agent.config import ALPACA_API_KEY, ALPACA_SECRET_KEY, PAPER


class _LazyClient:
    """Defers constructing the real alpaca-py client (which validates
    credentials immediately) until the first attribute access. Lets the rest
    of this codebase -- and the whole test suite -- import `agent.clients`
    and everything downstream of it without real API keys present; only an
    actual network call requires them."""

    def __init__(self, factory):
        self._factory = factory
        self._instance = None

    def _get(self):
        if self._instance is None:
            self._instance = self._factory()
        return self._instance

    def __getattr__(self, name):
        return getattr(self._get(), name)


trading_client = _LazyClient(lambda: TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=PAPER))
option_data_client = _LazyClient(lambda: OptionHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY))
stock_data_client = _LazyClient(lambda: StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY))


def cli_get(*args: str) -> dict | list:
    """Run an `alpaca ... ` read command and parse its JSON stdout.

    Example: cli_get("account", "get") -> {"equity": "100000.00", ...}
             cli_get("position", "list") -> [...]
    """
    cmd = ["alpaca", *args]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"alpaca CLI failed: {' '.join(cmd)}\n{result.stderr}")
    return json.loads(result.stdout)


def get_option_nbbo(occ_symbol: str) -> tuple[float, float] | None:
    """Returns (bid, ask) for one OCC option symbol, or None if unquoted."""
    quotes = option_data_client.get_option_latest_quote(OptionLatestQuoteRequest(symbol_or_symbols=occ_symbol))
    q = quotes.get(occ_symbol)
    if q is None or q.bid_price in (None, 0) or q.ask_price in (None, 0):
        return None
    return float(q.bid_price), float(q.ask_price)


def get_underlying_mid(symbol: str) -> float | None:
    quotes = stock_data_client.get_stock_latest_quote(StockLatestQuoteRequest(symbol_or_symbols=symbol))
    q = quotes.get(symbol)
    if q is None or q.bid_price in (None, 0) or q.ask_price in (None, 0):
        return None
    return (float(q.bid_price) + float(q.ask_price)) / 2.0


def get_open_orders(symbol: str) -> list:
    req = GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[symbol], nested=False)
    return trading_client.get_orders(req)


def get_recent_orders(symbol: str, limit: int = 10) -> list:
    req = GetOrdersRequest(status=QueryOrderStatus.ALL, symbols=[symbol], limit=limit, nested=False)
    return trading_client.get_orders(req)


def place_option_limit_order(occ_symbol: str, side: str, qty: int, limit_price: float):
    order_req = LimitOrderRequest(
        symbol=occ_symbol,
        qty=qty,
        side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
        time_in_force=TimeInForce.DAY,
        limit_price=round(limit_price, 2),
    )
    return trading_client.submit_order(order_req)


def place_equity_market_order(symbol: str, side: str, qty: int):
    order_req = MarketOrderRequest(
        symbol=symbol, qty=qty,
        side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
        time_in_force=TimeInForce.DAY,
    )
    return trading_client.submit_order(order_req)


def cancel_order(order_id: str) -> None:
    try:
        trading_client.cancel_order_by_id(order_id)
    except Exception as exc:  # noqa: BLE001 - order may have already filled/expired between check and cancel
        print(f"[clients] cancel_order_by_id({order_id}) failed (likely already terminal): {exc}")
