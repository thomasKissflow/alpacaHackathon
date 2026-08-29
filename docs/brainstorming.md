# Brainstorming Log

> **Rule of this file:** nothing gets deleted. Rejected ideas keep their reasoning, because "what we considered and why we dropped it" is itself a judging asset.
>
> **Status vocabulary:** `✅ Accepted` · `❌ Rejected` · `🔬 Needs Research` · `🔮 Future Scope` · `⏳ Under Consideration`

**Last updated:** 2026-08-29

---

## Part A — The strategic frame (read this before the ideas)

Three observations shape everything below.

**A1. P&L over 4.2 sessions is mostly noise.**
No options strategy has a statistically meaningful edge over four days. Anyone who wins purely on P&L got lucky. But P&L is still a judged criterion, so we must engineer the *distribution*: maximise P(modest positive) with a hard floor, rather than maximise E[P&L]. A defined-risk book that grinds out +0.5% to +2% with a capped downside is a far better contest asset than one with a 25% chance of +15% and a 40% chance of -20%.

**A2. This is a rank tournament, not a return-maximisation problem.**
Only the top 3 pay. But there are **five** criteria and four of them are fully under our control. The winning line is: *positive, explainable P&L* + dominate Technology Implementation, Creativity, Presentation. Betting the account to top the P&L leaderboard risks losing everything else too.

**A3. The abstention trap is the field's blind spot.**
Criterion 1 rewards P&L *"and how effectively the strategy performs through its trading activity."* Three of the twelve published competitors lead with "refuses to trade when no edge is proven." If they refuse, they have no activity and no P&L to judge. **We should be selective but always in the market** — a continuously-invested, risk-budgeted book with a steady trade cadence.

---

## Part B — Raw idea pool

### B1. Portfolio-Greeks Risk-Budget Desk
An agent whose core abstraction is not "signal → trade" but **"a risk budget → an allocation."** It maintains target ranges for the book's aggregate net delta, vega and theta, and every trade exists to move the book toward its target envelope. Diversified across 6–10 liquid underlyings.
**Status: ⏳ Under Consideration — top candidate.** Fully evaluated in Part C.

### B2. Volatility Risk Premium (VRP) Harvester
Systematically sells defined-risk premium (credit verticals / iron condors, 7–30 DTE) where implied vol is rich relative to trailing realised vol, on liquid underlyings. The oldest genuinely-positive-drift edge in options.
**Status: ⏳ Under Consideration — top candidate.** Fully evaluated in Part C.

### B3. Regime-Switching Strategy Playbook
The agent carries a *menu* of pre-validated, defined-risk options structures (credit vertical, debit vertical, iron condor, calendar, long strangle). A classifier reads the regime (trend / chop / vol-expansion / vol-crush / event-pending) and selects which playbook is live. The LLM's job is **regime classification and veto**, not price prediction — a legitimately good use of an LLM.
**Status: ⏳ Under Consideration — top candidate.** Fully evaluated in Part C.

### B4. Glass-Box / Time-Travel Audit Agent
The differentiator is the *artifact*, not the strategy: every decision the agent makes is written to an append-only, content-addressed decision log committed to git. The dashboard lets a judge scrub a timeline and see exactly what the agent saw, what it considered, what it rejected, and why — at any moment in the past week.
**Status: ⏳ Under Consideration — best as a *layer* on B1/B2/B3, not standalone.** Fully evaluated in Part C.

### B5. Event-Aware Agent (NFP-conscious)
The agent holds a calendar of scheduled macro events and changes behaviour around them: widens strikes, cuts size, closes short gamma before the Fri 4 Sep NFP print, or deliberately buys convexity into it.
**Status: ✅ Accepted as a feature** of whatever we build. Not a standalone project. Zero of the 12 published competitors mention event awareness, and NFP lands 2.5h before the deadline — this is free differentiation and a great demo beat.

### B6. Cross-Sectional IV Dispersion
Sell rich-IV names against cheap-IV names in a sector basket; capture the index-vs-single-name vol spread.
**Status: 🔮 Future Scope.** Genuinely elegant and genuinely original. But it needs a clean IV surface across many names, and our free tier gives indicative options data with a 200 req/min cap and greeks that silently go missing on wide-spread contracts. Too much data risk for a 2-day build.

