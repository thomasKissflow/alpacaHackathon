"""
Scheduled-macro-event awareness.

Every other strategy input this agent uses is reactive -- it reads prices and
Greeks that have already moved. Scheduled macro releases are the one thing a
trading agent can know about *in advance*, and the single largest of them
lands inside this competition's judging window:

    Non-Farm Payrolls (August 2026)  --  Fri 4 Sep 2026, 08:30 ET

That is one hour before the final session opens and 2.5 hours before the
submission deadline. Index implied vol is bid up ahead of the print and
collapses once the number is known ("IV crush"), and the underlying gaps on
the open.

The posture this module takes is deliberately the conservative one:

  * BEFORE the print  -> de-risk. Widen quotes (be paid more for carrying
    event risk), cut size, and stop opening NEW short-premium positions that
    would still be open across the release. A short-gamma book gapping
    through its strikes overnight is the one loss this account cannot
    recover from before judging.

  * ACROSS the print  -> blackout. Place nothing.

  * AFTER the print   -> re-engage. The uncertainty premium has collapsed,
    so market-making is *safer* post-event, not riskier: quote tighter to
    win fills, restore normal size.

This is what an actual options desk does around a known event. It is not a
directional bet on the number -- the agent has no opinion on payrolls, only
on the fact that uncertainty is scheduled, priced, and then resolved.

Rationale and prior art: docs/research.md section 5.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------- calendar ---
# 08:30 ET during EDT == 12:30 UTC.
SCHEDULED_EVENTS: list[dict] = [
    {
        "name": "Non-Farm Payrolls (Aug 2026)",
        "at": datetime(2026, 9, 4, 12, 30, tzinfo=timezone.utc),
        "severity": "high",
    },
]

# How long before/after a high-severity event each phase lasts.
DERISK_LEAD = timedelta(hours=20)      # covers the whole prior session + overnight
BLACKOUT_LEAD = timedelta(minutes=45)
BLACKOUT_TRAIL = timedelta(minutes=75)  # 12:30 UTC print -> ~13:45 UTC, just after the 13:30 open
REENGAGE_TRAIL = timedelta(hours=5)


@dataclass(frozen=True)
class EventPosture:
    phase: str                  # 'normal' | 'derisk' | 'blackout' | 'reengage'
    event_name: str | None
    minutes_to_event: float | None
    spread_multiplier: float    # scales target quoted width
    size_multiplier: float      # scales quote size
    block_new_short_premium: bool
    reason: str

    @property
    def is_blackout(self) -> bool:
        return self.phase == "blackout"


NORMAL = EventPosture(
    phase="normal", event_name=None, minutes_to_event=None,
    spread_multiplier=1.0, size_multiplier=1.0,
    block_new_short_premium=False, reason="no scheduled event nearby",
)


def _next_relevant(now: datetime) -> tuple[dict, float] | None:
    """Closest event whose influence window contains `now`, with signed
    minutes until it (negative once it has passed)."""
    best = None
    for ev in SCHEDULED_EVENTS:
        delta_min = (ev["at"] - now).total_seconds() / 60.0
        if -REENGAGE_TRAIL.total_seconds() / 60.0 <= delta_min <= DERISK_LEAD.total_seconds() / 60.0:
            if best is None or abs(delta_min) < abs(best[1]):
                best = (ev, delta_min)
    return best


def current_posture(now: datetime | None = None) -> EventPosture:
    now = now or datetime.now(timezone.utc)
    found = _next_relevant(now)
    if not found:
        return NORMAL
    ev, mins = found
    name = ev["name"]

    if -BLACKOUT_TRAIL.total_seconds() / 60 <= mins <= BLACKOUT_LEAD.total_seconds() / 60:
        return EventPosture(
            phase="blackout", event_name=name, minutes_to_event=mins,
            spread_multiplier=1.0, size_multiplier=0.0, block_new_short_premium=True,
            reason=f"{name} in {mins:.0f} min - blackout, placing nothing across the print",
        )

    if mins > 0:
        return EventPosture(
            phase="derisk", event_name=name, minutes_to_event=mins,
            spread_multiplier=1.6, size_multiplier=0.75, block_new_short_premium=True,
            reason=(f"{name} in {mins/60:.1f}h - de-risking: quotes widened 1.6x, size cut 25%, "
                    f"no new short premium held across the release"),
        )

    return EventPosture(
        phase="reengage", event_name=name, minutes_to_event=mins,
        spread_multiplier=0.85, size_multiplier=1.0, block_new_short_premium=False,
        reason=(f"{name} released {abs(mins):.0f} min ago - event premium has collapsed; "
                f"re-engaging with tighter quotes to win fills into the post-print IV crush"),
    )


def apply_to_plan(plan: dict, posture: EventPosture) -> dict:
    """Fold the posture into an approved MarketPlan. Deterministic, and applied
    AFTER the LLM has spoken -- the model can never widen its way out of, or
    talk its way past, an event rule."""
    if posture.phase == "normal":
        return plan
    adjusted = dict(plan)
    spreads = dict(plan.get("target_spread_bps") or {})
    adjusted["target_spread_bps"] = {
        sym: round(bps * posture.spread_multiplier, 1) for sym, bps in spreads.items()
    }
    if "max_quote_size" in plan:
        adjusted["max_quote_size"] = max(0, int(plan["max_quote_size"] * posture.size_multiplier))
    adjusted["event_posture"] = posture.phase
    adjusted["event_reason"] = posture.reason
    return adjusted
