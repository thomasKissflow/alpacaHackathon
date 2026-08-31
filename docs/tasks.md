# Task Board

> **Last updated:** 2026-08-31
> **Owners:** `A` = Developer A (agent runtime) · `B` = Developer B (frontend & presentation) · `T` = Thomas (decisions/accounts) · `C` = Claude
> **Priority:** `P0` = blocks the deadline · `P1` = important · `P2` = nice to have
>
> ⚠️ Dev A and Dev B are not yet mapped to real people — see [project-overview.md](project-overview.md) Q1.
> **2026-08-31: concept + architecture are decided (D-011, D-012) and code is live in `agent/`/`dashboard/`/`tests/`.** Rows below are updated to reflect what's actually built vs. still open — see each row's Notes rather than assuming Stage labels still mean "not started."

---

## 🔴 BLOCKED / NEEDS DECISION

| ID | Task | Owner | Pri | Status |
|---|---|---|---|---|
| ~~T-101~~ | Lock the project concept | T | **P0** | ✅ **Resolved — D-011** |
| ~~T-102~~ | Approve the two-tier architecture amendment | T | **P0** | ✅ **Resolved — D-012** |
| T-103 | Assign Dev A / Dev B to real people | T | **P0** | Still open |
| T-104 | Decide: buy Algo Trader Plus ($99 OPRA) or engineer around free tier | T | P1 | Still open — current build runs on the free indicative feed |
| ~~T-105~~ | Decide: public repo from day 1? | T | P1 | ✅ Resolved — repo is public |
| ~~T-106~~ | Name the project | Team | P1 | ✅ Resolved — "The Specialist" (see D-011) |

---

## 📋 BACKLOG

### Stage 0 — Today (Sat 29 Aug) · everything here is P0

| ID | Task | Owner | Pri | Notes |
|---|---|---|---|---|
| T-001 | **Create brand-new Alpaca paper account, set balance to $100,000** | T | **P0** | R4/R5. Do not trade on it. Record account ID in `docs/credentials.md` (ID only, never keys) |
| T-002 | Create a **separate** throwaway paper account for development | T | **P0** | Prevents contaminating the judged account (D-010) |
| T-003 | **Claim Featherless $25 credits** with code `ALPACA26` | T | **P0** | First-come, first-served — do this before anything else |
| ~~T-004~~ | Install Alpaca CLI; verify auth; **validate a multi-leg (`mleg`) order via `--dry-run`** on the dev account | A | **P0** | ✅ **Validated live** — see D-013. Also surfaced two real Alpaca constraints (naked calls rejected, no simultaneous same-contract buy+sell) and 3 bugs, all fixed. Ran on a dev/sandbox account, not the competition account — see D-013's process note. |
| ~~T-005~~ | Verify option chain + snapshot greeks are returned on the free indicative feed for our candidate tickers | A | **P0** | ✅ **Validated live** — Greeks/IV populate correctly, only when bid/ask are both non-zero, exactly as [research.md](research.md) §1.4 documented |
| ~~T-006~~ | ~~Freeze the `state/` JSON contract~~ | A + B | **P0** | ✅ **Superseded by D-012**: the contract is now the SQLite schema in `agent/ledger.py` (orders/fills/hedges/risk_events/market_plans/postmortems/snapshots tables) + the exported shape in `agent/dashboard_export.py`. Frozen in the same sense — anyone building a new dashboard reads `data/dashboard.json`. |
| T-007 | Write a fixture so a new dashboard contributor can start without a live account | A | P1 | Not yet done as a checked-in fixture file — `agent/dashboard_export.py` needs a real (or seeded) `data/ledger.db` to produce `data/dashboard.json`. Easy fast-follow: a `scripts/seed_demo_ledger.py` was used to visually QA the dashboard during the build and could be checked in for this purpose. |
| ~~T-008~~ | ~~Repo scaffold: agent dir, dashboard dir, `.github/workflows`, `.gitignore`, README~~ | A | P1 | ✅ **Done** |
| T-009 | Register team on lablab.ai platform + join Discord | T | P1 | Required to participate |
| T-010 | Confirm ISM/ADP dates and any large-cap earnings in the window | C | P1 | [research.md](research.md) §5 marked UNVERIFIED |

