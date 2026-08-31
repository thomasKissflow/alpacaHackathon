"""
Risk Gate: pure, deterministic Python -- zero LLM in this module. Every
MarketPlan, every specialist quote, and every Convexity Mode spread must
pass through here before anything reaches the market. Every rejection or
clamp is written to the ledger's risk_events table with a human-readable
reason -- that log is some of the best material for the submission write-up
and the "risk gate actually firing" dashboard panel.

Three surfaces, all deterministic:
  1. validate_market_plan()      -- clamps the LLM's proposed MarketPlan
  2. pretrade_gate_specialist()  -- per-quote delta/vega/gamma/notional check
  3. evaluate_convexity_plan()   -- per-trade income-strategy checks (existing)
Plus account-level: circuit_breaker_tripped(), kill_switch_engaged().
"""
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from agent import ledger
from agent.config import DAY_START_EQUITY, KILL_SWITCH_FLAG, RISK
from agent.strategy import StrategyPlan


@dataclass
class RiskDecision:
    approved: bool
    reasons: list[str]


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


# ============================================================ account-level

def get_or_init_day_start_equity(current_equity: float) -> float:
    state = {}
    if DAY_START_EQUITY.exists():
        state = json.loads(DAY_START_EQUITY.read_text())
    today = _today()
    if state.get("date") != today:
        state = {"date": today, "equity": current_equity}
        DAY_START_EQUITY.parent.mkdir(parents=True, exist_ok=True)
        DAY_START_EQUITY.write_text(json.dumps(state))
    return state["equity"]


def circuit_breaker_tripped(current_equity: float) -> tuple[bool, float]:
    day_start = get_or_init_day_start_equity(current_equity)
    if day_start <= 0:
        return False, 0.0
    drawdown_pct = (day_start - current_equity) / day_start
    tripped = drawdown_pct >= RISK.daily_loss_circuit_breaker_pct
    if tripped:
        ledger.log_risk_event(
            "circuit_breaker",
            f"daily equity drawdown {drawdown_pct:.2%} >= limit {RISK.daily_loss_circuit_breaker_pct:.2%}; "
            f"halting new order placement for the session (hedges of existing inventory still allowed)",
            details={"day_start_equity": day_start, "current_equity": current_equity, "drawdown_pct": drawdown_pct},
        )
    return tripped, drawdown_pct


def kill_switch_engaged() -> bool:
    return KILL_SWITCH_FLAG.exists()


# =========================================================== market plan ===

_ALLOWED_SYMBOLS = set(RISK.specialist_symbols) | set(RISK.candidate_underlyings)
_MIN_SPREAD_BPS, _MAX_SPREAD_BPS = 10.0, 250.0


def _fallback_market_plan() -> dict:
    return {
        "symbols": list(RISK.specialist_symbols),
        "target_spread_bps": {s: RISK.target_spread_bps for s in RISK.specialist_symbols},
        "mode_weights": {"specialist": 0.6, "convexity": 0.4},
        "rationale": "fallback: static defaults (no valid LLM plan available this cycle)",
    }


