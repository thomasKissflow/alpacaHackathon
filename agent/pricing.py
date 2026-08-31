"""
Options pricing, from scratch: Black-Scholes (European, no dividend yield --
fine for the short-dated, liquid, cash-settled-adjacent names in the basket)
plus a Newton-Raphson implied-volatility solver. This is the primary pricing
path per the hackathon requirements; py_vollib (if installed) is used only
as an optional cross-check in scripts/crosscheck_pricing.py, never in the
live quoting/hedging path.

Conventions used everywhere else in this codebase:
- `delta`, `gamma`, `theta` are per-share (i.e. per one unit of the
  underlying), matching standard option quoting.
- `vega` is quoted per 1 vol point (1.00 = 100% -> divide by 100 vs the raw
  calculus derivative), which is the market-standard "$ P&L per 1% IV move"
  convention.
- `theta` is per calendar day (raw annualized theta / 365), not per year.
- To get dollar Greeks for a position: multiply by the option's contract
  multiplier (100 for standard US equity options) and by the number of
  contracts. Delta-dollars additionally multiplies by the underlying price.
"""
import math
from dataclasses import dataclass

CONTRACT_MULTIPLIER = 100
_MIN_T_YEARS = 1e-6  # floor to avoid div-by-zero on expiration day


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


@dataclass
class Greeks:
    price: float
    delta: float
    gamma: float
    vega: float   # $ per 1 vol point (per share)
    theta: float  # $ per calendar day (per share)


def _d1_d2(S: float, K: float, T: float, r: float, sigma: float) -> tuple[float, float]:
    if S <= 0 or K <= 0:
        raise ValueError("S and K must be positive")
    T = max(T, _MIN_T_YEARS)
    if sigma <= 0:
        raise ValueError("sigma must be positive")
    sqrtT = math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * sqrtT)
    d2 = d1 - sigma * sqrtT
    return d1, d2


def price_and_greeks(S: float, K: float, T: float, r: float, sigma: float, option_type: str) -> Greeks:
    """European Black-Scholes price + Greeks. T in years, r as a decimal annual rate."""
    T = max(T, _MIN_T_YEARS)
    d1, d2 = _d1_d2(S, K, T, r, sigma)
    pdf_d1 = _norm_pdf(d1)
    sqrtT = math.sqrt(T)
    disc = math.exp(-r * T)

    if option_type == "call":
        price = S * _norm_cdf(d1) - K * disc * _norm_cdf(d2)
        delta = _norm_cdf(d1)
        theta_annual = -(S * pdf_d1 * sigma) / (2 * sqrtT) - r * K * disc * _norm_cdf(d2)
    elif option_type == "put":
        price = K * disc * _norm_cdf(-d2) - S * _norm_cdf(-d1)
        delta = _norm_cdf(d1) - 1.0
        theta_annual = -(S * pdf_d1 * sigma) / (2 * sqrtT) + r * K * disc * _norm_cdf(-d2)
    else:
        raise ValueError(f"option_type must be 'call' or 'put', got {option_type!r}")

    gamma = pdf_d1 / (S * sigma * sqrtT)
    vega_raw = S * pdf_d1 * sqrtT  # dPrice/dSigma, sigma in decimal (1.0 = 100%)

    return Greeks(
        price=price,
        delta=delta,
        gamma=gamma,
        vega=vega_raw / 100.0,
        theta=theta_annual / 365.0,
    )


def implied_volatility(
    market_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    option_type: str,
    initial_guess: float = 0.35,
    tol: float = 1e-5,
    max_iter: int = 100,
) -> float | None:
    """Newton-Raphson IV solve. Falls back to bisection if Newton misbehaves
    (near-zero vega at very deep ITM/OTM strikes). Returns None if it can't
    converge to a sane (0, 5.0) vol within max_iter."""
    T = max(T, _MIN_T_YEARS)
    intrinsic = max(S - K, 0.0) if option_type == "call" else max(K - S, 0.0)
    if market_price < intrinsic - 1e-6:
        return None  # arbitrage-violating quote, don't trust it

    sigma = initial_guess
    for _ in range(max_iter):
        try:
            g = price_and_greeks(S, K, T, r, sigma, option_type)
        except ValueError:
            break
        diff = g.price - market_price
        if abs(diff) < tol:
            return round(sigma, 6)
        vega_raw = g.vega * 100.0
        if vega_raw < 1e-8:
            break
        step = diff / vega_raw
        sigma -= step
        if sigma <= 0 or sigma > 5:
            sigma = max(min(sigma, 5.0), 1e-4)

    return _bisect_iv(market_price, S, K, T, r, option_type)


def _bisect_iv(market_price, S, K, T, r, option_type, lo=1e-4, hi=5.0, tol=1e-5, max_iter=200):
    def f(sig):
        return price_and_greeks(S, K, T, r, sig, option_type).price - market_price

    f_lo, f_hi = f(lo), f(hi)
    if f_lo * f_hi > 0:
        return None  # no sign change in range, can't bisect
    for _ in range(max_iter):
        mid = (lo + hi) / 2
        f_mid = f(mid)
        if abs(f_mid) < tol:
            return round(mid, 6)
        if f_lo * f_mid < 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return round((lo + hi) / 2, 6)


def position_dollar_greeks(greeks: Greeks, qty: int, underlying_price: float) -> dict:
    """qty is signed: positive = long contracts, negative = short contracts."""
    shares_equiv = qty * CONTRACT_MULTIPLIER
    return {
        "delta_dollars": greeks.delta * shares_equiv * underlying_price,
        "gamma_shares_per_dollar": greeks.gamma * shares_equiv,
        "vega_dollars": greeks.vega * shares_equiv,
        "theta_dollars": greeks.theta * shares_equiv,
    }
