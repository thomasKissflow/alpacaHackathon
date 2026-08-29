# Project Overview

> **Status:** Pre-build — research & idea convergence
> **Last updated:** 2026-08-29 (Sat)
> **Owner of this doc:** Claude (documentation owner)

---

## 1. Hackathon Summary

| Field | Value |
|---|---|
| **Event** | Alpaca AI Trading Agents Hackathon (lablab.ai × Alpaca) |
| **Format** | Fully online, 7 days |
| **Starts** | Fri 28 Aug 2026, 20:30 IST |
| **Submission deadline** | **Fri 4 Sep 2026, 20:30 IST** (15:00 UTC / 11:00 ET) |
| **Prize pool** | $6,300 |
| **Team size** | 1–6 (ours: 2) |
| **Main challenge** | "Options Alpha Agents" — an autonomous AI trading agent designed to generate P&L |
| **Page** | https://lablab.ai/ai-hackathons/alpaca-ai-trading-agents-hackathon |

### Prizes
- 🥇 $2,500 + $300 Featherless credits
- 🥈 $1,500
- 🥉 $1,000
- ⭐ **Social Engagement: 2 × $500** + 1-month Algo Trader Plus per team member

### Judges / mentors listed
Pawel Czech (CEO, lablab.ai) · Chiranjeev Shah (Technical Content Marketing, lablab.ai) · Tony Lee (Chief Brokerage Officer, Alpaca) · Grace Gao (PM, Alpaca) · Brandon Meyerowitz (Team Lead, Trading API, Alpaca)

> Read that judge list carefully: **three of five judges are Alpaca product people.** "Technology Implementation" is being scored by the people who built the API, the MCP server and the CLI. Idiomatic, correct, non-hacky use of their stack is worth real points, and hand-waving will be seen through instantly.

---

## 2. Hard Requirements (non-negotiable — failure here = ineligible)

| # | Requirement | Notes |
|---|---|---|
| R1 | **Autonomous** AI trading agent using Alpaca's Trading API | Must run and decide without a human in the loop |
| R2 | Must use **Alpaca's MCP server OR CLI** | Not just the raw REST SDK |
| R3 | **All strategies must incorporate options trading** | Options are mandatory, not optional |
| R4 | **Brand-new Alpaca paper account** dedicated to this hackathon | Reused/existing account = *not eligible for judging* |
| R5 | Starting balance set to **$100,000** | Configure on the new account |
| R6 | **Alpaca paper account ID** included in submission | This is how judges pull our P&L |
| R7 | **One-page write-up**: AI logic, risk gates, Alpaca infrastructure | Explicitly named deliverable |

### Submission checklist (from the hackathon page)
- [ ] Project title, short description, long description, technology & category tags
- [ ] Cover image
- [ ] Video presentation
- [ ] Slide presentation
- [ ] Public GitHub repository
- [ ] Demo application platform + **Application URL** (i.e. something hosted and clickable)
- [ ] **Alpaca paper trading account ID**
- [ ] Up to 5 social post links (X / LinkedIn), tagging @lablabai and @AlpacaHQ
- [ ] One-page write-up (AI logic / risk gates / Alpaca infrastructure)

---

## 3. Judging Criteria

Five criteria, **no published weights**:

1. **P&L Performance** — trading performance in the paper environment; P&L *and* how effectively the strategy performs through its trading activity
2. **Technology Implementation** — how effectively we use Alpaca's Trading API, MCP server, CLI
3. **Creativity & Originality** — of concept, strategy, agent behaviour
4. **Presentation & Execution** — clarity, demonstrating the agent in action, explaining the reasoning
5. **Social Engagement** — quality of content *and* engagement generated

> **Strategic read:** 4 of the 5 criteria are fully under our control. Only P&L is partly luck. See [decisions.md](decisions.md) D-003.

---

## 4. The Real Problem We Are Solving

**Stated problem:** build an autonomous agent that trades options and makes money.

**Actual problem, stated honestly:**

> Produce a *defensible, positive, explainable* options P&L over **~4.2 trading sessions**, from an agent that runs unattended while its two operators are asleep, using free-tier delayed market data — and make a judge believe the result came from a repeatable process rather than a coin flip.

That reframing drives every architectural and strategic decision in this repo. The window is too short for statistical significance, so **process legibility is the differentiator**, and P&L must be engineered for a high probability of a *modest* gain with a hard floor, not a lottery ticket.

---

## 5. The Clock (this is the binding constraint)

Deadline: **Fri 4 Sep, 20:30 IST**. US market hours in IST are **19:00 – 01:30**, i.e. overnight for us.

| Date | Day | Market | Notes |
|---|---|---|---|
| Sat 30 Aug | Sat | Closed | Build |
| Sun 31 Aug | Sun | Closed | Build — **agent must be live by end of today** |
| Mon 31 Aug | Mon | **Open** | Session 1 |
| Tue 1 Sep | Tue | **Open** | Session 2 |
| Wed 2 Sep | Wed | **Open** | Session 3 |
| Thu 3 Sep | Thu | **Open** | Session 4 |
| Fri 4 Sep | Fri | **Open until 11:00 ET** | Session 5 (partial, ~1.5h) — **NFP at 08:30 ET** |

**Total: ~4.2 trading sessions of P&L.**

