import math

from agent.pricing import implied_volatility, position_dollar_greeks, price_and_greeks


def test_call_delta_bounds():
    g = price_and_greeks(S=100, K=100, T=30 / 365, r=0.05, sigma=0.25, option_type="call")
    assert 0.0 <= g.delta <= 1.0
    assert g.gamma > 0
    assert g.price > 0


def test_put_delta_bounds():
    g = price_and_greeks(S=100, K=100, T=30 / 365, r=0.05, sigma=0.25, option_type="put")
    assert -1.0 <= g.delta <= 0.0
    assert g.gamma > 0


def test_put_call_parity():
    S, K, T, r, sigma = 100, 105, 45 / 365, 0.045, 0.30
    call = price_and_greeks(S, K, T, r, sigma, "call")
    put = price_and_greeks(S, K, T, r, sigma, "put")
    # C - P = S - K*e^(-rT)
    lhs = call.price - put.price
    rhs = S - K * math.exp(-r * T)
    assert abs(lhs - rhs) < 1e-6


def test_implied_volatility_round_trip():
    S, K, T, r, sigma_true = 450, 445, 21 / 365, 0.045, 0.22
    theo = price_and_greeks(S, K, T, r, sigma_true, "call")
    recovered = implied_volatility(theo.price, S, K, T, r, "call")
    assert recovered is not None
    assert abs(recovered - sigma_true) < 1e-4


def test_implied_volatility_handles_arbitrage_violating_price():
    # a call priced below intrinsic value is not a real market price
    recovered = implied_volatility(market_price=0.01, S=100, K=50, T=30 / 365, r=0.05, option_type="call")
    assert recovered is None


def test_position_dollar_greeks_short_call_is_negative_delta_dollars():
    g = price_and_greeks(S=100, K=100, T=30 / 365, r=0.05, sigma=0.25, option_type="call")
    dollar_greeks = position_dollar_greeks(g, qty=-1, underlying_price=100)
    assert dollar_greeks["delta_dollars"] < 0  # short a call -> negative delta exposure