### Stage 1 — Sun 30 Aug · agent live for Monday's open

> Concept changed (D-011) so several rows below are reframed from "VRP credit-spread agent" to "Specialist + Convexity Mode," but the underlying engineering task (basket selection, structure selection, sizing, risk gates, reconciliation, decision log, cron, kill switch) is the same shape and is **done in code**, pending live validation (T-004/T-005/T-021).

| ID | Task | Owner | Pri | Notes |
|---|---|---|---|---|
| ~~T-011~~ | Underlying basket selection + liquidity screen | A | **P0** | ✅ Done — `SPY/QQQ/AAPL/NVDA/TSLA` (Specialist), `SPY/QQQ/IWM` (Convexity) in `agent/config.py`. P-7: confirm this basket is still what we want. |
| ~~T-012~~ | Chain fetch + contract filtering (DTE 7–45, spread %, non-zero bid/ask) | A | **P0** | ✅ Done — `agent/specialist_mode.py::_pick_atm_contracts`, `agent/scanner.py` |
| ~~T-013~~ | IV vs realised-vol computation | A | **P0** | ✅ Done, reframed: Specialist Mode solves IV from live NBBO mid via a from-scratch Newton-Raphson solver (`agent/pricing.py`); Convexity Mode's IV-rank-vs-history is unchanged from the original design |
| ~~T-014~~ | Credit vertical structure selection + strike choice | A | **P0** | ✅ Done — `agent/strategy.py` (iron condor / bull put / bear call, unchanged design) |
| ~~T-015~~ | Deterministic position sizing + hard risk gates | A | **P0** | ✅ Done — `agent/risk_gate.py`: per-trade max loss, per-underlying notional cap, net delta/vega/gamma caps, daily circuit breaker, kill switch. 23+ unit tests, no live API calls. |
| T-016 | Multi-leg order submission via `alpaca api POST /v2/orders` with deterministic `--client-order-id` | A | **P0** | ⚠️ **Partially done.** Order submission works (`agent/execution.py`, via `alpaca-py`'s typed MLEG request). **Deterministic idempotent `client_order_id` is NOT yet set on any submitted order** — a retried/duplicated cycle could double-submit. Real gap, called out here rather than silently left out; needs an idempotency key design per mode (Convexity: keyed by date+underlying+structure; Specialist: less critical since it cancels/reposts every cycle by design, but hedge orders on fill should probably be keyed by fill id). |
| ~~T-017~~ | Position reconciliation ("never assume the last run happened") | A | **P0** | ✅ Done — `agent/reconcile.py`, runs first in every Convexity Mode cycle |
| ~~T-047~~ | **Naked-leg detection + auto-remediation** (complete or flatten an unpaired short leg) | A | **P0** | ✅ **Done** — `agent/reconcile.py::_flatten_naked_legs`, directly built in response to this exact finding ([research.md](research.md) §1.6). Flattens whatever leg IS held rather than blind-completing the missing one. 4 unit tests with mocked positions/orders. |
| ~~T-048~~ | Working-order management: marketable limits, cancel/re-price unfilled orders each run | A | **P0** | ✅ Done for both modes — Specialist Mode cancels/reposts every cycle by construction; Convexity Mode's stale (>30min) unfilled entries are cancelled by `agent/reconcile.py::_handle_unfilled_entry` |
| ~~T-018~~ | Decision log writer + state snapshot + git commit/push | A | **P0** | ✅ Done — `agent/ledger.py` (SQLite, superseding the originally-sketched per-run JSON files, see D-012) + `agent/logger.py` for the narrative feed |
| ~~T-019~~ | GitHub Actions workflow: cron at odd minutes + `workflow_dispatch` | A | **P0** | ✅ Done — `.github/workflows/trading-agent.yml`, 3x/day + manual dispatch. Note: Specialist Mode additionally needs `agent/daemon.py` running somewhere more continuously — cron alone is too sparse for two-sided quoting, see README "Running it for real." |
| ~~T-020~~ | Drawdown **kill switch** (flatten + halt + commit `HALTED`) | A | **P0** | ✅ Done — `python -m agent.kill_switch execute`, `agent/kill_switch.py` |
| T-021 | **Go-live smoke test on the competition account** | A + T | **P0** | ⏳ **Blocked on T-001.** The smoke test itself (equivalent of T-004/T-005) has been run and passed on a dev account — see D-013. What's left is purely: create the real competition account, then run `python -m agent.daemon --once` against it once to confirm. |
| ~~T-022~~ | Dashboard skeleton reading fixture JSON | B | P1 | ✅ Done, different stack than originally scoped (static vanilla JS + Chart.js instead of React/Vite/Tailwind/Recharts — see D-012). Visually verified end-to-end with synthetic ledger data. |
| T-023 | First build-in-public post (X + LinkedIn), tagging @lablabai + @AlpacaHQ | B | P1 | Still open — day 1 content slot may already be missed; post as soon as possible |

### Stage 2 — Mon–Tue · sophistication while it trades

| ID | Task | Owner | Pri | Notes |
|---|---|---|---|---|
| T-024 | Book-level greeks aggregation (net Δ / ν / Θ) | A | P1 | ✅ Done as **hard caps** (`agent/risk_gate.py`, `ledger.portfolio_greeks_now()`), reframed by D-011: this build uses aggregate Greeks as a *constraint on a market-making/premium-selling book*, not as the allocator that *drives trade selection* the way D-004's B1 envisioned (that's T-025 below, still open) |
| T-025 | Risk-budget allocator (trade selection driven by budget gaps) | A | P1 | ❌ **Not done** — the biggest conceptual gap vs. the original D-004 plan (see D-011 "what we're giving up"). Bridgeable: layer this onto Convexity Mode's structure selection using the same Greeks caps already computed. |
| T-026 | Regime classifier + playbook selection | A | P1 | Partial — the LLM MarketPlan step (`agent/llm_agent.py`) picks symbols/spread-width/mode-weights, which is a lighter version of the same instinct, but there's no explicit trend/chop/vol-expansion regime label |
| T-027 | Event calendar + **NFP rule** (reduce short gamma into Thu close) | A | **P0** | ❌ **Still not done.** Unchanged severity from the original finding — [research.md](research.md) §5 — NFP is Fri 4 Sep 08:30 ET regardless of which strategy concept is trading. This is probably the single highest-value task left. |
| ~~T-028~~ | Live book view: positions, greeks vs budget, equity curve | B | P1 | ✅ Done — `dashboard/` |
| T-029 | MCP server set up locally for research + demo | A | P1 | Still open — same D-007 rationale applies unchanged (CLI for the unattended loop, MCP for interactive research/demo) |

