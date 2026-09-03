# The Specialist — Alpaca AI Trading Agents Hackathon

> lablab.ai × Alpaca · 28 Aug – **4 Sep 2026, 20:30 IST** · $6,300 prize pool · Team of 2

**Status:** 🟢 **Code live.** Concept (D-004) and architecture (D-006) are decided — see [docs/decisions.md](docs/decisions.md) D-011/D-012 for what changed from the original proposal and why. Full history of how we got here (research, brainstorming, the original portfolio-greeks-desk proposal) is preserved in `docs/` and is worth reading — none of it was wasted, it's what this build is reconciled against.

## Start here

| If you want to… | Read |
|---|---|
| **Catch up after a `git pull`** | **[docs/team-handoff.md](docs/team-handoff.md)** ← start here |
| Run the code | This file, below |
| Understand what changed from the original plan and why | [docs/decisions.md](docs/decisions.md) D-011, D-012 |
| Understand the original research (still valid — data tiers, competitor field, NFP timing, paper-fill quirks) | [docs/research.md](docs/research.md) |
| See every idea considered, including rejected ones | [docs/brainstorming.md](docs/brainstorming.md) |
| Set up Alpaca accounts + keys | [docs/setup-guide.md](docs/setup-guide.md) |
| Find something to work on | [docs/tasks.md](docs/tasks.md) |
| Track submission requirements | [docs/submission-checklist.md](docs/submission-checklist.md) |
| Fill in the required one-page write-up | [docs/write-up-template.md](docs/write-up-template.md) |

## The three things that matter most

1. **~4.2 trading sessions** of judged P&L (Mon 31 Aug → Fri 4 Sep 11:00 ET). Getting a simple agent live for Monday's open beats getting a clever one live on Wednesday.
2. **US market hours are 19:00–01:30 IST.** The agent trades while we sleep, so it must be genuinely autonomous, idempotent and self-healing.
3. **NFP lands Fri 4 Sep 08:30 ET**, inside the judging window and 2.5h before the deadline. See `docs/research.md` §5 — the event-awareness rule (T-027) still needs to land before Thursday close regardless of which strategy concept is running.

## Hard requirements

- Autonomous AI trading agent on Alpaca's Trading API
- Must use Alpaca's **MCP server or CLI**
- **All strategies must incorporate options**
- **Brand-new** paper account, **$100,000** starting balance, account ID in the submission
- One-page write-up: AI logic, risk gates, Alpaca infrastructure

---

## What this build actually is

Two execution modes share one risk core, orchestrated by an LLM agent layer
that only ever proposes structured JSON — it never places an order itself.

- **Specialist Mode** (the differentiator — see D-011 for why this replaced
  the originally-proposed VRP portfolio-greeks desk): inventory-driven
  liquidity provision on near-the-money **puts** across SPY/QQQ/AAPL/NVDA/TSLA,
  priced off Black-Scholes theoretical value with IV solved from each
  contract's own live NBBO mid (Newton-Raphson, from scratch —
  `agent/pricing.py`). Two real Alpaca constraints, found by running this
  live against a real paper account rather than assumed, shape the exact
  mechanic — see D-013: naked short calls are rejected (puts only, cash-secured
  and allowed), and a resting buy + resting sell can't be open on the same
  contract at once (quotes one side per contract per cycle, chosen by
  current inventory, not both simultaneously). Every underlying's equity
  hedge is rebalanced to its current target delta every cycle — not hedged
  incrementally per fill — so a position that closes via the book's own
  opposite-side fill correctly unwinds its hedge too.
- **Convexity Mode** (fallback, keeps the account active): screens the same
  kind of basket for IV rank + SMA20/SMA50 trend, and opens a defined-risk
  vertical spread or iron condor when a signal fires — never a naked/
  undefined-risk leg. Exits are pre-committed: 50% of max profit, 2× the
  credit received as a stop, or ≤1 day to expiration.
- **Agent layer** (`agent/llm_agent.py`, Claude or a Featherless-hosted open
  model): a MarketPlan step every ~45 minutes decides which symbols to
  actively quote, target spread width per symbol, and the capital-weight
  split between the two modes. A once-daily post-mortem reads the day's
  closed trades and fills, writes a natural-language debrief, and proposes
  tomorrow's adjustment. Both outputs are **only ever proposals** —
  `agent/risk_gate.py` validates and clamps every field before anything
  downstream acts on it. This matches the team's own D-008 (LLM never has
  execution authority) exactly, just applied to a different strategy.

