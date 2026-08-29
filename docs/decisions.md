# Decisions Log

> One entry per meaningful decision. Nothing here is deleted; superseded decisions are marked and linked forward.
> **Status:** `DECIDED` · `PROPOSED` (awaiting Thomas) · `SUPERSEDED`

---

## D-001 — Documentation-first working model
**Date:** 2026-08-29 · **Status:** DECIDED

**Decision:** Every discussion, idea, research finding and architectural change is written into `docs/` in the same session it happens. Documentation is a first-class deliverable, not a trailing artifact.

**Reasoning:** Two developers working in parallel across a 7-day window with overnight market hours cannot rely on synchronous communication. The repo has to be the shared brain. Secondary benefit: the hackathon requires a one-page write-up and a slide deck — these docs are the raw material, so the work is not duplicated at the end when we will be exhausted.

**Alternatives considered:** Chat-only coordination (fails the moment one dev is asleep); a single README (does not scale past day two).

**Impact:** Small ongoing cost per session; large payoff in handoff quality and in the final write-up.

---

## D-002 — Read the competition before designing
**Date:** 2026-08-29 · **Status:** DECIDED

**Decision:** Treat the 12 already-published submissions on the hackathon page as primary research and design explicitly against the field.

**Reasoning:** lablab publishes submissions live. That is an unusual and significant information advantage — most teams will not look. It let us identify that "SPY-only", "risk gates" and "refuses to trade" are saturated framings, and that portfolio-level risk management, event-awareness and auditability are unclaimed. See [research.md](research.md) §2.

**Alternatives considered:** Design in a vacuum on strategy merit alone — would very likely have produced a seventh SPY-signal agent.

**Impact:** Reshaped the entire idea shortlist. Directly caused D-004 and the rejection of B7/B8/B10.

---

## D-003 — Optimise for P(top 3 overall), not for maximum P&L
**Date:** 2026-08-29 · **Status:** PROPOSED

**Decision:** Engineer the P&L *distribution* for a high probability of a modest positive return with a hard floor, and win decisively on the four criteria that are fully under our control (Technology Implementation, Creativity, Presentation, Social).

**Reasoning:** The judging window is **~4.2 trading sessions**. No options strategy has statistical significance over four days — the P&L leaderboard will be substantially determined by luck. Four of the five criteria are not. Swinging for the highest P&L means accepting a large probability of a *negative* number, which damages criterion 1 *and* undermines the credibility of everything we say in criteria 2–4. A defensible +1% with a visibly professional process beats a 25%-likely +15% with a 40%-likely -20%.

**Alternatives considered:**
- *Maximise expected return* — correct for an investor, wrong for a 4-day rank tournament with four other criteria.
- *Maximise variance to win the P&L leaderboard outright* — a rational play only if P&L were the sole criterion. It is one of five.

**Impact:** Drives defined-risk structures only, diversification across underlyings, hard drawdown kill switch, and continuous (not abstaining) market participation.

---

## D-004 — Build an autonomous options *desk*, not a signal bot
**Date:** 2026-08-29 · **Status:** PROPOSED — **needs Thomas's sign-off (Q2), blocks everything**

**Decision:** Build a diversified, defined-risk options book managed against a **portfolio-level greeks budget** (net delta / vega / theta), selecting structures from a regime-matched playbook, harvesting volatility risk premium, with scheduled-event awareness — presented through a glass-box replayable dashboard.

**Reasoning:**
1. It is the only unclaimed *sophisticated* lane: no competitor manages book-level greeks.
2. Diversification mechanically reduces the variance of a 4-day P&L, which is the right response to D-003.
3. VRP is a real, explainable positive-drift edge — we can say *why* we expect to make money without hand-waving.
4. It exercises the deep end of Alpaca's options API (multi-leg, chain, snapshot greeks), which three Alpaca judges will recognise.
5. It avoids every saturated framing.

**Alternatives considered:** see [brainstorming.md](brainstorming.md) — news-driven (crowded), multi-agent debate (AlphaSwarm owns it), 0DTE (technically blocked — no greeks), backtest-first research (crowded + abstention trap), IV dispersion (data risk too high for the timeline).

**Impact:** Medium-High complexity. **Mitigated by mandatory staging (D-005).**

---

## D-005 — Stage the build; a simple correct agent must be live for Monday's open
**Date:** 2026-08-29 · **Status:** PROPOSED

**Decision:** Stage 1 is a deliberately simple, correct VRP credit-spread agent, live before Mon 31 Aug 09:30 ET. Sophistication (portfolio-greeks allocator, regime playbook, dashboard) is layered on Mon–Thu *while the agent is already trading*.

**Reasoning:** There are only ~4.2 trading sessions. Every day the agent is not live destroys ~20-25% of our track record — and P&L is a judged criterion we cannot retroactively manufacture. A dumb agent trading on Monday beats a brilliant one trading on Wednesday. This also de-risks the whole project: if Stage 2+ slips, we still have a complete, working, judgeable submission.

**Alternatives considered:** Build the full system then deploy (~Tue/Wed) — sacrifices 40-50% of the track record and leaves no margin if anything breaks.

**Impact:** Stage 1 scope must be ruthlessly minimal. Non-negotiable gate.

---

## D-006 — Challenge and amend the "frontend only, no backend" constraint
**Date:** 2026-08-29 · **Status:** PROPOSED — **needs sign-off (Q3)**

**Decision:** Amend to: **"No application server, no database — but the agent runtime is a scheduled job, not a browser tab."** Tier 1 is a cron-triggered script (holds secrets, uses the Alpaca CLI, commits state). Tier 2 is a 100% static dashboard reading committed JSON, with zero secrets.