### Stage 3 — Tue–Wed · the glass box

| ID | Task | Owner | Pri | Notes |
|---|---|---|---|---|
| T-030 | Time-travel replay UI (scrub the week, see observed/considered/rejected/decided) | B | **P0** | ❌ **Not done — biggest open gap vs. the original plan** (see D-012). Current dashboard shows live/recent state, not a scrubbable timeline. The ledger already has every timestamped row a replay view needs; this is a UI task, not new data-collection work. |
| ~~T-031~~ | Risk panel (gates, caps, kill-switch, NFP countdown) | B | P1 | ✅ Mostly done — `dashboard/` has live Greeks-vs-caps gauges + the risk-gate event log; no NFP countdown yet (depends on T-027) |
| T-032 | Deploy the dashboard; capture the public **Application URL** | B | **P0** | Reframed by D-012: the dashboard is static (no build step), so **GitHub Pages** is the simpler deploy than Vercel — Settings → Pages → Deploy from branch → `/(root)`, then `<repo>/dashboard/`. Still not deployed yet; still a required submission field. |
| T-049 | Deterministic idempotent `client_order_id` on submitted orders | A | P1 | New — see T-016's note. Prevents a retried cron cycle from double-submitting the same entry. |
| T-033 | Responsive/mobile pass — judges may open it on a phone | B | P2 | |

