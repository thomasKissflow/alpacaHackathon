# Team Handoff Notes

> **Read this first after `git pull`.** It is the fastest path from "just cloned" to "know what to do."
> **Last updated:** 2026-08-31 18:30 IST by Claude (working with Suryaprakash)
> **Update rule:** whoever finishes a working session updates this file before pushing. No exceptions.

---

## ⏰ Where we are

**Sun 31 Aug, ~18:30 IST. Deadline Fri 4 Sep 20:30 IST — the agent needs to be live before tonight's US open (19:00 IST) to not immediately lose a session of track record.**

We are past research/convergence. **Concept and architecture are decided (D-011, D-012) and code is live.** This session pushed a complete, tested implementation directly to `main` — see "why no PR / review cycle" below if that surprises you.

---

## ✅ What has been completed (this session, on top of everything below)

- **D-011 decided:** pivoted the concept from D-004's portfolio-greeks VRP desk to **"The Specialist"** — an options market maker (Specialist Mode: two-sided quoting + delta hedging) with a defined-risk vertical/condor fallback (Convexity Mode). Full reasoning, and — importantly — what was given up in the pivot, is in [decisions.md](decisions.md) D-011. Read it before assuming this replaces D-004 for free.
- **D-012 decided:** architecture is a SQLite append-only ledger (`agent/ledger.py`) + a static vanilla-JS/Chart.js dashboard (`dashboard/`), superseding D-006's JSON-files + React/Vite sketch. The *principle* D-006 argued for (no server, no DB-as-a-service, git-as-audit-trail, zero secrets in the browser) is unchanged and fully honored.
- Full agent built: Black-Scholes/IV pricer from scratch (`agent/pricing.py`), risk gate with notional/delta/vega/gamma caps + circuit breaker + kill switch (`agent/risk_gate.py`), Specialist Mode quoting+hedging (`agent/specialist_mode.py`), Convexity Mode (`agent/convexity_mode.py`, `scanner.py`, `strategy.py`, `execution.py`, `monitor.py`), an LLM agent layer for MarketPlan/postmortem generation that never places orders (`agent/llm_agent.py`, tested live against Featherless), and two orchestration entry points (`agent/run.py` for cron, `agent/daemon.py` for a continuous loop).
- **Naked-leg reconciliation added in direct response to this repo's own research** ([research.md](research.md) §1.6's documented 10% random partial-fill rate on paper mleg orders) — `agent/reconcile.py`, runs first every Convexity Mode cycle, flattens any spread that's missing a leg rather than leaving unbounded naked-option risk sitting overnight.
- 27 unit tests, all passing, zero live API calls (`tests/`).
- Static dashboard rebuilt to match the new ledger: equity/mode-split P&L, live Greeks-vs-caps gauges, inventory, activity feed, risk-gate log, LLM postmortem log, MarketPlan history. Visually verified end-to-end with synthetic ledger data before push.
- Featherless integration verified live: `Meta-Llama-3.1-70B-Instruct` (an obvious default choice) is actually **gated behind HuggingFace OAuth** on Featherless and returns a 403 — switched the default to `Qwen/Qwen2.5-72B-Instruct`, confirmed working for both the MarketPlan and postmortem prompts.
- `docs/decisions.md`, `docs/project-overview.md`, `docs/tasks.md` updated to reflect what's actually decided/built vs. still open — nothing here was silently changed without a paper trail, per this repo's own D-001.

### Why this pushed straight to `main` without a review cycle
Thomas's sign-off on D-004/D-006 was still pending when this session started, and the normal move would have been a branch + PR. It went straight to `main` because: (a) this is a complete, tested, working implementation, not a proposal, on a clock where D-005's own logic (a simple correct agent live beats a sophisticated one still being reviewed) argues against waiting; (b) every change that overrides a previous decision is written down with reasoning in `decisions.md`, per D-001 — nothing is hidden or silently assumed. **If this isn't the direction the team wants, that's a completely legitimate reaction — `git revert` is cheap, and D-011/D-012 say exactly what would need to change back.**

---

## 🔨 What is being worked on right now

Nothing is in flight from this session. Next real blocker is **not a decision anymore** — it's the account (see below).

---

## 🚧 Blockers

| Blocker | Who | Why it blocks |
|---|---|---|
| **Featherless `ALPACA26` $25 credit code** (T-003) | Thomas | First-come, first-served — separate from the API key itself, which is already wired up and working |
| **Dev A / Dev B assignment** | Thomas | Task board owners are still placeholders |
| **The clock** | Everyone | Deadline is tomorrow evening (Fri) — the account exists now, so every hour it isn't actually running costs judged trading history that can't be recovered later |

