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
**Date:** 2026-08-29 · **Status:** SUPERSEDED by [D-011](#d-011--pivot-the-concept-to-an-options-market-maker-specialist-mode--convexity-mode-fallback)

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
**Date:** 2026-08-29 · **Status:** SUPERSEDED (constraint amendment accepted; concrete state/dashboard shape changed — see [D-012](#d-012--adopt-a-sqlite-ledger-and-a-static-vanilla-jshtml-dashboard-instead-of-json-files--reactvite))

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

## D-011 — Pivot the concept to an options market-maker (Specialist Mode) + Convexity Mode fallback
**Date:** 2026-08-31 · **Status:** DECIDED — supersedes D-004

**Decision:** Build "The Specialist" — an autonomous options market maker that quotes both sides of the market on a small basket of liquid, near-the-money options (SPY, QQQ, AAPL, NVDA, TSLA), captures the bid/ask edge, and immediately delta-hedges every fill with the underlying (**Specialist Mode**). A second, independent strategy — IV-rank/trend-filtered defined-risk vertical spreads and iron condors (**Convexity Mode**) — runs in parallel through the same risk core and ledger, specifically so the account keeps generating judged trading activity even in a week where Specialist Mode's passive quotes don't get filled. An LLM agent layer (Claude or Featherless) decides *where* to make markets and *how wide* to quote, and writes a daily post-mortem; it never places an order (unchanged principle from D-008).

**Reasoning:**
1. **This is a genuinely different, and arguably wider-open, lane than D-004's proposal.** The team's own competitor research ([research.md](research.md) §2) found no book-level-greeks manager among the 12 published entries — true, and D-004 was a sound response to that gap. But it also found nobody doing *inventory-managed two-sided quoting* — market making is a market-microstructure activity, not a directional-or-volatility bet, and none of the 12 competitors (signal bots, LLM-gated pickers, human-in-the-loop notifiers) touch it either. It is at least as unclaimed as D-004's framing, and it maps even more directly onto Alpaca's own "algorithmic trading" framing of the challenge.
2. **De-risks the P&L criterion the same way D-003 already argued for, via a different mechanism.** D-003's goal — a defensible, low-variance, explainable P&L over ~4.2 sessions — holds completely and is *why* this build ships two independent, parallel P&L engines (captured-spread market-making, and defined-risk premium-selling) sharing one ledger, rather than staging one concept into another over the week. If Specialist Mode's fills are sparse in a quiet week (a real risk with paper trading's fill semantics, see [research.md](research.md) §1.6), Convexity Mode still produces real, judgeable activity independently.
3. **It was already built, end-to-end, and tested against a real Featherless key before this decision was written down.** Given the clock (D-003's binding constraint), a complete, currently-working implementation beats re-deriving the portfolio-greeks-desk concept from scratch. This is a legitimate reason on a 4-day build, but it is an honest one, not a technical argument that D-004 was wrong — see "What we're giving up" below.
4. Both concepts satisfy R1–R7 equally well and use the same CLI-for-execution / MCP-for-research split the team had already independently arrived at (D-007) — that reasoning carries over unchanged.

**What we're giving up from D-004 (say this plainly, don't bury it):**
- **Book-level Greeks budget as the core allocator abstraction.** This build tracks and caps portfolio delta/vega/gamma (see D-012 and `agent/risk_gate.py`), but as *hard limits on a market-making/premium-selling book*, not as the risk-budget-driven trade-selection allocator D-004 envisioned (B1). If sophistication time remains this week, a Greeks-budget allocator layered on top of Convexity Mode's structure selection is the closest bridge back to that original idea — worth revisiting as Stage 2-equivalent work, not a rebuild.
- **Regime-switching playbook selection (B3)** is not implemented. Convexity Mode's trend read (SMA20/SMA50) is a simpler version of the same instinct.
- **NFP event-awareness (D-004/B5) is not yet implemented in this build** — still correctly flagged as high-severity and unclaimed in [research.md](research.md) §5, still needs to land before Thursday close regardless of which concept underlies the agent. Tracked in [tasks.md](tasks.md).
- **10–15% of team research effort (the VRP/regime-desk-specific parts of brainstorming.md Part C and decisions D-003) doesn't carry forward directly.** The account setup, data-tier findings, competitor analysis, paper-fill semantics ([research.md](research.md) §1.4–1.6), and D-001/D-007/D-008/D-009/D-010 all carry forward completely unchanged — this was not wasted work.

**Alternatives considered:** Build D-004 as originally scoped (rejected for now — would mean discarding a working, tested implementation to re-derive a comparable amount of new code, on a 4-day clock, for a concept whose main advantage — differentiation — this build's concept shares); build both concepts and pick the stronger one by mid-week (rejected — splits the team's scarce time on a clock where D-005's own logic says a live, correct agent beats a hypothetically-better one still being built).

**Naming (resolves P-6):** "The Specialist" — a specialist, in market-structure terms, is literally who makes a two-sided market in a security. Fits this concept much better than the `Nightshift`/`Vega Budget` shortlist, which were coined for the VRP-desk framing.

**Impact:** Supersedes D-004. Does not touch D-001, D-002, D-003, D-005 (still directionally correct — see note below), D-007, D-008, D-009, D-010, which all apply unchanged.
**Note on D-005:** its literal Stage 1/2/3 sequencing (simple VRP spreads first, sophistication layered on while live) doesn't apply to a system built complete before go-live, but its underlying principle — a simple, correct agent live for Monday's open beats a sophisticated one live Wednesday — is exactly why this build ships both modes together now rather than staging Specialist Mode in later.

---

## D-012 — Adopt a SQLite ledger and a static vanilla-JS/HTML dashboard, instead of JSON files + React/Vite
**Date:** 2026-08-31 · **Status:** DECIDED — supersedes the concrete state/dashboard shape proposed under D-006 (the "no server, no database, git-as-audit-trail" *principle* is unchanged and fully honored)

**Decision:** State (orders, fills, hedges, risk-gate events, LLM MarketPlans, postmortems, account/position snapshots) lives in one append-only SQLite file (`agent/ledger.py`, `data/ledger.db`) committed to the repo, rather than one JSON file per agent run under `state/decisions/*.json`. The dashboard (`dashboard/*.html+js`) is a single static page using Chart.js, reading one exported JSON snapshot (`agent/dashboard_export.py` → `data/dashboard.json`) — no React/Vite/Tailwind/Recharts build step, no npm toolchain, no Vercel deploy.

**Reasoning:**
1. **The core idea D-006 was arguing for — no application server, no database-as-a-service, the git repo itself as the audit trail — is fully preserved.** SQLite is a single file, not a server; it is arguably a *more* literal reading of "no database" than a folder of hand-shaped JSON files, and it is trivially inspectable by a judge with any SQLite browser (a concrete ask from `agent/config.py`'s own comments: "keep it simple and inspectable, since judges may want to see raw data").
2. **A single ledger with real foreign keys (fills reference orders, hedges reference the fill that triggered them) is a more honest audit trail than independent per-run JSON snapshots** for a system with two interacting strategies feeding one shared risk gate — reconstructing "why did the portfolio delta look like X at time T" is a join, not a multi-file scan.
3. **Zero npm toolchain removes a dependency and a build step** from a project that already has no other JS tooling; Chart.js via a CDN `<script>` tag is enough for an equity curve, Greeks gauges, and activity feeds. This trades away Recharts' visual polish and the time-travel replay UI's interaction quality (see "What we're giving up").
4. Both choices honor D-006 §2.1's actual constraints: no secrets in the browser (dashboard reads a public JSON export, same as before), works on GitHub Pages with zero backend, zero ops surface added.

**What we're giving up:**
- **The time-travel replay UI (T-030, a named P0 presentation differentiator in the original plan)** is not implemented. The current dashboard shows live/recent state (equity curve, current Greeks/inventory, activity feed, risk log, postmortems) but not a scrubbable timeline over the whole week. This is a real gap against a documented judging-criterion play (Presentation & Execution) and is the single highest-value frontend addition someone should pick up this week — the ledger already has everything a replay view would need (every row is timestamped); it needs a UI, not new state-collection work.
- **React/TypeScript component reuse and Dev B's originally-scoped frontend stack** don't apply to this codebase as shipped. If Dev B strongly prefers building the replay UI in React reading `data/dashboard.json` (or querying `data/ledger.db` directly via sql.js in the browser), that's a compatible, additive change — the data layer doesn't need to change for that.

**Alternatives considered:** Rebuild the ledger as `state/decisions/*.json` to match D-006's literal sketch (rejected — would mean re-plumbing every module in a working, tested system for a format whose only advantage is matching a sketch that predates any real data); keep both formats in parallel (rejected as unnecessary duplication of the same information).

**Impact:** Supersedes D-006's concrete `state/` JSON shape and frontend stack choice. The underlying principle (no server, no DB-as-a-service, static+public dashboard) is unchanged. `agent/dashboard_export.py` is the seam if someone wants to add a richer frontend on top later — it doesn't need the ledger schema to change to do that.

---

## D-013 — Specialist Mode's execution mechanic, corrected against real platform behavior found live
**Date:** 2026-08-31 · **Status:** DECIDED — refines D-011, doesn't reverse it

**Decision:** Running Specialist Mode against a real Alpaca paper account (rather than assuming the mechanics from the build brief would just work) surfaced two hard platform constraints and led to three bug fixes, all before any account was treated as the competition account:

1. **Puts only, not puts-and-calls.** Alpaca rejected a naked short call live: `"account not eligible to trade uncovered option contracts"`. A short call is uncovered (unbounded loss) unless backed by 100 held shares per contract or built as a recognized spread; a short put is cash-secured (bounded risk, covered by cash) and Alpaca allows it as a plain single-leg order. Specialist Mode now quotes puts only. Convexity Mode already covers call-side exposure structurally, via spreads.
2. **One side per contract per cycle, not both simultaneously.** Alpaca's wash-trade protection also rejected a live order: `"cannot open a short sell while a long buy order is open"`. The literal mechanic of "post a resting bid and a resting ask on the same contract at the same time" is not achievable via plain orders on this platform. `agent/specialist_mode.py::_pick_quote_side()` now quotes whichever side moves inventory toward flat (sell when long, buy when short, alternating when flat) — one live price per contract at a time, not two.
3. **Three bugs, found and fixed via the same live run, before any of this touched a real competition account:**
   - A rounding bug: bid/ask were checked for crossing at float precision but placed independently rounded to the cent, so a computed $7.278/$7.282 quote could collapse to $7.28/$7.28 and get rejected as a wash trade. Fixed in `compute_quote_prices()`.
   - A reconciliation scope bug: fills were only reconciled for contracts still selected as nearest-ATM *this* cycle. A contract that filled and then fell out of selection was never revisited, leaving a real fill unhedged indefinitely. Fixed by making reconciliation scan every open Specialist order globally, every cycle (`_reconcile_all_open_orders()`).
   - A hedge-orphaning bug: hedges were applied incrementally per fill, so when a position closed via the book's own opposite-side fill, its hedge was never unwound. Fixed by rebalancing each underlying's equity hedge to its *current total target delta* every cycle (`_rebalance_hedge()`), recomputed from currently-held positions rather than tracked incrementally.

**Reasoning:** All three bugs and both constraints were only discoverable by actually running the system against Alpaca's real (paper) order-entry logic — none of it is documented in Alpaca's public docs in a way that would have surfaced it from reading alone. This is exactly the kind of finding [research.md](research.md) and [team-handoff.md](team-handoff.md) already argued for doing early (T-004/T-021, "highest-uncertainty technical unknown," "the first real order must be intentional") — it just happened for Specialist Mode specifically, after D-011 had already been decided on paper. None of this reverses D-011's core call: market-making liquidity provision on puts, inventory-managed, is still a genuinely differentiated, still-unclaimed lane; it's more precisely specified now than it was when only described in prose.

**A process note, not a strategy one:** this testing surfaced a real mistake — while probing whether short puts were also restricted like short calls, a test order's price direction was set wrong and it filled for real (an inorganic, non-strategic trade). Per D-010's own logic (never contaminate the competition account with test trades), that account was retired to dev/sandbox use and a fresh account is needed before the account ID goes in the submission. **T-001 is unchanged and still the most urgent open item** — see [team-handoff.md](team-handoff.md).

**What's now actually validated live** (closing out T-004/T-005's "highest-uncertainty technical unknown" status): option chain + snapshot Greeks return correctly on the free indicative feed for the full basket (Greeks populate only when bid/ask are both non-zero, exactly as documented); Convexity Mode's MLEG bull-put-spread submission works via the SDK; Specialist Mode's put quoting, fill reconciliation, and hedge rebalancing all work end-to-end after the fixes above; portfolio delta converged to within ~$100 of flat after a hedge rebalance, against a $25,000 cap.

**Impact:** `agent/specialist_mode.py` rewritten around these constraints. `agent/occ.py` gained `underlying_from_occ_symbol()`. Test coverage added for all of the above (`tests/test_specialist_pricing.py`, `tests/test_specialist_reconcile.py`) — 39 tests passing, still zero live API calls in the suite itself. T-004/T-005/T-021 move from "assumed" to "validated, with fixes."

---

## D-014 — Scheduled-event rule: de-risk into NFP, blackout across it, re-engage after
**Date:** 2026-09-04 · **Status:** DECIDED — implements the D-004/B5 event-awareness item that D-011 left open

**Decision:** `agent/event_calendar.py` gives the agent a calendar of scheduled macro releases and four postures around each one. For Non-Farm Payrolls (Fri 4 Sep 2026, 08:30 ET / 12:30 UTC):

| Phase | Window | Behaviour |
|---|---|---|
| `derisk` | T-20h → T-45m | Quotes widened 1.6x, size cut 25%, **no new short premium opened** that would be held across the release |
| `blackout` | T-45m → T+75m | Place nothing. Covers the print and the first ~15 min of the open |
| `reengage` | T+75m → T+5h | Quotes tightened to 0.85x, full size, short premium allowed again |
| `normal` | otherwise | Unchanged |

Existing positions are still monitored, hedged and closed in every phase — the rule only gates *opening* new risk. The posture is applied **after** the LLM MarketPlan is approved, so the model can neither widen its way out of nor argue past an event rule (consistent with D-008).

**Reasoning:**
1. **It is the only thing a trading agent can know in advance.** Every other input this system uses is reactive — prices and Greeks that have already moved. A scheduled release is genuinely forecastable, and the largest of the month lands inside the judging window, one hour before the final session opens and 2.5 hours before the submission deadline.
2. **The overnight gap is the one loss this account cannot recover from.** A short-gamma book gapping through its strikes on Friday's open would end the P&L story with no session left to repair it. De-risking into the print is the conservative posture and is consistent with D-003's "high-probability modest positive with a hard floor."
3. **Post-event is genuinely safer, not riskier.** Once the number is known the uncertainty premium collapses, so quoting *tighter* to win fills after the print is the correct market-making response — and the re-engage window (13:45–15:00 UTC) is exactly the final session before judging.
4. **Unclaimed.** None of the 12 published competitor submissions mentions event awareness at all ([research.md](research.md) §5). This is differentiation that costs one module.
5. It is not a directional bet. The agent has no opinion on payrolls — only on the fact that uncertainty is scheduled, priced, and then resolved.

**Alternatives considered:**
- **Deliberately sell premium into the print to harvest the IV crush** (the aggressive version). Rejected: it is a coin flip on one number, on the last morning, with the whole P&L riding on it. Directly contradicts D-003. The crush is real, but capturing it requires carrying gap risk we cannot afford with no session left to recover.
- **Flatten the book entirely before the print.** Rejected: zero positions means zero trading activity in the final session, which judging criterion 1 explicitly weighs ("P&L *and how effectively the strategy performs through its trading activity*"). This is the abstention trap in a different costume.
- **Halve quote size during de-risk** (initial calibration). Softened to 0.75x: with only ~4 hours of market left in the whole competition, over-throttling Thursday costs fills we cannot replace.

**Impact:** New module + 7 tests. `cycle.py` computes the posture each cycle, folds it into the approved plan, logs it as a risk event (so it is visible in the dashboard risk log and reconstructable from the ledger), and passes it to both modes. Verified firing live on the competition account: `[event] DERISK: Non-Farm Payrolls (Aug 2026) in 17.8h`.

---

## D-015 — Additive gold exposure + a News Agent, and raise the delta cap to $60k
**Date:** 2026-09-04 · **Status:** DECIDED (approved by Thomas) — extends D-011, does not replace it

**Decision:** three changes, all additive:

1. **Gold added to the baskets.** Specialist Mode now quotes `GLD` and `IAU` alongside SPY/QQQ/AAPL/NVDA/TSLA; Convexity Mode adds `GLD`.
2. **A News Agent** (`agent/news_agent.py`) reads gold-market headlines from Alpaca's news API, asks Featherless to classify them into an *uncertainty regime* (`calm` / `mixed` / `turbulent`), and uses that only to scale quote width (0.9x / 1.0x / 1.35x).
3. **`max_net_delta_dollars` raised $25,000 → $60,000.**

**Reasoning:**

*Gold, additively.* The team asked whether to pivot the whole agent to gold-only news trading. Rejected as a pivot (see Alternatives) but accepted as an addition, because the underlying instinct is sound: gold is genuinely uncorrelated with the equity indices, so it **diversifies** the book rather than concentrating it — which is the same logic as D-003. Verified live: GLD has 6,266 contracts with usable Greeks, IAU 1,301, GDX 2,347. IAU is a particularly good fit — one ATM put carries ~$3.8k of delta vs SPY's ~$34.8k, so it sits comfortably inside the Greeks caps.

*The News Agent is the one place this system forms a view — and even there it does not pick a direction.* Turbulent headlines make the agent charge **more** to provide liquidity; calm headlines less. A market maker does not need to know which way gold goes, only how nervous to be about being on the other side of a trade. This keeps the "AI reads the news" capability the team wanted without adopting the sentiment→direction framing that NewsFlow Trader already occupies and that is the weakest link in most competitors' chains. A test asserts `NewsRead` carries no directional field.

*The delta cap.* At SPY $773.63 a single ATM put carries ~$34,814 of delta, so a $25,000 book cap made the two most liquid underlyings **impossible to quote** — 41 of 86 risk events in the first live session were `clamped 1->0 (delta room=0)`. This is not a loosening of real risk: Specialist Mode delta-hedges every fill within the same cycle, and observed **post-hedge** net book delta ran under $200 all session (TSLA: option −$17,246 vs stock +$17,188 = −$58). The cap was gating entry on unhedged exposure that never persists.

**Alternatives considered:**
- **Full pivot to gold-only news-directional trading.** Rejected with ~19h to the deadline: it discards a working, live-validated system (55 tests, 69 real fills, three platform bugs already found and fixed); news→sentiment→direction is the most crowded lane in the field; a single asset is maximum variance, the opposite of D-003; and it would replace a differentiator nobody else has (inventory-managed two-sided quoting) with one a dozen teams built.
- **Adding GDX too.** Deferred — gold miners are equities with idiosyncratic risk, not a gold proxy, and each extra symbol costs a chain fetch against the free tier's 200 req/min.
- **Leaving the delta cap at $25k and shrinking quote size instead.** Does not help: the problem is one indivisible contract, not the number of them.

**Impact:** New module + 7 tests (55 passing). `cycle.py` applies the news multiplier before the event-calendar posture, so an event rule always wins. Also fixed while wiring this up: `_build_market_plan_context` summed `position_snapshots` across time, double-counting the same positions — it told the model the book was at $120,013 delta against its cap when the true figure was $48.

---

## Pending decisions (not yet made)

| # | Decision needed | Blocks | Owner |
|---|---|---|---|
| P-3 | Agent runtime language: Python vs TypeScript | — | ~~Thomas + devs~~ **Resolved by D-011/D-012: Python** (`alpaca-py` + the LLM provider SDKs) |
| P-4 | Buy Algo Trader Plus ($99) for OPRA data? | Strategy design | Thomas |
| P-5 | Public repo from day 1, or private-then-public? | — | This repo is already public; **resolved: public from day 1** |
| P-7 | Underlying basket confirmation (SPY/QQQ/AAPL/NVDA/TSLA for Specialist Mode; SPY/QQQ/IWM for Convexity Mode, from before D-011) | Live trading | Whoever runs the daemon — see `agent/config.py` `RiskConfig` |
| P-8 | Dev A / Dev B assignment to real people | Task board | Thomas |
| P-9 | Time-travel replay dashboard (D-012's biggest open gap) — who picks it up? | Presentation criterion | Team |
| P-10 | NFP event rule (T-027) — still not implemented regardless of concept | P&L risk on the Friday session | Whoever has bandwidth Wed/Thu |