Two consequences:
1. **Every day the agent is not live costs ~20-25% of our track record.** Getting a *simple, correct* agent trading on Monday's open beats getting a sophisticated one trading on Wednesday.
2. **Non-Farm Payrolls lands Fri 4 Sep 08:30 ET**, 1 hour before the open and 2.5 hours before the submission deadline. It is the single most market-moving scheduled release, and it sits inside our judging window. This is both a risk (gap through our short strikes on the last morning) and an opportunity (an event-aware agent is a great demo). See [research.md](research.md) §5.

---

## 6. Vision

> An autonomous options desk that runs itself overnight, sizes every trade against a portfolio risk budget rather than a gut feeling, and can *replay and justify every decision it made* — so a judge can audit the process, not just the number.

---

## 7. Target Users

| User | Why they care |
|---|---|
| **The hackathon judges** (primary, be honest) | They need to evaluate P&L, tech usage, originality and clarity in a few minutes |
| Retail options traders with a day job | Cannot watch the market; want defined-risk automation they can inspect |
| Quant-curious developers | Want a legible reference implementation of an agentic trading loop on Alpaca |
| Alpaca (as a platform) | Wants a flagship example of agentic trading on their MCP/CLI stack |

---

## 8. High-Level Solution

**Not yet locked.** Candidate direction (see [brainstorming.md](brainstorming.md) and [decisions.md](decisions.md) D-004):

A two-tier system:
- **Agent runtime** — a scheduled, unattended job that uses the **Alpaca CLI / MCP server** to read the market, decide, and place defined-risk options trades, writing a full decision log.
- **Glass-box dashboard** — a static, frontend-only app that replays the agent's decision log and shows live positions/P&L, deployed at a public URL.

Awaiting your decision on the strategy concept before this section is filled in.

---

## 9. Current Status

| Area | Status |
|---|---|
| Hackathon analysis | ✅ Complete |
| Technical research | ✅ First pass complete (Alpaca CLI, MCP, data tiers, competitors) |
| Documentation structure | ✅ Created |
| Idea generation | ✅ 14 ideas logged, top 4 fully evaluated |
| **Strategy decision** | ⏳ **Awaiting Thomas** |
| New paper account (R4) | ❌ Not created — **blocking, do today** |
| Featherless credits | ❌ Not claimed — first-come-first-served |
| Repo scaffold | ❌ Not started (code frozen until instructed) |
| Agent live | ❌ Target: Sun 31 Aug |

---

## 10. Open Questions

| # | Question | Blocking? | Owner |
|---|---|---|---|
| Q1 | Who are Developer A and Developer B, and what are their strengths? | Task assignment | Thomas |
| Q2 | Which strategy concept do we commit to? | **Yes — everything downstream** | Thomas |
| Q3 | Are we willing to run the agent runtime outside the browser (scheduled job)? See [architecture.md](architecture.md) §2 | **Yes — R1/R2 depend on it** | Thomas |
| Q4 | Do we pay $99 for Algo Trader Plus (OPRA real-time options data), or engineer around the free indicative feed? | Strategy design | Thomas |
| Q5 | Who owns the social/build-in-public workstream? It is a separately winnable $500. | Prize EV | Thomas |
| Q6 | Do we have X and LinkedIn accounts with any existing audience? | Social prize realism | Thomas |
| Q7 | Is anyone awake/available during US market hours (19:00–01:30 IST) for a manual kill switch? | Risk design | Thomas |

---

## 11. Important Links

### Hackathon
- Hackathon page — https://lablab.ai/ai-hackathons/alpaca-ai-trading-agents-hackathon
- lablab.ai Discord — https://discord.gg/lablab-ai (register required)

### Alpaca
- Docs home — https://docs.alpaca.markets/
- Trading API — https://docs.alpaca.markets/docs/trading-api
- Options Trading — https://docs.alpaca.markets/us/docs/options-trading
- Multi-leg (Level 3) in paper — https://docs.alpaca.markets/changelog/multi-leg-level-3-options-trading-in-paper
- **Alpaca CLI (repo)** — https://github.com/alpacahq/cli
- **Alpaca CLI (docs)** — https://docs.alpaca.markets/us/docs/alpacas-cli
- **Alpaca MCP Server** — https://github.com/alpacahq/alpaca-mcp-server
- MCP docs — https://docs.alpaca.markets/us/docs/alpaca-mcp-server
- Market Data plans — https://docs.alpaca.markets/us/docs/about-market-data-api
- Paper account signup — https://app.alpaca.markets/signup

### Sponsor
- Featherless AI docs — https://featherless.ai/docs/quickstart-guide
- Featherless credit code: `ALPACA26` ($25/participant, first-come-first-served)

---

## 12. Document Map

| Doc | Purpose |
|---|---|
| [project-overview.md](project-overview.md) | This file — what/why/status |
| [brainstorming.md](brainstorming.md) | Every idea, with Accepted / Rejected / Needs Research / Future Scope |
| [research.md](research.md) | Alpaca stack, data constraints, competitor analysis, market calendar |
| [architecture.md](architecture.md) | System design and the frontend-only constraint challenge |
| [tasks.md](tasks.md) | Backlog / In Progress / Blocked / Done, with owners |
| [decisions.md](decisions.md) | Decision log with reasoning and alternatives |
| [team-handoff.md](team-handoff.md) | Pull-latest-and-catch-up doc |
