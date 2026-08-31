"""
Scanner Agent: for each candidate underlying, pulls the live option chain,
derives a simple ATM implied-vol proxy, and ranks it against IV readings the
agent has collected for itself over the week (Alpaca doesn't expose a
ready-made "IV Rank" field, so we build one from repeated snapshots -- this
is a known MVP simplification, called out in the write-up).

Also pulls recent daily bars to get a cheap trend read (SMA20 vs SMA50) so
the Strategy Agent can pick a directionally-appropriate spread.
"""
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import mean

from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.requests import OptionChainRequest, StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from agent.clients import option_data_client, stock_data_client
from agent.config import IV_HISTORY, RISK
from agent.occ import parse_occ_symbol


@dataclass
class Candidate:
    symbol: str
    atm_iv: float
    iv_rank: float
    trend: str  # "bullish" | "bearish" | "neutral"
    chain: dict  # symbol -> OptionsSnapshot, for the Strategy Agent to pick strikes from


def _load_iv_history() -> dict:
    if IV_HISTORY.exists():
        return json.loads(IV_HISTORY.read_text())
    return {}


def _save_iv_history(history: dict) -> None:
    IV_HISTORY.parent.mkdir(parents=True, exist_ok=True)
    IV_HISTORY.write_text(json.dumps(history, indent=2))


def _atm_iv(underlying: str, chain: dict, underlying_price: float) -> float | None:
    """Average IV of the two contracts (one call, one put) closest to the money."""
    closest_call, closest_put, best_call_diff, best_put_diff = None, None, float("inf"), float("inf")
    for occ_symbol, snap in chain.items():
        iv = getattr(snap, "implied_volatility", None)
        if iv is None:
            continue
        try:
            parsed = parse_occ_symbol(underlying, occ_symbol)
        except ValueError:
            continue
        diff = abs(parsed.strike - underlying_price)
        if parsed.option_type == "call" and diff < best_call_diff:
            best_call_diff, closest_call = diff, iv
        elif parsed.option_type == "put" and diff < best_put_diff:
            best_put_diff, closest_put = diff, iv
    ivs = [v for v in (closest_call, closest_put) if v is not None]
    return mean(ivs) if ivs else None


def _trend(symbol: str) -> str:
    bars_req = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Day,
        start=datetime.now(timezone.utc) - timedelta(days=90),
    )
    bars = stock_data_client.get_stock_bars(bars_req).data.get(symbol, [])
    closes = [b.close for b in bars]
    if len(closes) < 50:
        return "neutral"
    sma20 = mean(closes[-20:])
    sma50 = mean(closes[-50:])
    if sma20 > sma50 * 1.01:
        return "bullish"
    if sma20 < sma50 * 0.99:
        return "bearish"
    return "neutral"


def scan() -> list[Candidate]:
    history = _load_iv_history()
    candidates = []
    today = datetime.now(timezone.utc).date().isoformat()

    for symbol in RISK.candidate_underlyings:
        try:
            chain_req = OptionChainRequest(underlying_symbol=symbol)
            chain = option_data_client.get_option_chain(chain_req)
        except Exception as exc:  # noqa: BLE001 - log and skip a bad symbol, don't crash the run
            print(f"[scanner] skipping {symbol}: {exc}")
            continue

        last_prices = [getattr(s.latest_trade, "price", None) for s in chain.values() if getattr(s, "latest_trade", None)]
        underlying_price = mean([p for p in last_prices if p]) if last_prices else None
        if underlying_price is None:
            continue

        atm_iv = _atm_iv(symbol, chain, underlying_price)
        if atm_iv is None:
            continue

        series = history.setdefault(symbol, [])
        series.append({"date": today, "iv": atm_iv})
        history[symbol] = series[-60:]  # keep a rolling window

        readings = [pt["iv"] for pt in series]
        if len(readings) < 5:
            iv_rank = 50.0  # not enough history yet -- treat as neutral, don't block entry
        else:
            lo, hi = min(readings), max(readings)
            iv_rank = 50.0 if hi == lo else 100 * (atm_iv - lo) / (hi - lo)

        candidates.append(
            Candidate(symbol=symbol, atm_iv=atm_iv, iv_rank=iv_rank, trend=_trend(symbol), chain=chain)
        )

    _save_iv_history(history)
    candidates.sort(key=lambda c: c.iv_rank, reverse=True)
    return candidates
