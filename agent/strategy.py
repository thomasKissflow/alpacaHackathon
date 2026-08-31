"""
Strategy Agent: turns a scanned Candidate into a concrete, defined-risk,
premium-selling multi-leg plan. Deliberately a small fixed playbook (no
undefined-risk/naked legs, ever) rather than letting an LLM freehand strikes --
that's the "testable strategy" + risk-gate story the submission needs.

  neutral trend  -> Iron Condor        (short strangle + protective wings)
  bullish trend  -> Bull Put Spread    (sell downside, defined risk)
  bearish trend  -> Bear Call Spread   (sell upside, defined risk)
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from agent.config import RISK
from agent.occ import parse_occ_symbol
from agent.scanner import Candidate


@dataclass
class Leg:
    symbol: str  # OCC option symbol
    side: str  # "buy" | "sell"
    ratio_qty: int = 1


@dataclass
class StrategyPlan:
    strategy_type: str
    underlying: str
    expiration: date
    legs: list[Leg]
    net_credit_estimate: float  # per-contract, in dollars (not x100)
    max_loss_estimate: float  # per-contract, in dollars x100 multiplier applied
    rationale: str = ""


def _mid_price(snap) -> float | None:
    q = getattr(snap, "latest_quote", None)
    if not q:
        return None
    bid, ask = getattr(q, "bid_price", None), getattr(q, "ask_price", None)
    if bid is None or ask is None:
        return None
    return (bid + ask) / 2


def _contracts(chain: dict, underlying: str, expiration: date, option_type: str):
    out = []
    for occ_symbol, snap in chain.items():
        try:
            parsed = parse_occ_symbol(underlying, occ_symbol)
        except ValueError:
            continue
        if parsed.expiration == expiration and parsed.option_type == option_type:
            out.append((occ_symbol, parsed, snap))
    return out


def _pick_expiration(chain: dict, underlying: str) -> date | None:
    today = datetime.now(timezone.utc).date()
    lo, hi = today + timedelta(days=RISK.min_days_to_expiration), today + timedelta(days=RISK.max_days_to_expiration)
    expirations = set()
    for occ_symbol in chain:
        try:
            expirations.add(parse_occ_symbol(underlying, occ_symbol).expiration)
        except ValueError:
            continue
    in_range = sorted(e for e in expirations if lo <= e <= hi)
    return in_range[0] if in_range else None


def _pick_short_strike(contracts, target_delta: float):
    best, best_diff = None, float("inf")
    for occ_symbol, parsed, snap in contracts:
        greeks = getattr(snap, "greeks", None)
        delta = getattr(greeks, "delta", None) if greeks else None
        if delta is None:
            continue
        diff = abs(abs(delta) - target_delta)
        if diff < best_diff:
            best_diff, best = diff, (occ_symbol, parsed, snap)
    return best


def _pick_long_strike(contracts, target_strike: float):
    best, best_diff = None, float("inf")
    for occ_symbol, parsed, snap in contracts:
        diff = abs(parsed.strike - target_strike)
        if diff < best_diff:
            best_diff, best = diff, (occ_symbol, parsed, snap)
    return best


def _credit_spread(chain, underlying, expiration, option_type: str, direction: str) -> tuple | None:
    """direction: 'lower' (long strike below short, for puts) or 'higher' (for calls)."""
    contracts = _contracts(chain, underlying, expiration, option_type)
    if len(contracts) < 2:
        return None
    short = _pick_short_strike(contracts, RISK.target_short_leg_delta)
    if short is None:
        return None
    _, short_parsed, short_snap = short
    target_long_strike = (
        short_parsed.strike - RISK.spread_width_dollars
        if direction == "lower"
        else short_parsed.strike + RISK.spread_width_dollars
    )
    remaining = [c for c in contracts if c[0] != short[0]]
    long_ = _pick_long_strike(remaining, target_long_strike)
    if long_ is None:
        return None
    _, long_parsed, long_snap = long_
    short_mid, long_mid = _mid_price(short_snap), _mid_price(long_snap)
    if short_mid is None or long_mid is None:
        return None
    credit = short_mid - long_mid
    width = abs(long_parsed.strike - short_parsed.strike)
    return short, long_, credit, width


def build_plan(candidate: Candidate) -> StrategyPlan | None:
    if candidate.iv_rank < RISK.min_iv_rank_for_entry:
        return None

    expiration = _pick_expiration(candidate.chain, candidate.symbol)
    if expiration is None:
        return None

    legs: list[Leg] = []
    net_credit = 0.0
    width_used = 0.0
    strategy_type = ""

    if candidate.trend == "neutral":
        put_result = _credit_spread(candidate.chain, candidate.symbol, expiration, "put", "lower")
        call_result = _credit_spread(candidate.chain, candidate.symbol, expiration, "call", "higher")
        if not put_result or not call_result:
            return None
        (short_put, long_put, put_credit, put_width) = put_result
        (short_call, long_call, call_credit, call_width) = call_result
        legs = [
            Leg(short_put[0], "sell"), Leg(long_put[0], "buy"),
            Leg(short_call[0], "sell"), Leg(long_call[0], "buy"),
        ]
        net_credit = put_credit + call_credit
        width_used = max(put_width, call_width)  # max loss on an iron condor is bounded by the wider side
        strategy_type = "iron_condor"

    elif candidate.trend == "bullish":
        result = _credit_spread(candidate.chain, candidate.symbol, expiration, "put", "lower")
        if not result:
            return None
        short_put, long_put, credit, width = result
        legs = [Leg(short_put[0], "sell"), Leg(long_put[0], "buy")]
        net_credit, width_used = credit, width
        strategy_type = "bull_put_spread"

    elif candidate.trend == "bearish":
        result = _credit_spread(candidate.chain, candidate.symbol, expiration, "call", "higher")
        if not result:
            return None
        short_call, long_call, credit, width = result
        legs = [Leg(short_call[0], "sell"), Leg(long_call[0], "buy")]
        net_credit, width_used = credit, width
        strategy_type = "bear_call_spread"
    else:
        return None

    if net_credit <= 0:
        return None  # never pay a debit for a "premium selling" strategy in this playbook

    max_loss = (width_used - net_credit) * 100  # per contract, x100 multiplier
    if max_loss <= 0:
        return None

    return StrategyPlan(
        strategy_type=strategy_type,
        underlying=candidate.symbol,
        expiration=expiration,
        legs=legs,
        net_credit_estimate=net_credit,
        max_loss_estimate=max_loss,
        rationale=(
            f"{candidate.symbol}: IV rank {candidate.iv_rank:.0f}, trend={candidate.trend} -> {strategy_type}, "
            f"credit~${net_credit:.2f}, max_loss~${max_loss:.2f}, exp {expiration}"
        ),
    )