### B7. News/Filing-Driven Options Agent
LLM reads headlines/filings, scores sentiment and surprise, buys directional options.
**Status: ❌ Rejected.** NewsFlow Trader already submitted essentially this. Sentiment→direction is also the weakest link in the chain — it is the part most likely to be a coin flip, and we would be buying premium (negative theta) into a 4-day window. High variance, low originality, crowded.

### B8. Multi-Agent Adversarial Debate Fund
Bull agent vs bear agent vs risk agent argue; a judge agent decides.
**Status: ❌ Rejected.** AlphaSwarm Sovereign Capital has planted this flag hard (adversarial dialectic debate + chart vision + 1,000-path Monte Carlo). Competing head-on with a more-elaborate version of someone's headline feature is a losing framing. Also: LLM debate adds token cost and latency without adding edge. *We can still use a single adversarial "red team" check as a cheap internal gate — see B14.*

### B9. 0DTE Scalping Agent
Trade same-day-expiry SPY options intraday.
**Status: ❌ Rejected — technically blocked.** Alpaca cannot compute greeks or IV for 0DTE contracts (days-to-expiry sits in the Black-Scholes denominator → division by zero). We would also be trading on 15-minute-stale data with a cron that drifts up to 30 minutes. This is the single clearest "obvious idea that the constraints kill." Documented in [research.md](research.md) §1.4.

### B10. Backtest-First Research Agent
Agent generates hypotheses, backtests them, only trades what validates out-of-sample.
**Status: ❌ Rejected as the headline.** SPY Sentinel AI and Odysseus both occupy this space. Worse, it walks straight into the abstention trap (A3) and burns our scarcest resource — trading days — on research. **However:** a *lightweight* offline validation of our chosen playbook is worth doing as evidence for the write-up. Reframed as B15.

### B11. Copy/Mirror Agent (follow unusual options activity)
Detect unusual options volume and piggyback.
**Status: ❌ Rejected.** Requires OPRA-quality volume/open-interest data we do not have on the free tier (indicative feed), and "unusual activity" screening on IEX-only equity data is unreliable. Also thin on originality.

### B12. Crypto+Options Cross-Asset Agent
Use Alpaca's 24/7 crypto to trade around the clock and hedge with options.
**Status: 🔮 Future Scope.** Attractive because crypto trades over the weekend, when equity markets are shut — it would extend our tiny track record. But R3 requires options to be central, crypto options are not offered, and the linkage would be contrived. Revisit only if we need weekend activity to show.

### B13. Options Income Ladder / Wheel
Systematic covered calls and cash-secured puts on a held equity portfolio.
**Status: 🔬 Needs Research.** Very reliable, very legible, genuinely "portfolio income" (a phrase the challenge text explicitly uses). But: the wheel's income over 4 days is trivially small (~0.2%), and it needs meaningful equity exposure, which reintroduces raw directional risk. Possible *component* of B1's book rather than the whole thesis.

### B14. Pre-Trade Red-Team Gate
Before any order, a second cheap model argues the *opposite* case and must fail to find a disqualifying objection. Runs on Featherless (cheap, high volume).
**Status: ✅ Accepted as a component.** Gives Featherless a genuine, defensible role (partner-prize eligibility), costs almost nothing, and produces excellent decision-log content for the glass-box UI. Not a headline feature — AlphaSwarm owns the "debate" framing — but as a *gate* it is cheap and honest.

### B15. Offline Playbook Validation Harness
Not a live research agent (B10), just a one-off script that replays our chosen structures over historical data to produce the win-rate/expectancy numbers we cite in the write-up and video.
**Status: ✅ Accepted as evidence work.** Low effort, high presentation value. "Here is why we expected this distribution" is exactly what criterion 4 rewards. ⚠️ Constrained by free-tier historical options data — may have to validate the *underlying* signal rather than full option P&L.

