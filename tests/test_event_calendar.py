"""NFP event-rule behaviour. Pure time arithmetic -- no API calls."""
from datetime import datetime, timezone

from agent import event_calendar as ec

NFP = datetime(2026, 9, 4, 12, 30, tzinfo=timezone.utc)  # 08:30 ET


def at(**kw):
    from datetime import timedelta
    return NFP + timedelta(**kw)


def test_far_from_event_is_normal():
    p = ec.current_posture(at(days=-3))
    assert p.phase == "normal"
    assert p.spread_multiplier == 1.0 and p.size_multiplier == 1.0
    assert not p.block_new_short_premium


def test_prior_session_derisks():
    p = ec.current_posture(at(hours=-18))
    assert p.phase == "derisk"
    assert p.spread_multiplier > 1.0, "quotes must widen to be paid for event risk"
    assert p.size_multiplier < 1.0, "size must come down"
    assert p.block_new_short_premium, "no new short premium held across the print"


def test_blackout_across_the_print():
    for t in (at(minutes=-30), at(minutes=0), at(minutes=+60)):
        p = ec.current_posture(t)
        assert p.is_blackout, f"{t} should be blackout"
        assert p.size_multiplier == 0.0
        assert p.block_new_short_premium


def test_reengages_after_the_print():
    p = ec.current_posture(at(hours=+2))
    assert p.phase == "reengage"
    assert p.spread_multiplier < 1.0, "quote tighter once event premium has collapsed"
    assert p.size_multiplier == 1.0
    assert not p.block_new_short_premium


def test_reengage_window_covers_the_submission_deadline():
    """Friday's session runs 13:30-15:00 UTC before the 20:30 IST deadline.
    The agent must be actively trading through it, not still in blackout."""
    deadline = datetime(2026, 9, 4, 15, 0, tzinfo=timezone.utc)
    assert ec.current_posture(deadline).phase == "reengage"
    # and by 15 min after the open we are out of blackout
    assert ec.current_posture(datetime(2026, 9, 4, 13, 50, tzinfo=timezone.utc)).phase == "reengage"


def test_apply_to_plan_scales_spreads_and_size_and_is_pure():
    plan = {"symbols": ["SPY"], "target_spread_bps": {"SPY": 40.0}, "max_quote_size": 4}
    out = ec.apply_to_plan(plan, ec.current_posture(at(hours=-18)))
    assert out["target_spread_bps"]["SPY"] > 40.0
    assert out["max_quote_size"] < 4
    assert out["event_posture"] == "derisk" and out["event_reason"]
    assert plan["target_spread_bps"]["SPY"] == 40.0, "must not mutate the caller's plan"


def test_apply_to_plan_is_noop_when_normal():
    plan = {"symbols": ["SPY"], "target_spread_bps": {"SPY": 40.0}, "max_quote_size": 4}
    assert ec.apply_to_plan(plan, ec.current_posture(at(days=-3))) == plan
