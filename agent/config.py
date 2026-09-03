"""
Central config + risk-gate parameters. Tune these before the competition run --
they ARE the "risk gates" the submission write-up needs to describe.
"""
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"

ALPACA_API_KEY = os.environ.get("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY", "")
PAPER = os.environ.get("ALPACA_PAPER_TRADE", "true").lower() == "true"
ALPACA_PAPER_ACCOUNT_ID = os.environ.get("ALPACA_PAPER_ACCOUNT_ID", "")

# --- LLM agent layer: provider-abstracted. Anthropic (Claude) is preferred
# if ANTHROPIC_API_KEY is set (matches the brief's "Claude via MCP server"
# framing); otherwise falls back to Featherless's OpenAI-compatible endpoint.
# Order placement never goes through this path -- see llm_agent.py.
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")

FEATHERLESS_API_KEY = os.environ.get("FEATHERLESS_API_KEY", "")
FEATHERLESS_BASE_URL = os.environ.get("FEATHERLESS_BASE_URL", "https://api.featherless.ai/v1")
FEATHERLESS_MODEL = os.environ.get("FEATHERLESS_MODEL", "Qwen/Qwen2.5-72B-Instruct")

# NOTE: os.environ.get(key, default) returns "" when the key EXISTS but is
# empty -- the default is only used when the key is ABSENT. .env.example ships
# with a bare `LLM_PROVIDER=` line, so every .env copied from it set the
# provider to "" and silently disabled the entire LLM layer: every MarketPlan
# logged source='fallback' and every postmortem read "[LLM call failed]".
# Found live 2026-09-04. Treat empty/whitespace as unset.
LLM_PROVIDER = (os.environ.get("LLM_PROVIDER") or "").strip() or (
    "anthropic" if ANTHROPIC_API_KEY else ("featherless" if FEATHERLESS_API_KEY else "none")
)

RISK_FREE_RATE = float(os.environ.get("RISK_FREE_RATE", "0.045"))

KILL_SWITCH_FLAG = DATA_DIR / "KILL_SWITCH"


@dataclass
class RiskConfig:
    # =================================================================
    # Specialist Mode (market making) hard limits
    # =================================================================
    # Gold ETFs added alongside the equity names (D-015). Gold is genuinely
    # uncorrelated with the equity indices, so it diversifies the book rather
    # than concentrating it -- and IAU's small contract size (~$3.8k of delta
    # per ATM put vs SPY's ~$34.8k) fits comfortably inside the Greeks caps.
    specialist_symbols: tuple = ("SPY", "QQQ", "AAPL", "NVDA", "TSLA", "GLD", "IAU")
    target_spread_bps: float = 40.0            # target quoted width, in bps of theoretical mid
    min_quote_size: int = 1                    # contracts per side
    max_quote_size: int = 3                    # contracts per side
    quote_dte_min: int = 7
    quote_dte_max: int = 35
    quote_moneyness_band_pct: float = 0.03     # only quote strikes within +/-3% of underlying spot
    requote_underlying_move_bps: float = 15.0  # replace quotes if underlying moved this much since last quote

    # notional / concentration
    max_notional_pct_per_underlying: float = 0.05   # <= 5% of equity in options exposure, per symbol

    # Greeks caps (dollar Greeks; see agent/pricing.py docstring for convention).
    # The build brief's own example ("e.g. +/-$2,000 delta-dollars") doesn't
    # survive contact with real contract economics: one single ATM contract
    # on a ~$450 underlying is already ~$24,000 of delta-dollar exposure
    # (delta ~0.53 * 100 multiplier * $450), so a literal $2,000 cap would
    # make Specialist Mode unable to ever post a single quote. Recalibrated
    # against the actual basket (SPY/QQQ/AAPL/NVDA/TSLA) so the cap is a real
    # backstop against a hedge failure or multiple simultaneous fills, not a
    # tripwire on the very first fill -- worth calling out in the write-up as
    # a deliberate deviation, not an oversight.
    # Raised 25k -> 60k (D-015). At SPY $773 a single ATM put carries ~$34.8k
    # of delta, so a $25k cap made the two most liquid underlyings impossible
    # to quote: 41 of 86 risk events were "clamped 1->0 (delta room=0)".
    # This is not a loosening of real risk -- Specialist Mode delta-hedges
    # every fill in the same cycle, and observed POST-hedge net book delta ran
    # under $200 all session. The cap was blocking entry, not controlling risk.
    max_net_delta_dollars: float = 60_000.0
    max_net_vega_dollars: float = 3_000.0
    max_net_gamma_shares_per_dollar: float = 400.0

    # =================================================================
    # Convexity Mode (fallback vertical/condor selling) limits
    # =================================================================
    max_risk_per_trade_pct: float = 0.02       # max defined loss on any single trade, as % of equity
    max_concurrent_positions: int = 5          # cap on open multi-leg strategies at once
    max_underlying_concentration: int = 1      # max open strategies per underlying symbol

    profit_target_pct_of_credit: float = 0.50  # close at 50% of max profit
    stop_loss_multiple_of_credit: float = 2.0  # close if loss reaches 2x credit received

    min_iv_rank_for_entry: float = 50.0        # only sell premium when IV proxy rank is elevated
    min_days_to_expiration: int = 7
    max_days_to_expiration: int = 45
    target_short_leg_delta: float = 0.18       # ~18-delta short strikes = defined-risk, high-probability
    spread_width_dollars: float = 5.0          # width between short and long strike

    candidate_underlyings: tuple = ("SPY", "QQQ", "IWM", "GLD")

    # =================================================================
    # Account-level (both modes)
    # =================================================================
    daily_loss_circuit_breaker_pct: float = 0.02  # halt NEW entries if equity drops this % from day-start

    # =================================================================
    # Agent orchestration cadence
    # =================================================================
    market_plan_refresh_minutes: int = 45      # how often the LLM MarketPlan step re-runs
    daemon_poll_seconds: int = 30               # quote-maintenance/hedge loop interval


RISK = RiskConfig()

# the ledger (agent/ledger.py) is the source of truth for orders/fills/
# hedges/risk-events/plans/postmortems. These few remain as small JSON side
# files for things that are either narrative (decisions.json) or naturally
# process-local scratch state (day_start_equity.json, iv_history.json).
DECISIONS_LOG = DATA_DIR / "decisions.json"
IV_HISTORY = DATA_DIR / "iv_history.json"
DAY_START_EQUITY = DATA_DIR / "day_start_equity.json"
