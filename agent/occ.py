"""
Alpaca's option chain/snapshot objects don't carry strike/expiration/type as
separate fields -- they're encoded in the OCC option symbol itself, e.g.
"SPY251003C00450000" = SPY, exp 2025-10-03, Call, strike 450.00.
"""
from dataclasses import dataclass
from datetime import date


@dataclass
class ParsedOccSymbol:
    underlying: str
    expiration: date
    option_type: str  # "call" | "put"
    strike: float


def parse_occ_symbol(underlying: str, occ_symbol: str) -> ParsedOccSymbol:
    if not occ_symbol.startswith(underlying):
        raise ValueError(f"{occ_symbol!r} does not start with underlying {underlying!r}")
    remainder = occ_symbol[len(underlying):]
    date_str, cp, strike_str = remainder[:6], remainder[6], remainder[7:]
    yy, mm, dd = int(date_str[0:2]), int(date_str[2:4]), int(date_str[4:6])
    expiration = date(2000 + yy, mm, dd)
    option_type = "call" if cp.upper() == "C" else "put"
    strike = int(strike_str) / 1000.0
    return ParsedOccSymbol(underlying=underlying, expiration=expiration, option_type=option_type, strike=strike)
