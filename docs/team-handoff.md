# Team Handoff Notes

> **Read this first after `git pull`.** It is the fastest path from "just cloned" to "know what to do."
> **Last updated:** 2026-08-29 12:30 IST by Claude
> **Update rule:** whoever finishes a working session updates this file before pushing. No exceptions.

---

## ⏰ Where we are

**Sat 29 Aug, ~12:30 IST. Deadline Fri 4 Sep 20:30 IST — about 6 days, but only ~4.2 trading sessions.**

We are in the **research and convergence** phase. No code has been written (deliberately — code is frozen until Thomas gives the go-ahead).

---

## ✅ What has been completed

- Hackathon kickoff email and the full lablab.ai hackathon page analysed. Requirements, judging criteria, submission fields, deadline and prize structure extracted into [project-overview.md](project-overview.md).
- Technical research on the Alpaca stack: CLI, MCP server, options API, market-data tiers and their limits → [research.md](research.md).
- **Competitor analysis of the 12 submissions already published on the hackathon page** → [research.md](research.md) §2.
- 16 ideas generated, 4 evaluated in full, a recommendation made → [brainstorming.md](brainstorming.md).
- Two-tier architecture proposed, with an explicit challenge to the "frontend only, no backend" constraint → [architecture.md](architecture.md).
- 10 decisions recorded (2 decided, 8 proposed and awaiting sign-off) → [decisions.md](decisions.md).
- Task board with 46 tasks, staged, owner-tagged, with a critical path → [tasks.md](tasks.md).

---

## 🔨 What is being worked on right now

Nothing is in flight. **The project is waiting on Thomas** for the decisions below.

---

## 🚧 Blockers — all of them are decisions, not code

| Blocker | Who | Why it blocks |
|---|---|---|
| **Concept sign-off** (D-004) | Thomas | Every downstream task depends on what we are building |
| **Architecture sign-off** (D-006) | Thomas | Determines whether we can satisfy R1/R2 at all |
| **Dev A / Dev B assignment** | Thomas | Task board owners are placeholders |
| **New $100k paper account not created** (T-001) | Thomas | Hard eligibility requirement; the email says create it now |
| **Featherless credits not claimed** (T-003) | Thomas | First-come, first-served — may run out |

---

## ⚠️ The five things a newcomer must understand

1. **The judging window is ~4.2 trading sessions**, not 7 days. Mon 31 Aug → Fri 4 Sep 11:00 ET. P&L over that span is mostly noise, so we optimise for a *high-probability modest positive with a hard floor*, and win on the four criteria we fully control.

2. **US market hours are 19:00–01:30 IST.** We are asleep while the agent trades. This is not a detail — it is why the agent must genuinely be autonomous, idempotent and self-healing, and why a browser tab cannot be the runtime.

3. **Non-Farm Payrolls lands Fri 4 Sep 08:30 ET**, one hour before the final session's open and 2.5 hours before the submission deadline. It is the biggest scheduled volatility event of the month and it sits inside our judged window. None of the 12 published competitors mention event awareness.

4. **"Frontend only, no backend" as originally stated cannot satisfy the hackathon's hard requirements.** The Alpaca CLI is a Go binary and the MCP server is a self-hosted Python process — neither runs in a browser. The proposed amendment keeps the spirit (no server, no database, static dashboard, zero secrets in the browser) while achieving compliance. See [architecture.md](architecture.md) §2.

5. **0DTE options have no greeks on Alpaca** (days-to-expiry is in the Black-Scholes denominator). Any 0DTE-greek strategy is dead on arrival. Stay in the 7–45 DTE band.

---

## ▶️ Next actions, in order

**Thomas (today, Sat 29 Aug):**
1. Claim Featherless credits — code `ALPACA26` (first-come, first-served).
2. Create the brand-new paper account, set balance to $100,000, record the account ID. **Do not trade on it.**
3. Create a second, throwaway paper account for development.
4. Sign off (or push back on) D-004 concept and D-006 architecture.
5. Answer Q1 and Q4–Q7 in [project-overview.md](project-overview.md) §10.
6. Register the team on lablab.ai and join the Discord.

**Dev A (as soon as accounts exist):**
1. T-004 — install the Alpaca CLI, authenticate against the **dev** account, and validate a multi-leg (`mleg`) order with `--dry-run`. This is our highest-uncertainty technical unknown.
2. T-005 — confirm option chain + snapshot greeks come back on the free indicative feed for our candidate tickers.
3. T-006/T-007 — freeze the `state/` JSON contract and commit fixture files so Dev B is unblocked.

**Dev B (as soon as the contract is frozen):**
1. T-022 — dashboard skeleton reading the fixture JSON. Do not wait for the agent to exist.
2. T-023 — first build-in-public post. Day 1 content gets the most engagement, and the Social prize is separately winnable.

---

## 🐛 Known issues / open risks

| Risk | Severity | Status |
|---|---|---|
| Agent not live by Mon open → lose ~25% of the track record | **High** | Mitigated by staged plan (D-005); not yet actioned |
| Multi-leg order placement is not a documented CLI flag set | Medium | Must validate day 1 (T-004) |
| GitHub Actions cron drifts 5–30 min and **can silently drop runs** | Medium | Design must be latency-insensitive + idempotent + self-healing |
| Free-tier data: indicative options feed, IEX equities, last 15 min of history blocked, 200 req/min | Medium | Strategy designed around it; revisit Algo Trader Plus (P-4) |
| Short-premium book gapping through strikes on NFP Friday | **High** | Event rule T-027 — must be built before Thu close |
| Accidentally trading on the competition account during dev | **High** | Two-account separation (D-010) + env guard (T-002) |
| Only 2 developers across agent + frontend + video + slides + social | Medium | Presentation tasks are P0 and time-boxed in Stage 5 |
| ISM/ADP dates and window earnings unconfirmed | Low | T-010 |

---

## 📓 Session log

### 2026-08-29 · Claude
Analysed the kickoff email and hackathon page (the page carried far more than the email — deadline, judging criteria, full submission field list, judge names, and **12 live competitor submissions**). Researched the Alpaca CLI, MCP server, options API and data-tier limits; found the 0DTE-greeks blocker and the free-tier 15-minute historical restriction. Confirmed NFP falls inside the judging window. Built the full `docs/` structure, generated 16 ideas, evaluated the top 4, and recommended a staged build of a portfolio-greeks options desk with a glass-box dashboard. Challenged the frontend-only constraint with a two-tier alternative. **No code written.** Everything now waits on Thomas's decisions.
