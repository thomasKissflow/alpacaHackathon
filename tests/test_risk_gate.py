from datetime import date

from agent import risk_gate
from agent.config import RISK
from agent.pricing import position_dollar_greeks, price_and_greeks
from agent.strategy import Leg, StrategyPlan


def _make_convexity_plan(max_loss_estimate=100.0, underlying="SPY") -> StrategyPlan:
    return StrategyPlan(
        strategy_type="iron_condor",
        underlying=underlying,
        expiration=date(2026, 10, 16),
        legs=[Leg("SPY261016P00440000", "sell"), Leg("SPY261016P00435000", "buy")],
        net_credit_estimate=1.50,
        max_loss_estimate=max_loss_estimate,
        rationale="test plan",
    )


# ======================================================= circuit breaker ===

def test_circuit_breaker_not_tripped_on_small_drawdown(tmp_path, monkeypatch):
    monkeypatch.setattr(risk_gate, "DAY_START_EQUITY", tmp_path / "day_start.json")
    risk_gate.get_or_init_day_start_equity(100_000)
    tripped, drawdown = risk_gate.circuit_breaker_tripped(99_500)  # 0.5% down
    assert tripped is False
    assert drawdown < RISK.daily_loss_circuit_breaker_pct


def test_circuit_breaker_trips_on_large_drawdown(tmp_path, monkeypatch):
    monkeypatch.setattr(risk_gate, "DAY_START_EQUITY", tmp_path / "day_start.json")
    risk_gate.get_or_init_day_start_equity(100_000)
    daily_loss_dollars = 100_000 * (RISK.daily_loss_circuit_breaker_pct + 0.01)
    tripped, drawdown = risk_gate.circuit_breaker_tripped(100_000 - daily_loss_dollars)
    assert tripped is True
    assert drawdown >= RISK.daily_loss_circuit_breaker_pct


# ============================================================ kill switch ==

def test_kill_switch_default_clear(tmp_path, monkeypatch):
    monkeypatch.setattr(risk_gate, "KILL_SWITCH_FLAG", tmp_path / "KILL_SWITCH")
    assert risk_gate.kill_switch_engaged() is False


def test_kill_switch_engaged_when_flag_file_present(tmp_path, monkeypatch):
    flag = tmp_path / "KILL_SWITCH"
    monkeypatch.setattr(risk_gate, "KILL_SWITCH_FLAG", flag)
    flag.write_text("engaged for test")
    assert risk_gate.kill_switch_engaged() is True


def test_convexity_plan_rejected_when_kill_switch_engaged(tmp_path, monkeypatch):
    monkeypatch.setattr(risk_gate, "KILL_SWITCH_FLAG", tmp_path / "KILL_SWITCH")
    monkeypatch.setattr(risk_gate, "DAY_START_EQUITY", tmp_path / "day_start.json")
    (tmp_path / "KILL_SWITCH").write_text("engaged")
    plan = _make_convexity_plan()
    account = {"equity": "100000", "buying_power": "50000"}
    decision = risk_gate.evaluate_convexity_plan(plan, account, open_strategies=[])
    assert decision.approved is False
    assert any("kill switch" in r for r in decision.reasons)


# ======================================================= convexity mode ====

def test_convexity_plan_rejected_when_max_loss_exceeds_per_trade_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(risk_gate, "KILL_SWITCH_FLAG", tmp_path / "KILL_SWITCH")
    monkeypatch.setattr(risk_gate, "DAY_START_EQUITY", tmp_path / "day_start.json")
    account = {"equity": "100000", "buying_power": "50000"}
    too_large = 100_000 * RISK.max_risk_per_trade_pct + 500
    plan = _make_convexity_plan(max_loss_estimate=too_large)
    decision = risk_gate.evaluate_convexity_plan(plan, account, open_strategies=[])
    assert decision.approved is False
    assert any("max loss" in r for r in decision.reasons)


def test_convexity_plan_approved_within_all_caps(tmp_path, monkeypatch):
    monkeypatch.setattr(risk_gate, "KILL_SWITCH_FLAG", tmp_path / "KILL_SWITCH")
    monkeypatch.setattr(risk_gate, "DAY_START_EQUITY", tmp_path / "day_start.json")
    account = {"equity": "100000", "buying_power": "50000"}
    plan = _make_convexity_plan(max_loss_estimate=100.0)
    decision = risk_gate.evaluate_convexity_plan(plan, account, open_strategies=[])
    assert decision.approved is True
    assert decision.reasons == []


def test_convexity_plan_rejected_at_max_concurrent_positions(tmp_path, monkeypatch):
    monkeypatch.setattr(risk_gate, "KILL_SWITCH_FLAG", tmp_path / "KILL_SWITCH")
    monkeypatch.setattr(risk_gate, "DAY_START_EQUITY", tmp_path / "day_start.json")
    account = {"equity": "100000", "buying_power": "50000"}
    plan = _make_convexity_plan()
    open_strategies = [{"underlying": "QQQ"}] * RISK.max_concurrent_positions
    decision = risk_gate.evaluate_convexity_plan(plan, account, open_strategies)
    assert decision.approved is False
    assert any("max concurrent" in r for r in decision.reasons)


# ============================================================ market plan ==

def test_validate_market_plan_uses_fallback_on_garbage_input(tmp_path, monkeypatch):
    monkeypatch.setattr(risk_gate, "KILL_SWITCH_FLAG", tmp_path / "KILL_SWITCH")
    approved = risk_gate.validate_market_plan({}, source="fallback")
    assert set(approved["symbols"]) <= set(RISK.specialist_symbols) | set(RISK.candidate_underlyings)
    assert abs(sum(approved["mode_weights"].values()) - 1.0) < 1e-6


