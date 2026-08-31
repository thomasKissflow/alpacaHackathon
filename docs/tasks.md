# Task Board

> **Last updated:** 2026-08-29
> **Owners:** `A` = Developer A (agent runtime) · `B` = Developer B (frontend & presentation) · `T` = Thomas (decisions/accounts) · `C` = Claude
> **Priority:** `P0` = blocks the deadline · `P1` = important · `P2` = nice to have
>
> ⚠️ Dev A and Dev B are not yet mapped to real people — see [project-overview.md](project-overview.md) Q1.

---

## 🔴 BLOCKED / NEEDS DECISION

| ID | Task | Owner | Pri | Blocked by |
|---|---|---|---|---|
| T-101 | Lock the project concept | T | **P0** | Decision D-004 sign-off |
| T-102 | Approve the two-tier architecture amendment | T | **P0** | Decision D-006 sign-off |
| T-103 | Assign Dev A / Dev B to real people | T | **P0** | — |
| T-104 | Decide: buy Algo Trader Plus ($99 OPRA) or engineer around free tier | T | P1 | Depends on T-101 |
| T-105 | Decide: public repo from day 1? | T | P1 | — |
| T-106 | Name the project | Team | P1 | Depends on T-101 |

---

## 📋 BACKLOG

### Stage 0 — Today (Sat 29 Aug) · everything here is P0

| ID | Task | Owner | Pri | Notes |
|---|---|---|---|---|
| T-001 | **Create brand-new Alpaca paper account, set balance to $100,000** | T | **P0** | R4/R5. Do not trade on it. Record account ID in `docs/credentials.md` (ID only, never keys) |
| T-002 | Create a **separate** throwaway paper account for development | T | **P0** | Prevents contaminating the judged account (D-010) |
| T-003 | **Claim Featherless $25 credits** with code `ALPACA26` | T | **P0** | First-come, first-served — do this before anything else |
| T-004 | Install Alpaca CLI; verify auth; **validate a multi-leg (`mleg`) order via `--dry-run`** on the dev account | A | **P0** | Highest-uncertainty technical unknown — see [research.md](research.md) §1.1 |
| T-005 | Verify option chain + snapshot greeks are returned on the free indicative feed for our candidate tickers | A | **P0** | Confirms the strategy is buildable at all |
| T-006 | **Freeze the `state/` JSON contract** | A + B | **P0** | This is the parallelisation boundary ([architecture.md](architecture.md) §5) |
| T-007 | Write a fixture `state/latest.json` + 3 sample decision files so B can start immediately | A | **P0** | Unblocks B without waiting for the agent |
| T-008 | Repo scaffold: agent dir, dashboard dir, `.github/workflows`, `.gitignore`, README | A | P1 | **Awaiting explicit go-ahead to write code** |
| T-009 | Register team on lablab.ai platform + join Discord | T | P1 | Required to participate |
| T-010 | Confirm ISM/ADP dates and any large-cap earnings in the window | C | P1 | [research.md](research.md) §5 marked UNVERIFIED |

### Stage 1 — Sun 30 Aug · agent live for Monday's open

| ID | Task | Owner | Pri | Notes |
|---|---|---|---|---|
| T-011 | Underlying basket selection + liquidity screen | A | **P0** | 6–10 hyper-liquid names; IEX-only equity data constrains this |
| T-012 | Chain fetch + contract filtering (DTE 7–45, spread %, non-zero bid/ask) | A | **P0** | The bid/ask filter also guarantees greeks exist |
| T-013 | IV vs realised-vol computation | A | **P0** | The VRP signal |
| T-014 | Credit vertical structure selection + strike choice | A | **P0** | Defined risk only |
| T-015 | Deterministic position sizing + hard risk gates | A | **P0** | Per-trade max loss, per-book cap, concentration cap |
| T-016 | Multi-leg order submission via `alpaca api POST /v2/orders` with deterministic `--client-order-id` | A | **P0** | Idempotency is mandatory (cron may retry/drop) |
| T-017 | Position reconciliation ("never assume the last run happened") | A | **P0** | Self-healing loop |
| T-047 | **Naked-leg detection + auto-remediation** (complete or flatten an unpaired short leg) | A | **P0** | Paper partial-fills 10% at random — a half-filled spread is unbounded risk ([research.md](research.md) §1.6) |
| T-048 | Working-order management: marketable limits, cancel/re-price unfilled orders each run | A | **P0** | Paper fills only when marketable — otherwise the agent silently does nothing |
| T-018 | Decision log writer + state snapshot + git commit/push | A | **P0** | The audit trail |
| T-019 | GitHub Actions workflow: cron at odd minutes + `workflow_dispatch` | A | **P0** | Manual trigger from phone for overnight |
| T-020 | Drawdown **kill switch** (flatten + halt + commit `HALTED`) | A | **P0** | Non-negotiable before going live |
| T-021 | **Go-live smoke test on the competition account** | A + T | **P0** | The first real order must be intentional |
| T-022 | Dashboard skeleton reading fixture JSON | B | P1 | Runs in parallel from T-007 |
| T-023 | First build-in-public post (X + LinkedIn), tagging @lablabai + @AlpacaHQ | B | P1 | Day 1 content is the highest-engagement slot |

### Stage 2 — Mon–Tue · sophistication while it trades

| ID | Task | Owner | Pri | Notes |
|---|---|---|---|---|
| T-024 | Book-level greeks aggregation (net Δ / ν / Θ) | A | P1 | The core originality claim |
| T-025 | Risk-budget allocator (trade selection driven by budget gaps) | A | P1 | |
| T-026 | Regime classifier + playbook selection | A | P1 | LLM labels regime; deterministic code picks the structure |
| T-027 | Event calendar + **NFP rule** (reduce short gamma into Thu close) | A | **P0** | Fri 4 Sep 08:30 ET — see [research.md](research.md) §5 |
| T-028 | Live book view: positions, greeks vs budget, equity curve | B | P1 | |
| T-029 | MCP server set up locally for research + demo | A | P1 | D-007 |

### Stage 3 — Tue–Wed · the glass box

| ID | Task | Owner | Pri | Notes |
|---|---|---|---|---|
| T-030 | Time-travel replay UI (scrub the week, see observed/considered/rejected/decided) | B | **P0** | The presentation differentiator |
| T-031 | Risk panel (gates, caps, kill-switch, NFP countdown) | B | P1 | |
| T-032 | Deploy to Vercel; capture the public **Application URL** | B | **P0** | Required submission field |
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