def validate_market_plan(proposed: dict, source: str) -> dict:
    """Validates/clamps an LLM-proposed MarketPlan into one the execution core
    may act on. Always returns a safe, well-formed plan -- never raises.
    Logs the before/after to the ledger's market_plans table."""
    clamped = False
    reasons = []

    symbols = proposed.get("symbols") if isinstance(proposed, dict) else None
    if not isinstance(symbols, list) or not symbols:
        symbols, clamped = list(RISK.specialist_symbols), True
        reasons.append("no valid symbols list proposed, used default basket")
    else:
        filtered = [s for s in symbols if s in _ALLOWED_SYMBOLS]
        if filtered != symbols:
            clamped = True
            reasons.append(f"dropped symbols outside the approved basket: {set(symbols) - set(filtered)}")
        symbols = filtered or list(RISK.specialist_symbols)

    raw_spreads = proposed.get("target_spread_bps") if isinstance(proposed, dict) else None
    spreads = {}
    for s in symbols:
        val = raw_spreads.get(s) if isinstance(raw_spreads, dict) else None
        if not isinstance(val, (int, float)):
            val = RISK.target_spread_bps
        clamped_val = max(_MIN_SPREAD_BPS, min(_MAX_SPREAD_BPS, float(val)))
        if clamped_val != val:
            clamped = True
            reasons.append(f"{s}: spread {val}bps clamped to [{_MIN_SPREAD_BPS},{_MAX_SPREAD_BPS}] -> {clamped_val}")
        spreads[s] = clamped_val

    raw_weights = proposed.get("mode_weights") if isinstance(proposed, dict) else None
    specialist_w = raw_weights.get("specialist") if isinstance(raw_weights, dict) else None
    convexity_w = raw_weights.get("convexity") if isinstance(raw_weights, dict) else None
    if not isinstance(specialist_w, (int, float)) or not isinstance(convexity_w, (int, float)):
        specialist_w, convexity_w, clamped = 0.6, 0.4, True
        reasons.append("no valid mode_weights proposed, used default 0.6/0.4 split")
    else:
        specialist_w, convexity_w = max(0.0, specialist_w), max(0.0, convexity_w)
        total = specialist_w + convexity_w
        if total <= 0:
            specialist_w, convexity_w, clamped = 0.6, 0.4, True
            reasons.append("mode_weights summed to 0, used default 0.6/0.4 split")
        elif abs(total - 1.0) > 1e-6:
            specialist_w, convexity_w = specialist_w / total, convexity_w / total
            clamped = True
            reasons.append(f"mode_weights renormalized to sum to 1 (were {specialist_w:.2f}+{convexity_w:.2f}!=1)")

    approved = {
        "symbols": symbols,
        "target_spread_bps": spreads,
        "mode_weights": {"specialist": round(specialist_w, 3), "convexity": round(convexity_w, 3)},
        "rationale": proposed.get("rationale", "") if isinstance(proposed, dict) else "",
    }

    if clamped:
        for r in reasons:
            ledger.log_risk_event("clamp", r, mode="market_plan", details={"proposed": proposed})
    ledger.log_market_plan(proposed if isinstance(proposed, dict) else {}, approved, source=source, was_clamped=clamped)
    return approved


# ====================================================== specialist mode ====

@dataclass
class QuoteApproval:
    approved_qty: int
    reasons: list[str]