```
Agent layer (Claude, or a Featherless-hosted open model -- agent/llm_agent.py)
  -> MarketPlan every ~45min: which symbols to quote, spread width, mode weights
  -> Daily post-mortem: debrief + proposed adjustment
  -> NEVER touches order placement -- emits JSON only
        |
        v
Risk Gate (agent/risk_gate.py) -- pure deterministic Python, zero LLM
  -> validates/clamps the MarketPlan
  -> per-quote delta/vega/gamma/notional checks (Specialist Mode)
  -> per-trade checks + circuit breaker + kill switch (both modes)
  -> every rejection/clamp logged to the ledger with a reason
        |
        v
Execution core
  -> Specialist Mode (agent/specialist_mode.py): Black-Scholes/IV pricer
     (agent/pricing.py, from scratch) -> inventory-driven one-sided-at-a-time
     resting put quotes inside NBBO (D-013: Alpaca rejects naked calls and
     simultaneous same-contract buy+sell) -> cancel/repost each cycle ->
     global fill reconciliation -> hedge rebalanced to target delta
  -> Convexity Mode (agent/convexity_mode.py): reconcile actual broker
     positions vs the ledger FIRST (agent/reconcile.py -- catches the
     naked-leg risk from Alpaca's documented ~10% random partial-fill rate
     on paper multi-leg orders, per docs/research.md §1.6) -> IV-rank+trend
     scan (agent/scanner.py) -> vertical/condor plan (agent/strategy.py) ->
     MLEG order (agent/execution.py) -> monitor/close (agent/monitor.py)
  -> both modes write every order/fill/hedge/rejection to one ledger
        |
        v
Ledger (agent/ledger.py, SQLite, append-only) -> dashboard/ (static HTML/JS)
```

Two entry points share one `run_cycle()` (`agent/cycle.py`):

- **`agent/run.py`** — a single cycle, driven by GitHub Actions cron. Fine
  for Convexity Mode and the LLM layer, which only need to act every so often.
- **`agent/daemon.py`** — a long-running loop (`RISK.daemon_poll_seconds`,
  default 30s). Specialist Mode actually needs this: two-sided quoting that
  only reprices every few hours isn't market-making, it's noise. Run this
  somewhere during market hours for real fills (see "Running it for real").

## Setup

### 1. Alpaca accounts + keys

Follow [docs/setup-guide.md](docs/setup-guide.md) — **three accounts, not
one**: a personal sandbox each for dev, and a single brand-new $100k
competition account (never traded on manually) whose keys live only in
GitHub Actions Secrets. That guide's reasoning (D-010, account contamination
risk) applies unchanged to this build.

### 2. LLM agent layer

Set **one** of these in `.env` (see `.env.example`):

- `ANTHROPIC_API_KEY` — Claude.
- `FEATHERLESS_API_KEY` (+ `FEATHERLESS_MODEL`) — Featherless's
  OpenAI-compatible endpoint. Claim the `ALPACA26` credit code per
  `docs/project-overview.md` §11 (T-003, still time-sensitive/first-come).
  Note: several gated models (e.g. `meta-llama/Meta-Llama-3.1-70B-Instruct`)
  return a 403 unless you've connected HuggingFace OAuth for your Featherless
  account; `Qwen/Qwen2.5-72B-Instruct` is ungated and verified working.

Neither is required to run the system — `agent/llm_agent.py` degrades to a
clearly-labeled deterministic fallback (static default MarketPlan, templated
post-mortem) if no provider is configured or a call fails. That fallback
still goes through the same risk gate, so both modes keep trading either way.

### New to options trading or this codebase?

Start with [examples/](examples/) instead of jumping straight into `agent/`
— heavily-commented, standalone scripts that explain and demo the pricer,
the risk gate, and a safe read-only account check, plus how to seed the
dashboard with sample data and how to run the real test suite.

### 3. Local dev environment

```bash
cd alpaca-options-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in ALPACA_API_KEY / ALPACA_SECRET_KEY / an LLM key
```

Install the Alpaca CLI (used for account/position reads each cycle):

```bash
brew install alpacahq/tap/cli
# or: go install github.com/alpacahq/cli/cmd/alpaca@latest
alpaca profile login --api-key   # paper trading
```

Run the test suite (pure logic, no live API calls — safe to run anytime):

```bash
python -m pytest tests/ -v
```

Run one cycle locally to sanity check both modes end-to-end:

```bash
python -m agent.daemon --once
```

### 4. Interactive development with the Alpaca MCP server

