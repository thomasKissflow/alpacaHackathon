"""The market-maker's core invariant: never close a position at a loss.

Reproduces the live failure of 2026-09-03, where the agent bought at 11.10 and
then quoted a sell at 10.92 to flatten inventory — 33 round trips for -$85
gross captured. A market maker that pays the spread on both sides is not
making a market.
"""
import pytest

from agent.specialist_mode import apply_inventory_cost_floor as floor
from agent.config import RISK


MID = 11.00


def test_the_live_failure_case_is_now_prevented():
    """Bought at 11.10; market drifted; agent wanted to sell at 10.92."""
    out = floor("sell", price=10.92, qty=1, avg_price=11.10, mid=MID)
    assert out > 11.10, "must not sell below cost"


def test_long_inventory_sells_above_cost_plus_edge():
    out = floor("sell", price=10.50, qty=3, avg_price=11.10, mid=MID)
    expected_edge = max(0.01, MID * RISK.min_close_edge_bps / 10_000.0)
    assert out == pytest.approx(round(11.10 + expected_edge, 2))


def test_short_inventory_buys_below_cost_minus_edge():
    out = floor("buy", price=11.40, qty=-2, avg_price=11.00, mid=MID)
    expected_edge = max(0.01, MID * RISK.min_close_edge_bps / 10_000.0)
    assert out == pytest.approx(round(11.00 - expected_edge, 2))


def test_a_better_market_price_is_kept():
    """If the market is already offering more than our floor, take it."""
    assert floor("sell", price=12.50, qty=1, avg_price=11.10, mid=MID) == 12.50
    assert floor("buy", price=9.00, qty=-1, avg_price=11.00, mid=MID) == 9.00


def test_opening_a_position_is_unconstrained():
    """Flat book: the market-relative price IS the edge. Do not touch it."""
    assert floor("buy", price=10.90, qty=0, avg_price=0.0, mid=MID) == 10.90
    assert floor("sell", price=11.10, qty=0, avg_price=0.0, mid=MID) == 11.10


def test_adding_to_a_position_is_unconstrained():
    """Buying while already long is opening more risk, not closing — the floor
    only applies to the side that reduces the position."""
    assert floor("buy", price=10.90, qty=2, avg_price=11.10, mid=MID) == 10.90
    assert floor("sell", price=11.10, qty=-2, avg_price=11.00, mid=MID) == 11.10


def test_missing_cost_basis_is_a_noop():
    assert floor("sell", price=10.92, qty=1, avg_price=0.0, mid=MID) == 10.92


def test_edge_never_smaller_than_one_tick():
    """On a cheap contract, bps-of-mid rounds to sub-penny; must still move."""
    out = floor("sell", price=0.50, qty=1, avg_price=0.50, mid=0.50)
    assert out >= 0.51