### B16. "Desk Notes" — the agent writes its own daily commentary
Each session the agent publishes a short, human-readable note: what it saw, what it did, what it is worried about. Auto-posted as the build-in-public content.
**Status: ✅ Accepted.** This is the sleeper idea. It (a) makes the agent feel alive in the demo, (b) generates the social content for the $500 Social Engagement prize *as a by-product of the agent running*, and (c) is genuinely novel — no competitor is doing agent-authored public commentary. Very low effort on top of a decision log.

---

## Part C — Full evaluation of the top candidates

### 🥇 Candidate 1 — B1+B2+B3 fused: **"An autonomous options desk with a risk budget"**

The three top ideas are not really competitors; they are the three layers of one coherent system. Evaluating the fusion.

> **One-line pitch:** An autonomous agent that runs a *diversified options book* to a portfolio-level greeks budget — selecting defined-risk structures from a regime-matched playbook, harvesting volatility risk premium, and de-risking around scheduled macro events — with every decision replayable.

**Problem**
Retail options automation is per-trade: "signal fires → buy a spread → set a stop." Real options desks do not think that way; they manage a *book* against aggregate risk limits. Nobody automates that for retail, and — per [research.md](research.md) §2 — none of the 12 published competitors do it either.

**Target users**
Judges (it is visibly more sophisticated than the field); working retail traders who cannot watch the screen; Alpaca (it exercises the deep end of their options API).

**Why it is interesting to judges**
- It is the only entry that would manage **net delta / vega / theta at the book level** — a genuine "wow, that's what a real desk does" moment.
- It sidesteps every crowded framing (not SPY-only, not "risk gates", not "refuses to trade", not debate).
- Diversification across 6–10 underlyings *mechanically reduces the variance of our 4-day P&L*, which is the smartest possible response to A1.
- VRP is a real, documented, positive-drift edge — we can explain *why* we expect to make money without hand-waving.

**Technical complexity: Medium-High**
Chain fetching + IV-vs-RV computation + structure selection + mleg order construction + book-level greeks aggregation + reconciliation loop. The greeks aggregation is the genuinely novel part and also the riskiest.

**Demo impact: High**
A live book with a greeks gauge moving toward target, positions across multiple tickers, and a timeline you can scrub. Far more visually interesting than a single SPY signal.

**Feasibility (2 devs, ~2 days to live): Medium** ⚠️
This is the honest risk. The full vision is not buildable by Sunday. **Mitigation: ship it in two stages** — a correct, simple VRP credit-spread agent live for Monday's open (Stage 1), then layer the portfolio-greeks allocator on Mon–Wed while it trades (Stage 2). The account keeps accumulating P&L while we build the sophistication.

**Risks**
| Risk | Mitigation |
|---|---|
| Short premium + NFP gap on the final morning | B5 event rule: flatten/reduce short gamma into Thu close |
| Missing greeks on wide-spread contracts | Filter for quote quality; fall back to our own BS calc |
| Over-scope → not live by Monday | Hard stage gate; Stage 1 must be dumb and correct |
| Credit spreads have a fat left tail (many small wins, rare big loss) | Defined-risk structures only; hard per-trade and per-book max loss; diversify |
| 200 req/min | One `option chain` call per underlying, cached |

**APIs needed**
Alpaca Trading API + Market Data API (options chain/snapshot), Alpaca **CLI** (execution loop, R2), Alpaca **MCP** (research surface), Featherless (regime labelling + red-team gate + desk notes), GitHub Actions (scheduler), Vercel/GH Pages (dashboard).

**Recommended team split**
- **Dev A — "must be live Monday":** CLI integration, mleg order construction, position reconciliation, risk gates, scheduler, state/decision log format.
- **Dev B — "judged Friday":** dashboard + replay UI, deployment, cover image, slides, video, write-up, social/desk-notes pipeline.

---

### 🥈 Candidate 2 — B2 alone: **Pure VRP Credit-Spread Harvester**

**Problem** Implied vol is systematically richer than realised vol; retail has no automated, risk-managed way to harvest it.
**Why interesting** Cleanest, most defensible "why this makes money" story of any idea here. Honest and rigorous.
**Complexity: Low-Medium.** **Demo impact: Medium** — it is a table of credit spreads; visually plainer.
**Feasibility: High** ✅ — comfortably live by Monday.
**Risks** Less original (Options Sniper/AEGIS-Q are adjacent); fat left tail into NFP.
**Verdict:** This *is* Stage 1 of Candidate 1. Recommend building it as such rather than choosing between them.