def test_validate_market_plan_clamps_spread_bps_out_of_range():
    proposed = {
        "symbols": ["SPY"],
        "target_spread_bps": {"SPY": 5000},  # way outside [10, 250]
        "mode_weights": {"specialist": 0.5, "convexity": 0.5},
    }
    approved = risk_gate.validate_market_plan(proposed, source="llm")
    assert approved["target_spread_bps"]["SPY"] <= 250.0


def test_validate_market_plan_drops_disallowed_symbols():
    proposed = {
        "symbols": ["SPY", "GME"],  # GME not in either allowed basket
        "target_spread_bps": {"SPY": 40},
        "mode_weights": {"specialist": 0.5, "convexity": 0.5},
    }
    approved = risk_gate.validate_market_plan(proposed, source="llm")
    assert "GME" not in approved["symbols"]
    assert "SPY" in approved["symbols"]


def test_validate_market_plan_renormalizes_mode_weights():
    proposed = {
        "symbols": ["SPY"],
        "target_spread_bps": {"SPY": 40},
        "mode_weights": {"specialist": 3, "convexity": 1},  # doesn't sum to 1
    }
    approved = risk_gate.validate_market_plan(proposed, source="llm")
    assert abs(sum(approved["mode_weights"].values()) - 1.0) < 1e-6
    assert approved["mode_weights"]["specialist"] > approved["mode_weights"]["convexity"]


# ======================================================== specialist mode ==

def _one_contract_greeks():
    return price_and_greeks(S=450, K=450, T=21 / 365, r=0.045, sigma=0.20, option_type="call")


def test_pretrade_gate_approves_small_order_within_all_caps():
    greeks = _one_contract_greeks()
    incremental = position_dollar_greeks(greeks, qty=-1, underlying_price=450)  # selling 1 contract
    approval = risk_gate.pretrade_gate_specialist(
        symbol="SPY261016C00450000", underlying="SPY", side="sell", requested_qty=1,
        equity=100_000, underlying_price=450, option_notional_per_contract=greeks.price * 100,
        current_underlying_notional=0, portfolio_delta_dollars=0, portfolio_vega_dollars=0,
        portfolio_gamma_shares_per_dollar=0, incremental_greeks=incremental,
    )
    assert approval.approved_qty == 1


def test_pretrade_gate_clamps_to_zero_when_notional_cap_already_full():
    greeks = _one_contract_greeks()
    incremental = position_dollar_greeks(greeks, qty=-1, underlying_price=450)
    equity = 100_000
    max_notional = equity * RISK.max_notional_pct_per_underlying
    approval = risk_gate.pretrade_gate_specialist(
        symbol="SPY261016C00450000", underlying="SPY", side="sell", requested_qty=1,
        equity=equity, underlying_price=450, option_notional_per_contract=greeks.price * 100,
        current_underlying_notional=max_notional,  # already at the cap
        portfolio_delta_dollars=0, portfolio_vega_dollars=0, portfolio_gamma_shares_per_dollar=0,
        incremental_greeks=incremental,
    )
    assert approval.approved_qty == 0
    assert any("notional cap" in r for r in approval.reasons)


def test_pretrade_gate_clamps_by_delta_cap():
    greeks = _one_contract_greeks()
    incremental = position_dollar_greeks(greeks, qty=1, underlying_price=450)  # buying -> positive delta added
    # portfolio is already almost at the positive delta cap
    near_cap = RISK.max_net_delta_dollars - (incremental["delta_dollars"] * 0.5)
    approval = risk_gate.pretrade_gate_specialist(
        symbol="SPY261016C00450000", underlying="SPY", side="buy", requested_qty=5,
        equity=100_000, underlying_price=450, option_notional_per_contract=greeks.price * 100,
        current_underlying_notional=0, portfolio_delta_dollars=near_cap, portfolio_vega_dollars=0,
        portfolio_gamma_shares_per_dollar=0, incremental_greeks=incremental,
    )
    assert approval.approved_qty < 5
    assert any("Greeks caps" in r for r in approval.reasons)


def test_flatten_required_true_when_over_cap():
    assert risk_gate.flatten_required(RISK.max_net_delta_dollars + 1) is True


def test_flatten_required_false_when_within_cap():
    assert risk_gate.flatten_required(RISK.max_net_delta_dollars * 0.5) is False


def test_day_start_equity_rebaselines_on_account_switch(tmp_path, monkeypatch):
    """Regression: the baseline was keyed by date alone, so swapping to a
    different Alpaca account mid-session kept the previous account's equity as
    the day-start. Live on 2026-09-03 that reported +$248 day P&L while the
    fresh $100k account was actually down $28."""
    import json
    from agent import risk_gate

    state_file = tmp_path / "day_start_equity.json"
    monkeypatch.setattr(risk_gate, "DAY_START_EQUITY", state_file)

    # dev account establishes a baseline
    assert risk_gate.get_or_init_day_start_equity(99_723.83, "PA_DEV") == 99_723.83

    # same day, DIFFERENT account -> must re-baseline, not reuse 99,723.83
    assert risk_gate.get_or_init_day_start_equity(100_000.00, "PA_COMP") == 100_000.00
    assert json.loads(state_file.read_text())["account_id"] == "PA_COMP"

    # same day, same account -> baseline is sticky as intended
    assert risk_gate.get_or_init_day_start_equity(99_971.60, "PA_COMP") == 100_000.00