For iterating on strategy logic inside Claude Code / Cursor, add Alpaca's
official MCP server (`alpacahq/alpaca-mcp-server`) to your MCP client config
with `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` / `ALPACA_PAPER_TRADE=true` — lets
you ask the assistant to pull option chains, Greeks, and place test orders in
plain English while you're building. The scheduled/daemon runs themselves use
the CLI + SDK, not MCP — same division of labor the team already researched
and decided in D-007 (MCP for research/operator surface, CLI for the
unattended execution loop), just carried over unchanged.

### 5. Running it for real

Two things need to run during the competition week:

1. **`python -m agent.daemon`**, somewhere long-lived during US market hours
   (19:00–01:30 IST) — a laptop left open, or any small always-on VM/Cloud
   Run instance (`docs/research.md` §4 has the options the team already
   evaluated for this). This is what generates real Specialist Mode fills.
   `DAEMON_IGNORE_MARKET_HOURS=true` skips the market-clock check if you
   want to exercise it off-hours.
2. **GitHub Actions** (`.github/workflows/trading-agent.yml`), 3x/day —
   redundant coverage for Convexity Mode + the LLM layer even if the daemon
   isn't running, and what commits `data/*.json` + `data/ledger.db` back to
   the repo for the dashboard (the same "git repo as audit trail" idea from
   the original architecture proposal, D-006 — see D-012). Add repo secrets
   (`ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, and whichever LLM key you're
   using), then trigger a manual run first via the Actions tab
   (`workflow_dispatch`) to confirm it works end to end.

**Kill switch**, if anything looks wrong:

```bash
python -m agent.kill_switch execute   # cancels every resting order, flattens every position
python -m agent.kill_switch status    # check whether it's currently engaged
python -m agent.kill_switch disengage
```

### 6. Dashboard

`agent/dashboard_export.py` regenerates `data/dashboard.json` from the
ledger at the end of every cycle — that's what `dashboard/app.js` fetches, so
there's no backend and no Alpaca keys in the browser.

Enable GitHub Pages (Settings → Pages → Deploy from branch → `/ (root)`),
then visit `https://<you>.github.io/<repo>/dashboard/`. Locally:

```bash
python3 -m http.server 8934
# open http://localhost:8934/dashboard/index.html
```

It shows: equity curve + day/mode-split P&L, live portfolio Greeks vs. risk
gate caps, current Specialist Mode inventory, the quote/fill/hedge activity
feed, Convexity Mode's open and closed positions, the risk-gate event log
(rejections/clamps — judges scoring "technology implementation" respond well
to seeing this actually fire), the daily LLM post-mortem, and MarketPlan
history.

## Tuning the strategy / risk gates

All knobs live in [agent/config.py](agent/config.py) (`RiskConfig`) — the
Specialist Mode basket, target spread width, DTE/moneyness window, Greeks
caps; the Convexity Mode basket, per-trade risk %, profit target/stop loss
multiples; and the account-level circuit breaker. These are also exactly
what the submission write-up needs to describe, so tune deliberately and
note *why* — see `agent/config.py`'s comment on why the Greeks caps were
recalibrated away from an early literal example number.

## Known MVP simplifications (call these out in the write-up, don't hide them)

- **Working-order staleness:** Specialist Mode cancels/reposts every cycle
  (self-correcting by construction). Convexity Mode's entry and exit orders
  are only reconciled once per cycle by `agent/reconcile.py` — on a very
  sparse cron cadence a non-marketable limit could sit for a while before
  the next reconcile catches it. Tighten `STALE_UNFILLED_MINUTES` or run the
  daemon more often if this matters for your cadence.
- **Cancel-and-replace, not PATCH-replace:** Specialist Mode cancels and
  reposts both sides of a quote every cycle rather than using Alpaca's
  partial order-replace endpoint. Correct and simple, at the cost of extra
  order churn — a natural next iteration.
- **Per-mode P&L split is an approximation:** Convexity Mode's realized P&L
  is tracked exactly (closed spread economics); Specialist Mode's is the
  residual of the day's total equity change minus Convexity's realized P&L,
  not a fully separate mark-to-market subledger. Noted in `agent/cycle.py`.
- **IV Rank is self-collected** (Alpaca has no trailing-IV-rank endpoint), so
  Convexity Mode's IV rank filter starts neutral and gets more meaningful as
  runs accumulate over the week.
- **Multi-leg order limit-price sign convention** for net credit vs. debit
  should be double-checked against
  `docs.alpaca.markets/docs/options-level-3-trading` before the first real
  submission run — confirm with a small test order first.
- Convexity Mode opens **one new entry per cycle**, by design, to keep the
  risk story easy to reason about and demo.
- **NFP event rule (T-027) is not yet implemented.** `docs/research.md` §5
  and the team-handoff both flag this as high-severity and unclaimed by any
  competitor — still open, still worth building before Thursday close.
