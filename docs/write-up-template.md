# The Specialist — One-Page Write-Up

*(Required submission artifact. Fill in the bracketed parts. Keep it to one page.)*

## AI logic

Two execution modes share one risk core, orchestrated by an LLM agent layer
that only ever proposes structured JSON — it never places an order itself.

- **Specialist Mode** (the differentiator): maintains two-sided resting limit
  quotes, priced off Black-Scholes theoretical value with IV solved from each
  contract's own live NBBO mid (Newton-Raphson, from scratch — see
  `agent/pricing.py`), on near-the-money contracts across [SPY/QQQ/AAPL/NVDA/TSLA].
  Quotes are cancelled and reposted every cycle as the underlying/IV move.
  Every fill triggers an immediate offsetting equity order to flatten that
  fill's delta contribution.
- **Convexity Mode** (fallback, keeps the account active): screens the same
  kind of basket for IV rank + SMA20/SMA50 trend, and opens a defined-risk
  vertical spread or iron condor when a signal fires — never a naked/
  undefined-risk leg. Exits are pre-committed: [50]% of max profit, [2]× the
  credit received as a stop, or ≤1 day to expiration.
- **Agent layer** (`agent/llm_agent.py`, [Claude / a Featherless-hosted model]):
  a MarketPlan step every [45] minutes decides which symbols to actively
  quote, target spread width per symbol, and the capital-weight split between
  the two modes. A once-daily post-mortem reads the day's closed trades and
  fills, writes a natural-language debrief, and proposes tomorrow's
  adjustment. Both outputs are **only ever proposals** — `agent/risk_gate.py`
  validates and clamps every field before anything downstream acts on it.

## Risk gates

- Max notional options exposure per underlying: **[5]%** of equity.
- Max net portfolio delta-dollars: **±$[25,000]** (recalibrated from a naive
  ±$2,000 example — that's smaller than one ATM contract's delta exposure on
  a ~$450 name, see `agent/config.py` for the math).
- Max net vega-dollars: **±$[3,000]**; max net gamma: **±[400]** shares/$1 move.
- Daily loss circuit breaker: halts *new* entries (existing inventory still
  hedged/monitored) at **[2]%** intraday equity drawdown.
- Convexity Mode per-trade max loss: **[2]%** of equity, structurally capped
  by the spread's own construction.
- Kill switch (`python -m agent.kill_switch execute`): cancels every resting
  order and flattens every option + equity position immediately.
- Every rejection/clamp is written to the ledger's `risk_events` table with a
  human-readable reason. **Real example from a run:** *[paste one risk_events
  row here, e.g. "AAPL: SPY notional cap reached ($X >= $Y = 5% of equity)"]*.

## Alpaca infrastructure

- **Trading & Market Data API** (`alpaca-py`) for option chain/NBBO/Greeks
  data, resting limit order placement/cancellation for two-sided quoting, and
  typed multi-leg order construction (`OptionLegRequest`, `OrderClass.MLEG`)
  for Convexity Mode spreads.
- **Alpaca CLI** for account/position telemetry inside every scheduled cycle
  — the pattern Alpaca's own docs recommend for cron/CI, satisfying the
  hackathon's CLI-or-MCP requirement.
- **Alpaca MCP server** for interactive strategy development/debugging in
  Claude Code during the build phase (see README).
- A long-running local daemon (`python -m agent.daemon`) drives Specialist
  Mode's quote-maintenance loop far more frequently than GitHub Actions' cron
  reasonably can; the cron job (`agent/run.py`, 3x/day) covers Convexity Mode
  and the LLM layer. **[state where/how the daemon actually ran during
  competition week]**.
- Paper account ID: **[fill in]**, funded at $100,000, created fresh for
  this submission on **[date]**.

## Results

- Starting equity: $100,000. Ending equity: **[$X]**. Net P&L: **[$X / X%]**,
  split **[$X specialist / $X convexity]**.
- Specialist Mode: **[N]** fills, average captured spread **[X bps]**, **[N]**
  hedge trades, average hedge slippage **[X cents/share]**.
- Convexity Mode: **[N]** positions opened, **[N]** closed, win rate **[N]**.
- Circuit breaker engaged **[N]** time(s); kill switch engaged **[N]** time(s)
  (zero is a fine answer — say so either way).
- [1–2 sentences on what worked, what didn't, and what you'd change with
  more time — e.g. specific to market-making, how much of the week Specialist
  Mode actually got filled vs. sat unfilled, and whether cancel-and-replace
  quoting (an MVP simplification vs. a native replace/PATCH) mattered.]