**Reasoning:** A pure browser app cannot satisfy R1 (autonomy overnight, 19:00–01:30 IST), cannot satisfy R2 (the CLI is a Go binary; the MCP server is a self-hosted Python process — neither runs in a page), and would expose keys on an account whose ID we are *required* to publish (R6), creating a real sabotage vector. Full reasoning in [architecture.md](architecture.md) §2.

**Alternatives considered:**
- Pure frontend + browser tab left open — fails "autonomous" on inspection; fragile; judges will ask.
- Browser calls Alpaca directly via CORS (which Alpaca does allow) — key exposure on a published account ID is unacceptable.
- A real backend (Fastify/Express on Railway) — more capable, but violates the constraint's actual intent and adds ops burden for no benefit.

**Impact:** Preserves the spirit of the constraint (nothing to operate, Dev B stays entirely in the frontend) while achieving compliance. Note this is *less* operational surface than a typical frontend-only app, not more.

---

## D-007 — Use the CLI for execution and MCP for research (both, deliberately)
**Date:** 2026-08-29 · **Status:** PROPOSED

**Decision:** The unattended execution loop runs on the **Alpaca CLI**. The **MCP server** is used as the research and operator surface (interrogating the book from Claude Code, exploratory chain analysis, the demo).

**Reasoning:** R2 requires one; using both well is stronger than using one thinly, *provided each has a genuine job*. The CLI is explicitly built by Alpaca for "AI agents, scripts, and automation pipelines" — JSON-first, `--client-order-id` idempotency, `--dry-run` preflight, built-in jq. Putting an LLM in the hot path of an order submission would be slower, costlier and non-deterministic. MCP earns its place as the human/LLM-facing surface and has native multi-leg `place_option_order`.

**Alternatives considered:** MCP-only (LLM in the execution path — non-deterministic, and the MCP server needs an MCP *client* to drive it, so autonomy still needs solving); CLI-only (leaves an obvious judged capability unused).

**Impact:** Two integrations instead of one; modest extra effort, materially stronger "Technology Implementation" story.

---

## D-008 — The LLM never has direct execution authority
**Date:** 2026-08-29 · **Status:** PROPOSED

**Decision:** LLMs classify market regime, generate rationale text, and may **veto** a trade. They never choose position size, never choose strikes unbounded, and never submit an order. Structure construction, sizing and submission are deterministic code behind hard gates.

**Reasoning:** Reproducibility, explainability, and blowup protection. An LLM that can size positions can, on one bad sample, end our P&L. A veto-only LLM can only ever make us *more* conservative. It is also the honest engineering answer, and it makes a strong, quotable claim on camera.

**Alternatives considered:** Full LLM agency (higher originality optics, unacceptable tail risk, and hard to reproduce); no LLM at all (fails the spirit of an *AI* trading agent hackathon and wastes the Featherless partner-prize angle).

**Impact:** Shapes the entire agent loop. Note this is *similar* to AEGIS-Q's stated approach — we are not unique here, so do not lead the pitch with it.

---

## D-009 — Treat Social Engagement as a first-class workstream
**Date:** 2026-08-29 · **Status:** PROPOSED

**Decision:** Assign explicit ownership of build-in-public content, and generate most of it automatically as a by-product of the agent (the "Desk Notes" idea, B16).

**Reasoning:** The Social Engagement prize is **2 × $500 + Algo Trader Plus per member**, judged on content quality *and* engagement. Most engineering teams treat it as an afterthought or skip it entirely, so the effective competition is far thinner than for the main prizes. It is also a *separate* prize pool — winning it does not compete with placing in the main three. On expected value per hour invested, it is likely the highest-ROI work in the hackathon. Making the agent write its own daily commentary means the content pipeline costs almost nothing after the first day.

**Alternatives considered:** Ignore it (leaves ~$1,000 + subscriptions on the table for a handful of hours); manual daily posts (works, but competes with build time at exactly the wrong moment).

**Impact:** ~1h/day of one developer's time, mostly on day 1.

---

## D-010 — Create the competition account today, and never prototype on it
**Date:** 2026-08-29 · **Status:** PROPOSED — **urgent**

**Decision:** Create the brand-new $100k paper account immediately, record its ID in the repo, and use a **separate** throwaway paper account for all development and testing.

**Reasoning:** R4 disqualifies reused accounts and the email says "create it now so your trading history is clean from minute one." A single accidental test order on the competition account contaminates the history we are judged on. Two accounts, two credential sets, and the competition credentials must only ever live in GitHub Actions Secrets — never in a local `.env` that a test script might pick up.

**Alternatives considered:** One account with careful discipline — one mistake at 01:00 IST costs us eligibility. Not worth it.

**Impact:** Two credential sets to manage; an environment-separation guard is a Stage 0 task (T-002).

---

## Pending decisions (not yet made)

| # | Decision needed | Blocks | Owner |
|---|---|---|---|
| P-1 | Sign off D-004 (the concept) | Everything | Thomas |
| P-2 | Sign off D-006 (the architecture amendment) | Stage 1 | Thomas |
| P-3 | Agent runtime language: Python vs TypeScript | Stage 1 | Thomas + devs |
| P-4 | Buy Algo Trader Plus ($99) for OPRA data? | Strategy design | Thomas |
| P-5 | Public repo from day 1, or private-then-public? | Stage 1 | Thomas |
| P-6 | Project name | Branding, cover image | Team |
| P-7 | Underlying basket (which 6–10 tickers) | Stage 1 | Dev A |
| P-8 | Dev A / Dev B assignment to real people | Task board | Thomas |
