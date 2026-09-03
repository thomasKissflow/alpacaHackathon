# The Specialist — Autonomous Options Market-Making Agent

**Alpaca AI Trading Agents Hackathon · lablab.ai × Alpaca · September 2026**
**Alpaca paper account:** `PA318JJN6DXK`
**Repo:** https://github.com/thomasKissflow/alpacaHackathon · **Live dashboard:** https://thomaskissflow.github.io/alpacaHackathon/dashboard/

---

## What it does

Most trading agents predict direction: *will SPY go up?* The Specialist doesn't predict anything. It runs an **options market-making book** — the business of quoting a price to buy and a price to sell, and earning the spread between them — and neutralises the resulting directional risk by hedging with the underlying stock within the same cycle.

It runs two independent strategies through one shared risk core and one shared ledger:

**Specialist Mode** quotes out-of-the-money puts (7–35 DTE) on SPY, QQQ, AAPL, NVDA and TSLA. It posts one live price per contract per cycle, chosen to move inventory back toward flat — sell when long, buy when short. Every fill is immediately delta-hedged by rebalancing that underlying's equity position to the book's current total target delta. The edge is the captured bid/ask spread, not a market view.

**Convexity Mode** sells defined-risk credit verticals and iron condors (18-delta short strikes, $5 wide) on SPY/QQQ/IWM, filtered by IV rank and trend. It exists so the account keeps generating real trading activity in a week when passive quotes go unfilled.

An LLM layer (Featherless, `Qwen2.5-72B-Instruct`) proposes which symbols to quote and how wide, and writes a daily post-mortem. **It has no execution authority.** Every number it proposes passes through a deterministic clamp before it reaches an order.

---

## AI logic

The division of labour is deliberate and is the core design decision:

| The LLM decides | Deterministic code decides |
|---|---|
| Which symbols to focus on this cycle | Which strikes and expiries qualify |
| How wide to quote (target spread, bps) | Actual quote prices, clamped inside the live NBBO |
| Relative weight of the two modes | Position size |
| Daily post-mortem and rationale text | Whether an order is placed at all |

An LLM that can size a position can end the account on one bad sample. A veto-and-advise LLM can only ever make the system *more* conservative. Every proposal is logged alongside the approved version and a `was_clamped` flag, so the ledger records not just what the model said but what the machine let through.

The model also cannot argue past a risk rule: the scheduled-event posture (below) is applied **after** the plan is approved.

---

## Risk gates

Every gate is deterministic, evaluated before each order, and written to the ledger whether it passes or fails.

1. **Portfolio Greeks caps** — hard limits on aggregate net delta, vega and gamma. Order size is clamped to the largest quantity that keeps the book inside all three, not rejected outright.
2. **Per-underlying notional cap** — no more than 5% of equity of option exposure in any one name.
3. **Defined risk only** — Convexity Mode trades spreads, never naked premium. Max loss per trade is capped at 2% of equity and known at entry.
4. **Immediate delta hedging** — each underlying's equity hedge is rebalanced every cycle to its current *total* target delta, recomputed from positions actually held rather than tracked incrementally. Observed net book delta has run **under $200 against a $25,000 cap**.
5. **Naked-leg reconciliation** — Alpaca's paper environment fills multi-leg orders partially ~10% of the time at random. A half-filled vertical is a *naked short option with unbounded loss*. Before anything else each cycle, the agent reconciles broker state against the ledger and flattens any spread missing a leg.
6. **Daily drawdown circuit breaker** — new entries halt at a 2% daily loss; closing and hedging continue.
7. **Kill switch** — `data/KILL_SWITCH` halts all new risk immediately.
8. **Scheduled-event rule** — see below.
9. **Liquidity and DTE filters** — non-zero two-sided quotes and 7–45 DTE, which also guarantees Alpaca can compute Greeks (0DTE contracts have none — days-to-expiry sits in the Black-Scholes denominator).

### The NFP rule

Every other input this agent uses is reactive — prices and Greeks that have already moved. A scheduled macro release is the one thing it can know *in advance*, and the largest of the month landed inside the competition window: **Non-Farm Payrolls, Friday 4 September, 08:30 ET** — one hour before the final session opened.

The agent carries an event calendar and changes posture around it:

- **T−20h → T−45m — de-risk.** Quotes widen 1.6×, size reduced, and **no new short premium is opened** that would be held across the release.
- **T−45m → T+75m — blackout.** Places nothing. Covers the print and the first fifteen minutes of the open.
- **T+75m → T+5h — re-engage.** Quotes tighten to 0.85×, full size. Once the number is known the uncertainty premium collapses, so market-making is *safer* after the event, not riskier.

Existing positions are monitored, hedged and closed in every phase; the rule only gates opening new risk. This is not a bet on payrolls — the agent has no opinion on the number, only on the fact that uncertainty is scheduled, priced, and then resolved.

---

## Alpaca infrastructure

- **Alpaca CLI** drives the unattended loop's account telemetry (`alpaca account get`, positions, orders). Alpaca built the CLI for "AI agents, scripts, and automation pipelines" and it is the right tool for a scheduled agent — JSON-first, `--client-order-id` idempotency, `--dry-run` preflight.
- **Trading API** via `alpaca-py` for typed multi-leg construction (`OptionLegRequest`, `OrderClass.MLEG`) — the most reliable way to build a spread correctly.
- **Options Market Data API** for chains, snapshots, Greeks and IV. The system runs entirely on the **free indicative feed**: ~10,000 of 12,500 SPY contracts return usable Greeks, and the strategy is deliberately latency-insensitive so a 15-minute data restriction and a ±30-minute scheduler drift are both tolerable by design.
- **Alpaca MCP Server** as the research and operator surface — interrogating the live book in natural language during development, deliberately kept out of the order path where an LLM would add latency and non-determinism.
- **Paper trading**, multi-leg Level 3, enabled by default.

**Two platform constraints found by running it live, not by reading docs:** Alpaca rejects naked short calls (`account not eligible to trade uncovered option contracts`), so the agent quotes puts only, with call-side exposure covered structurally by Convexity Mode's spreads. And wash-trade protection rejects a simultaneous resting bid and ask on the same contract, so the agent quotes one side per contract per cycle — whichever moves inventory toward flat.

---

## Architecture

No server and no database. The agent is a scheduled process; state is one append-only SQLite ledger with real foreign keys (fills reference orders, hedges reference the fill that triggered them); the dashboard is a static page reading an exported JSON snapshot, holding no credentials. Reconstructing *why the book looked like this at time T* is a join, not a guess.

Every cycle reconciles broker state before acting — it never assumes the previous run succeeded — so a dropped or delayed run is a non-event.

**39 → 48 unit tests**, zero live API calls in the suite. Several exist because live running broke the code first: a rounding bug that collapsed a $7.278/$7.282 quote into a wash trade, a reconciliation gap that left a fill unhedged when its contract fell out of selection, a hedge-orphaning bug on position close, and a day-P&L baseline that survived an account switch and misreported P&L by $276.

---

## Honest notes

- Paper fills are optimistic: Alpaca does not model slippage, market impact, queue position or finite liquidity. Live market-making results would be worse, and the spread capture reported here is an upper bound.
- Per-mode P&L attribution is an approximation — whatever today's equity change Convexity's realised P&L doesn't explain is attributed to Specialist Mode. A true per-mode subledger would need separate mark-to-market accounting.
- The competition window was ~4 trading sessions. That is far too short for any options strategy to demonstrate statistical significance, and we have not claimed otherwise. What the account shows is a *process* running unattended and behaving as specified.