def pretrade_gate_specialist(
    symbol: str,
    underlying: str,
    side: str,                 # 'buy' | 'sell' -- the side of the NEW resting order being placed
    requested_qty: int,
    equity: float,
    underlying_price: float,
    option_notional_per_contract: float,   # theoretical price * 100
    current_underlying_notional: float,    # sum of abs notional already resting/held for this underlying
    portfolio_delta_dollars: float,
    portfolio_vega_dollars: float,
    portfolio_gamma_shares_per_dollar: float,
    incremental_greeks: dict,              # position_dollar_greeks() for ONE contract, signed by side
) -> QuoteApproval:
    """Clamps requested_qty down (possibly to 0) so that none of the hard
    caps in RiskConfig would be breached if the order fully fills. Never
    raises; every clamp/reject is logged with its reason."""
    reasons = []
    qty = max(0, int(requested_qty))

    max_notional = equity * RISK.max_notional_pct_per_underlying
    room_notional = max_notional - current_underlying_notional
    if room_notional <= 0:
        reasons.append(
            f"{symbol}: {underlying} notional cap reached (${current_underlying_notional:,.0f} >= "
            f"${max_notional:,.0f} = {RISK.max_notional_pct_per_underlying:.0%} of equity)"
        )
        qty = 0
    else:
        max_by_notional = int(room_notional // max(option_notional_per_contract, 1e-6))
        if max_by_notional < qty:
            reasons.append(f"{symbol}: clamped qty {qty}->{max_by_notional} by per-underlying notional cap")
            qty = max_by_notional

    def _max_units_within_cap(n_requested: int, cap: float, current: float, per_unit: float) -> int:
        """Largest n in [0, n_requested] such that |current + n*per_unit| <= cap.
        Brute-forced over a tiny range (quote sizes are single-digit contracts)
        rather than solved algebraically, so it stays correct regardless of
        whether adding units moves the aggregate toward or away from zero."""
        if per_unit == 0:
            return n_requested
        for n in range(n_requested, -1, -1):
            if abs(current + n * per_unit) <= cap:
                return n
        return 0

    if qty > 0:
        max_by_delta = _max_units_within_cap(qty, RISK.max_net_delta_dollars, portfolio_delta_dollars,
                                              incremental_greeks["delta_dollars"])
        max_by_vega = _max_units_within_cap(qty, RISK.max_net_vega_dollars, portfolio_vega_dollars,
                                             incremental_greeks["vega_dollars"])
        max_by_gamma = _max_units_within_cap(qty, RISK.max_net_gamma_shares_per_dollar, portfolio_gamma_shares_per_dollar,
                                              incremental_greeks["gamma_shares_per_dollar"])
        capped = min(qty, max_by_delta, max_by_vega, max_by_gamma)
        if capped < qty:
            reasons.append(
                f"{symbol}: clamped qty {qty}->{max(capped,0)} by Greeks caps "
                f"(delta room={max_by_delta}, vega room={max_by_vega}, gamma room={max_by_gamma})"
            )
        qty = max(capped, 0)

    if qty < requested_qty:
        ledger.log_risk_event(
            "clamp" if qty > 0 else "reject",
            "; ".join(reasons) if reasons else f"{symbol}: quote size clamped",
            mode="specialist",
            details={"symbol": symbol, "side": side, "requested_qty": requested_qty, "approved_qty": qty},
        )

    return QuoteApproval(approved_qty=qty, reasons=reasons)


def flatten_required(portfolio_delta_dollars: float) -> bool:
    """True if net portfolio delta is already outside the cap -- the hedger
    must flatten toward zero before any *new* quoting is allowed."""
    breached = abs(portfolio_delta_dollars) > RISK.max_net_delta_dollars
    if breached:
        ledger.log_risk_event(
            "reject",
            f"portfolio delta-dollars ${portfolio_delta_dollars:,.0f} exceeds cap "
            f"+/-${RISK.max_net_delta_dollars:,.0f}; forcing hedge-to-flat before new quotes",
            mode="specialist",
            details={"portfolio_delta_dollars": portfolio_delta_dollars},
        )
    return breached


# ======================================================= convexity mode ====

def evaluate_convexity_plan(plan: StrategyPlan, account: dict, open_strategies: list[dict]) -> RiskDecision:
    reasons = []
    equity = float(account.get("equity", 0))
    buying_power = float(account.get("buying_power", 0))

    tripped, drawdown_pct = circuit_breaker_tripped(equity)
    if tripped:
        reasons.append(f"daily circuit breaker tripped: equity down {drawdown_pct:.1%} today")

    if kill_switch_engaged():
        reasons.append("kill switch is engaged: no new order placement")

    if len(open_strategies) >= RISK.max_concurrent_positions:
        reasons.append(f"max concurrent positions reached ({RISK.max_concurrent_positions})")

    same_underlying = [s for s in open_strategies if s.get("underlying") == plan.underlying]
    if len(same_underlying) >= RISK.max_underlying_concentration:
        reasons.append(f"already have an open position on {plan.underlying}")

    # structural per-trade cap: verticals/condors are naturally defined-risk,
    # so this check also doubles as the "options trading" requirement being
    # airtight -- max loss is bounded by the spread's own construction, we're
    # just also enforcing it stays within the account-level per-trade budget.
    max_allowed_loss = equity * RISK.max_risk_per_trade_pct
    if plan.max_loss_estimate > max_allowed_loss:
        reasons.append(
            f"max loss ${plan.max_loss_estimate:.2f} exceeds per-trade cap "
            f"${max_allowed_loss:.2f} ({RISK.max_risk_per_trade_pct:.0%} of equity)"
        )

    if plan.max_loss_estimate > buying_power:
        reasons.append(f"insufficient buying power (${buying_power:.2f}) for max loss ${plan.max_loss_estimate:.2f}")

    decision = RiskDecision(approved=len(reasons) == 0, reasons=reasons)
    if not decision.approved:
        ledger.log_risk_event(
            "reject", "; ".join(reasons), mode="convexity",
            details={"underlying": plan.underlying, "strategy_type": plan.strategy_type,
                      "max_loss_estimate": plan.max_loss_estimate},
        )
    return decision