### Stage 4 — Wed–Thu · sponsor integration & content

| ID | Task | Owner | Pri | Notes |
|---|---|---|---|---|
| T-034 | Featherless integration: regime labelling + red-team veto gate | A | P1 | Partner-prize eligibility |
| T-035 | "Desk Notes" — agent writes its own daily commentary | A | P1 | Feeds the social workstream (B16/D-009) |
| T-036 | Desk Notes surfaced in the dashboard | B | P2 | |
| T-037 | Offline playbook validation harness → numbers for the write-up | A | P2 | Evidence for criterion 4 |
| T-038 | Social posts 2–4 | B | P1 | Up to 5 total submitted |

### Stage 5 — Thu–Fri · submission

| ID | Task | Owner | Pri | Notes |
|---|---|---|---|---|
| T-039 | **One-page write-up**: AI logic, risk gates, Alpaca infrastructure | C + T | **P0** | Explicit requirement R7 |
| T-040 | Slide presentation | B | **P0** | Required field |
| T-041 | **Video presentation** | B | **P0** | Required field — allow 3h, it always overruns |
| T-042 | Cover image | B | **P0** | Required field |
| T-043 | Long + short description, tech/category tags | C | **P0** | Required fields |
| T-044 | Final social post (results) | B | P1 | 5th post |
| T-045 | **Submit** — incl. Alpaca account ID, repo URL, app URL, 5 social links | T | **P0** | Deadline Fri 4 Sep **20:30 IST** — submit by 18:00 IST |
| T-046 | Verify the agent's Friday NFP behaviour before the deadline | A | P1 | |

---

## 🚧 IN PROGRESS

| ID | Task | Owner | Started | Notes |
|---|---|---|---|---|
| T-000 | Hackathon analysis, research, documentation structure, idea generation | C | 2026-08-29 | Substantially complete |

---

## ✅ COMPLETED

| ID | Task | Owner | Done |
|---|---|---|---|
| T-000a | Analyse kickoff email + hackathon page; extract requirements, criteria, deadline | C | 2026-08-29 |
| T-000b | Research Alpaca CLI, MCP server, options API, data tiers and limits | C | 2026-08-29 |
| T-000c | Competitor analysis of 12 published submissions | C | 2026-08-29 |
| T-000d | Identify NFP (Fri 4 Sep 08:30 ET) inside the judging window | C | 2026-08-29 |
| T-000e | Create `docs/` structure and initial content | C | 2026-08-29 |
| T-000f | Generate 16 ideas; evaluate top 4; recommend | C | 2026-08-29 |

---

## Critical path

```
T-001/T-002 (accounts) ──► T-004/T-005 (CLI + data validation) ──► T-006/T-007 (contract)
                                                                        │
                          ┌─────────────────────────────────────────────┴──────────┐
                          ▼ Dev A                                          Dev B ▼
              T-011…T-020 (Stage 1 agent)                        T-022 (dashboard skeleton)
                          │
                          ▼
              ⏰ T-021 GO LIVE — Mon 31 Aug, before 19:00 IST  ◄── HARD GATE
                          │
              T-024…T-027 (Stage 2)                            T-030…T-032 (Stage 3)
                          └───────────────┬──────────────────────────────┘
                                          ▼
                            T-039…T-045 (submission) — Fri 4 Sep
```

**The single hard gate is T-021.** Everything before it is P0. If Stage 1 is not live before Monday's open, we lose a quarter of our judged P&L history and it cannot be recovered.
