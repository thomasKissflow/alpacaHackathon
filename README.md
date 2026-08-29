# Alpaca AI Trading Agents Hackathon

> lablab.ai × Alpaca · 28 Aug – **4 Sep 2026, 20:30 IST** · $6,300 prize pool · Team of 2

**Status:** 📚 Research & convergence — no application code yet.

## Start here

| If you want to… | Read |
|---|---|
| **Catch up after a `git pull`** | **[docs/team-handoff.md](docs/team-handoff.md)** ← start here |
| Understand what we're building and why | [docs/project-overview.md](docs/project-overview.md) |
| See every idea, including rejected ones | [docs/brainstorming.md](docs/brainstorming.md) |
| Check technical constraints & the competition | [docs/research.md](docs/research.md) |
| Understand the system design | [docs/architecture.md](docs/architecture.md) |
| Find something to work on | [docs/tasks.md](docs/tasks.md) |
| Know why a choice was made | [docs/decisions.md](docs/decisions.md) |

## The three things that matter most

1. **~4.2 trading sessions** of judged P&L (Mon 31 Aug → Fri 4 Sep 11:00 ET). Getting a simple agent live for Monday's open beats getting a clever one live on Wednesday.
2. **US market hours are 19:00–01:30 IST.** The agent trades while we sleep, so it must be genuinely autonomous, idempotent and self-healing.
3. **NFP lands Fri 4 Sep 08:30 ET**, inside the judging window and 2.5h before the deadline.

## Hard requirements

- Autonomous AI trading agent on Alpaca's Trading API
- Must use Alpaca's **MCP server or CLI**
- **All strategies must incorporate options**
- **Brand-new** paper account, **$100,000** starting balance, account ID in the submission
- One-page write-up: AI logic, risk gates, Alpaca infrastructure

## Documentation rule

Every discussion, decision, research finding or architecture change is written into `docs/` in the same session it happens. If it isn't in the docs, it didn't happen.