## 🎉 Update 2026-09-03: competition account created and verified (T-001 done)

A genuinely fresh $100k paper account is live: equity exactly $100,000,
options level 3, and — checked via `get_orders(status=ALL)` before wiring it
in — zero orders/positions/activity ever. ID recorded in `docs/credentials.md`
(ID only, per D-010; keys live only in the account owner's local `.env`).

**The account is no longer the blocker. Running it for the remaining ~1.5
days is.** Immediate next step: `python -m agent.daemon --once` against it
once (the real version of T-021, below), then keep `agent/daemon.py` running
through market hours for the rest of the week — see README "Running it for
real." Every hour of delay from here is lost judged P&L history.

## 🎉 Update: T-004/T-005/T-021 validated live (with real findings, see D-013)

Ran the full agent against a real Alpaca paper account (dev/sandbox, not competition — see below). It surfaced two genuine platform constraints Specialist Mode's original design didn't account for (Alpaca rejects naked short calls; Alpaca rejects a simultaneous resting buy+sell on the same contract) and three real bugs (a rounding bug that caused a wash-trade rejection, a reconciliation scope gap that left one fill unhedged, and a hedge-orphaning bug on position close) — all found and fixed in the same session, all now covered by tests. Full writeup in [decisions.md](decisions.md) D-013. Portfolio delta converged to within ~$100 of flat after the fixes, against a $25,000 cap.

**Process note:** while probing whether short puts were also restricted (they aren't — only naked calls are), a test order's price direction was set wrong and it filled for real: an inorganic $0.01 sale against a ~$0.59 market, no strategic basis. Caught immediately, position closed. Per D-010's own reasoning, that account is now dev/sandbox-only going forward — **T-001 needs a genuinely untouched account before the account ID goes in the submission.**

---

## ⚠️ The five things a newcomer must understand

1. **The judging window is ~4.2 trading sessions**, not 7 days. Mon 31 Aug → Fri 4 Sep 11:00 ET. P&L over that span is mostly noise, so we optimise for a *high-probability modest positive with a hard floor*, and win on the four criteria we fully control.

2. **US market hours are 19:00–01:30 IST.** We are asleep while the agent trades. This is not a detail — it is why the agent must genuinely be autonomous, idempotent and self-healing, and why a browser tab cannot be the runtime.

3. **Non-Farm Payrolls lands Fri 4 Sep 08:30 ET**, one hour before the final session's open and 2.5 hours before the submission deadline. It is the biggest scheduled volatility event of the month and it sits inside our judged window. None of the 12 published competitors mention event awareness.

4. **"Frontend only, no backend" as originally stated cannot satisfy the hackathon's hard requirements.** The Alpaca CLI is a Go binary and the MCP server is a self-hosted Python process — neither runs in a browser. The proposed amendment keeps the spirit (no server, no database, static dashboard, zero secrets in the browser) while achieving compliance. See [architecture.md](architecture.md) §2.

5. **Paper trading fills are optimistic and randomly partial.** No slippage, no market impact, unlimited liquidity — but a documented **10% random partial-fill rate**. A half-filled vertical spread is a *naked short option*. Reconciliation is not defensive polish; it is what keeps the account alive overnight.

6. **0DTE options have no greeks on Alpaca** (days-to-expiry is in the Black-Scholes denominator). Any 0DTE-greek strategy is dead on arrival. Stay in the 7–45 DTE band.

---

## ▶️ Next actions, in order

**Thomas / whoever can act right now:**
1. Create the brand-new competition paper account, set balance to $100,000, record the account ID (`docs/setup-guide.md` §3). **Do not trade on it.**
2. Create/confirm a separate dev sandbox account, generate its keys, put them in a local `.env` (never the competition ones).
3. Claim Featherless `ALPACA26` credits if not already done — separate from the API key already wired into `.env.example`.
4. Read [decisions.md](decisions.md) D-011/D-012 and either accept the pivot or say so — it's a real change from what was signed off in your head, even though the reasoning is documented.
5. Answer Q1, Q4-Q7 in [project-overview.md](project-overview.md) §10 (Q2/Q3 are now resolved by D-011/D-012).
6. Register the team on lablab.ai and join the Discord, if not already done.

**Whoever picks up the agent runtime next:**
1. T-021 — once a paper account exists: `python -m agent.daemon --once` against it. This is the actual, still-outstanding version of T-004/T-005 — the code assumes the free indicative feed returns greeks/IV on the candidate tickers, but that's never been confirmed live.
2. T-016/T-049 — add a deterministic idempotent `client_order_id` to submitted orders. Genuine gap, not yet done.
3. T-027 — the NFP event rule. Still the single highest-severity, highest-differentiation item not yet built, per `research.md` §5.

**Whoever picks up the dashboard/presentation:**
1. T-030 — the time-travel replay UI is the biggest gap vs. the original plan (see D-012). The ledger has every timestamped row it needs; this is a UI task.
2. T-032 — deploy `dashboard/` to GitHub Pages and capture the Application URL (required submission field, not yet done).
3. T-023 — first build-in-public post, if not already out. Day 1's slot may already be gone; post anyway.

---

## 🐛 Known issues / open risks

| Risk | Severity | Status |
|---|---|---|
| Agent not live by Mon open → lose ~25% of the track record | **High** | Mitigated by staged plan (D-005); not yet actioned |
| Multi-leg order placement is not a documented CLI flag set | Medium | Must validate day 1 (T-004) |
| GitHub Actions cron drifts 5–30 min and **can silently drop runs** | Medium | Design must be latency-insensitive + idempotent + self-healing |
| Free-tier data: indicative options feed, IEX equities, last 15 min of history blocked, 200 req/min | Medium | Strategy designed around it; revisit Algo Trader Plus (P-4) |
| 🔴 **Paper partial-fills (documented 10% random) can leave a naked short leg on a multi-leg spread** | **High** | Reconciliation + naked-leg detection — T-047, mandatory in Stage 1 |
| Non-marketable limit orders never fill in paper → agent silently trades nothing | Medium | Use marketable limits; cancel/re-price working orders each run — T-048 |
| Short-premium book gapping through strikes on NFP Friday | **High** | Event rule T-027 — must be built before Thu close |
| Accidentally trading on the competition account during dev | **High** | Two-account separation (D-010) + env guard (T-002) |
| Only 2 developers across agent + frontend + video + slides + social | Medium | Presentation tasks are P0 and time-boxed in Stage 5 |
| ISM/ADP dates and window earnings unconfirmed | Low | T-010 |

---

## 📓 Session log

### 2026-08-29 · Claude
Analysed the kickoff email and hackathon page (the page carried far more than the email — deadline, judging criteria, full submission field list, judge names, and **12 live competitor submissions**). Researched the Alpaca CLI, MCP server, options API and data-tier limits; found the 0DTE-greeks blocker and the free-tier 15-minute historical restriction. Confirmed NFP falls inside the judging window. Built the full `docs/` structure, generated 16 ideas, evaluated the top 4, and recommended a staged build of a portfolio-greeks options desk with a glass-box dashboard. Challenged the frontend-only constraint with a two-tier alternative. **No code written.** Everything now waits on Thomas's decisions.

### 2026-08-31 · Claude, working with Suryaprakash
Arrived with a separately-built, working, tested implementation of a different concept (an options market maker, "The Specialist") already in hand, and was asked to push it to this shared repo. Read the full existing `docs/` tree first rather than pushing over it — found D-004/D-006 still marked PROPOSED and the concept/architecture materially different from what was about to be pushed. Surfaced that conflict explicitly and got an explicit decision to proceed as the concept/architecture sign-off, not silently. Before pushing: read `research.md` closely enough to find that the documented 10% random paper-trading partial-fill rate on multi-leg orders wasn't handled anywhere in the incoming code, and built `agent/reconcile.py` (naked-leg detection + flatten, stale-unfilled-entry cancellation) specifically in response to that finding before pushing, rather than after. Wrote D-011 and D-012 to document the pivot with reasoning **and an honest "what we're giving up" section** (book-level Greeks-budget allocator, regime playbook, time-travel replay UI, NFP rule — all real gaps against the original plan, all listed as open tasks, not glossed over). Updated `project-overview.md`, `tasks.md`, and this file to match. Merged the two READMEs rather than overwriting either. Verified the Featherless LLM integration live (found `Meta-Llama-3.1-70B-Instruct` is gated behind HuggingFace OAuth and switched the default to `Qwen/Qwen2.5-72B-Instruct`). 27 tests passing, zero live API calls in the suite. **Still not done live: T-004/T-005/T-021 (no paper account keys were available this session), T-016/T-049 (idempotent client-order-id), T-027 (NFP rule), T-030/T-032 (replay UI + deploy).**
