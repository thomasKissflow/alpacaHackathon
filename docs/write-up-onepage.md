# The Specialist — Autonomous Options Market-Making Agent

**Alpaca paper account:** `PA318JJN6DXK` · **Repo:** github.com/thomasKissflow/alpacaHackathon
**Dashboard:** thomaskissflow.github.io/alpacaHackathon/dashboard/

## What it does

Most trading agents predict direction. The Specialist doesn't predict anything — it **makes a market**. It quotes a price to buy and a price to sell out-of-the-money puts on SPY, QQQ, AAPL, NVDA, TSLA, GLD and IAU, earns the spread between them, and neutralises the resulting directional risk by rebalancing an equity hedge every cycle. Observed net book delta ran under **$200** against a $60,000 cap while holding option positions worth tens of thousands.

A second strategy, **Convexity Mode**, sells defined-risk credit verticals and iron condors (18-delta short strikes, $5 wide) so the account keeps generating trading activity when passive quotes go unfilled. Both share one risk core and one append-only ledger.

## AI logic

An open-weights model on **Featherless** (`Qwen2.5-72B-Instruct`) does two jobs, neither of which touches an order:

- **MarketPlan** — reads the live book (equity, net Greeks vs caps, fill count, news regime) and proposes which symbols to quote and how wide.
- **News Agent** — reads gold-market headlines from Alpaca's news API and classifies an *uncertainty regime* (`calm` / `mixed` / `turbulent`) that scales quote width 0.9×/1.0×/1.35×. It deliberately never emits a direction: a market maker needs to know how nervous to be, not which way to lean. A test asserts the output type carries no directional field.

**The LLM has no execution authority.** It advises on where and how wide; deterministic code owns strike selection, sizing, pricing and submission. Every proposal is logged next to the approved version with a `was_clamped` flag, so the ledger records what the model said *and* what the machine allowed.

## Risk gates

All deterministic, evaluated pre-order, logged pass or fail.

1. **Portfolio Greeks caps** — net delta/vega/gamma limits; orders are *clamped* to the largest compliant size, not rejected.
2. **Immediate delta hedging** — each underlying's hedge is rebalanced every cycle from positions actually held, not tracked incrementally.
3. **Inventory cost floor** — the closing side of a position is never quoted below cost plus a minimum edge. Without this the agent flattened inventory at whatever the mid had drifted to and *paid* the spread it was supposed to earn.
4. **Defined risk only** — Convexity trades spreads, never naked premium; max loss known at entry, capped at 2% of equity.
5. **Naked-leg reconciliation** — Alpaca's paper environment partially fills multi-leg orders ~10% of the time at random, and a half-filled vertical is a *naked short option*. Every cycle reconciles broker state before acting and flattens any incomplete spread.
6. **Daily drawdown circuit breaker** (2%) and a **kill switch**.
7. **Scheduled-event rule** — Non-Farm Payrolls landed inside the competition window. The agent widens quotes 1.6× and opens no new short premium for 20 hours before the print, places nothing across it, then re-engages at 0.85× once the uncertainty premium has collapsed. It has no opinion on the number — only on the fact that uncertainty is scheduled, priced, then resolved.

## Alpaca infrastructure

**Alpaca CLI** drives the unattended loop's account telemetry — Alpaca built it for "AI agents, scripts and automation pipelines" and it is the right tool for a scheduled agent. **Trading API** via `alpaca-py` for typed multi-leg (`OrderClass.MLEG`) construction. **Options Market Data API** for chains, snapshots and Greeks — running entirely on the **free indicative feed** (~10,000 of 12,500 SPY contracts return usable Greeks), with the strategy made deliberately latency-insensitive so a 15-minute data restriction is tolerable by design. **MCP server** as the research and operator surface, deliberately kept out of the order path. **News API** for the gold headlines.

Two platform constraints found by running it, not by reading docs: Alpaca rejects naked short calls, so the agent quotes puts only; and wash-trade protection rejects a simultaneous resting bid and ask on one contract, so it quotes the side that moves inventory toward flat.

## Honest notes

Paper fills are optimistic — Alpaca models no slippage, market impact or queue position, so live results would be worse. Per-mode P&L attribution is an approximation. The competition window was ~4 sessions, far too short for statistical significance; what the account demonstrates is a process running unattended and behaving as specified. **63 tests pass**, several written because live running broke the code first.
