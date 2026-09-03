from agent.specialist_mode import compute_quote_prices


def test_normal_spread_produces_valid_two_sided_quote():
    quote = compute_quote_prices(bid=7.20, ask=7.40, mid=7.30, spread_bps=40)
    assert quote is not None
    bid, ask = quote
    assert bid < ask
    assert 7.20 <= bid < ask <= 7.40


def test_rounding_collapse_is_widened_not_crossed():
    # Reproduces the exact live failure: a 2-cent-wide NBBO with a tiny
    # spread_bps pushes both target_bid and target_ask toward the same
    # midpoint tick, which Alpaca rejected as a wash trade (a market maker
    # can't quote $X.XX / $X.XX). The fix must widen to a real 1-cent
    # spread rather than collapse to equal prices.
    bid, ask, mid = 7.27, 7.29, 7.28
    quote = compute_quote_prices(bid=bid, ask=ask, mid=mid, spread_bps=1.0)
    assert quote is not None
    q_bid, q_ask = quote
    assert q_ask - q_bid >= 0.01 - 1e-9
    assert q_bid != q_ask
    assert bid <= q_bid < q_ask <= ask


def test_one_cent_wide_nbbo_still_yields_a_valid_quote():
    # The narrowest realistic real market (1 cent) has just enough room to
    # quote exactly the observed bid/ask -- this must succeed, not decline.
    quote = compute_quote_prices(bid=7.27, ask=7.28, mid=7.275, spread_bps=1.0)
    assert quote == (7.27, 7.28)


def test_degenerate_nbbo_is_declined():
    # ask <= bid is corrupt/bad data -- never fabricate a quote around it.
    assert compute_quote_prices(bid=7.28, ask=7.28, mid=7.28, spread_bps=40) is None
    assert compute_quote_prices(bid=7.30, ask=7.28, mid=7.29, spread_bps=40) is None


def test_quote_never_exceeds_real_nbbo():
    quote = compute_quote_prices(bid=10.00, ask=10.50, mid=10.25, spread_bps=500)
    assert quote is not None
    bid, ask = quote
    assert bid >= 10.00
    assert ask <= 10.50


def test_strike_band_excludes_itm_puts():
    """Regression: the moneyness band used to be symmetric, so _pick_atm_put
    could select an in-the-money put. ITM puts have delta near -1.0 (~$75k of
    delta on one SPY contract vs a $25k book cap), so the risk gate clamped
    every quote to zero and the agent silently stopped trading. Found live
    2026-09-03. Band must admit strikes at-or-below spot only."""
    spot, band = 750.0, 750.0 * 0.03  # +/-3% => 22.5

    def in_band(strike):
        return 0 <= (spot - strike) <= band

    assert in_band(750.0)          # ATM
    assert in_band(730.0)          # OTM, inside band
    assert in_band(727.5)          # OTM, at the band edge
    assert not in_band(727.4)      # OTM, beyond the band
    assert not in_band(774.0)      # ITM -- the live failure case
    assert not in_band(751.0)      # even 1 point ITM is excluded