---

### 🥉 Candidate 3 — B4: **Glass-Box Replayable Agent**

**Problem** Nobody trusts an AI trading agent because nobody can see why it did what it did.
**Why interesting** Directly serves criterion 4 (Presentation & Execution: *"demonstrates the agent in action, and presents the reasoning"*). A judge with 4 minutes can *audit* us instead of taking our word.
**Complexity: Low-Medium.** **Demo impact: Very High.** **Feasibility: High** ✅ — and it is almost entirely frontend, which fits the team's stated preference perfectly.
**Risks** Zero trading substance on its own; Vega already claims reproducibility (though as a *claim*, not a UI).
**Verdict: ✅ Accept as the presentation layer of Candidate 1.** It is what converts a good agent into a winning submission, and it is the natural home for Dev B.

---

### Candidate 4 — B5: **Event-Aware / NFP Agent** (as a standalone)

**Complexity: Low. Demo impact: High. Feasibility: High. Originality: High (unclaimed).**
**Risk:** As a *standalone* thesis it is a single-event bet — a coin flip on one print, on the last morning, with our whole P&L riding on it. Unacceptable variance.
**Verdict: ✅ Accept as a feature (B5), ❌ reject as the thesis.**

---

## Part D — Recommendation

**Build Candidate 1, staged, with B4 as the presentation layer and B5/B14/B16 as accepted features.**

Working title placeholder: *(to be named — naming session pending)*

| Stage | By when | Content |
|---|---|---|
| **Stage 0** | Today, Sat 29 Aug | New paper account ($100k), Featherless credits, repo scaffold, CLI auth + `--dry-run` mleg validation |
| **Stage 1** | Sun 30 Aug EOD | Simple, correct VRP credit-spread agent trading a diversified basket. Idempotent, self-healing, hard risk caps. **Must be live for Mon open.** |
| **Stage 2** | Mon–Tue | Portfolio-greeks budget allocator; regime playbook selection; event calendar (NFP) |
| **Stage 3** | Tue–Wed | Glass-box dashboard + replay UI, deployed |
| **Stage 4** | Wed–Thu | Featherless red-team gate + desk notes; social posts; validation harness |
| **Stage 5** | Thu–Fri | Video, slides, cover image, write-up, submission. NFP event handling live. |

**Why this and not something flashier:** the field already contains six competent SPY-signal agents. It does not contain a book-level risk manager, it does not contain event awareness, and it does not contain an auditable replay. Those three are achievable, differentiated, and — crucially — the first one also *reduces our P&L variance*, which is the only rational response to a 4-day judging window.

---

## Part E — Naming candidates (parking lot)
`Theta Desk` · `Vega Budget` (⚠️ collides with competitor "Vega") · `Ledger` · `Quorum` · `Nightshift` (plays on it trading while we sleep in IST) · `Blackboard` · `The Book` · `Overwatch`
**Status: ⏳ open.** `Nightshift` is the most distinctive and tells the IST-timezone story, which is genuinely charming build-in-public content.

---

## Part F — Rejected ideas graveyard (kept deliberately)

| Idea | Status | One-line reason |
|---|---|---|
| B7 News-driven options | ❌ Rejected | Crowded (NewsFlow); sentiment→direction is a coin flip; long premium bleeds |
| B8 Multi-agent debate | ❌ Rejected | AlphaSwarm owns it; adds cost, not edge |
| B9 0DTE scalping | ❌ Rejected | **Blocked**: Alpaca cannot compute 0DTE greeks; 15-min stale data; cron drift |
| B10 Live backtest-first research agent | ❌ Rejected | Crowded (Sentinel, Odysseus); walks into the abstention trap |
| B11 Unusual options activity | ❌ Rejected | Needs OPRA data we don't have |
| B6 IV dispersion | 🔮 Future | Beautiful, but too much data risk for a 2-day build |
| B12 Crypto cross-asset | 🔮 Future | Contrived under R3; no crypto options |
| B13 Wheel / income ladder | 🔬 Needs Research | Income too small over 4 days; possible book component |
