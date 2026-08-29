# Architecture Notes

> **Last updated:** 2026-08-29
> **Status:** Proposed — awaiting sign-off on the constraint challenge in §2.

---

## 1. Constraints as originally stated

From the project kickoff:
- Frontend only
- No custom backend
- API-driven architecture
- Git workflow, Claude Code assisted
- 2 developers working in parallel

---

## 2. ⚠️ Constraint Challenge — "frontend only, no backend" cannot satisfy this hackathon

I was asked to challenge assumptions where warranted. This one has to be challenged, because three of the hard requirements break against it.

### 2.1 Why it breaks

**(a) R1 "Autonomous" requires unattended execution.**
US market hours are **19:00–01:30 IST**. A browser tab is not a runtime: it requires an open laptop, an awake machine, a focused tab (browsers throttle timers in background tabs), and no network blip for six and a half hours a night, five nights running. "Autonomous" that depends on a human keeping a tab open is not autonomous, and judges will ask.

**(b) R2 "MCP server or CLI" is not browser-executable.**
- The Alpaca **CLI** is a compiled Go binary. It cannot run in a browser.
- The Alpaca **MCP server** is a Python FastMCP process, self-hosted only (Alpaca publishes no hosted remote MCP server), and it runs *inside an MCP client*, not in a page.

There is no reading of R2 that a pure browser app satisfies. This is not a preference — it is a compliance failure.

**(c) Secrets.**
Alpaca does allow CORS, so a browser *can* call the Trading API. But any key shipped to a browser is public. We are required (R6) to **publish our paper account ID**. Publishing the account ID *and* exposing its keys means any observer can trade — or deliberately destroy — the account we are being judged on. This is a live sabotage vector, not a theoretical one.

### 2.2 What I recommend instead — and why it preserves the intent

The spirit of "frontend only, no custom backend" is: *don't build and operate a bespoke application server.* We can honour that completely.

> **We build no server. We build a scheduled job and a static site.**

- **No API server.** Nothing listens on a port. Nothing to deploy, scale, secure or keep up.
- **No database.** State lives in versioned JSON files in the git repo.
- **The "backend" is a cron-triggered script** that runs for ~30 seconds, does its work through the Alpaca CLI, commits its output, and exits.
- **The frontend is 100% static** — it reads committed JSON. It never holds a secret, never calls Alpaca, and can be hosted on GitHub Pages or Vercel free tier.

That is *less* operational surface than a typical "frontend-only + third-party APIs" app, not more. And it keeps Dev B's work entirely in the frontend, as intended.

**Decision needed from Thomas — see [project-overview.md](project-overview.md) Q3.** Everything below assumes this is accepted.

---

## 3. Proposed system design

```
┌──────────────────────────────────────────────────────────────────────┐
│  TIER 1 — AGENT RUNTIME  (scheduled, unattended, holds all secrets)   │
│                                                                       │
│   GitHub Actions cron  ──►  agent run (~30s)                          │
│   (:07 / :23 past hour,          │                                    │
│    dodging the stampede)         │                                    │
│                                  ▼                                    │
│        ┌─────────────────────────────────────────────┐               │
│        │ 1. OBSERVE   alpaca clock / calendar        │               │
│        │              alpaca account get             │               │
│        │              alpaca position list           │               │
│        │              alpaca data option chain ...   │               │
│        ├─────────────────────────────────────────────┤               │
│        │ 2. RECONCILE  actual book vs intended state │               │
│        │               (self-healing: never assume   │               │
│        │                the last run succeeded)      │               │
│        ├─────────────────────────────────────────────┤               │
│        │ 3. ORIENT     regime classify · IV vs RV    │               │
│        │               event calendar (NFP)          │               │
│        │               ── LLM: label + veto ──       │               │
│        ├─────────────────────────────────────────────┤               │
│        │ 4. DECIDE     playbook select → structure   │               │
│        │               size vs PORTFOLIO GREEKS      │               │
│        │               BUDGET (net Δ / ν / Θ)        │               │
│        ├─────────────────────────────────────────────┤               │
│        │ 5. GATE       deterministic risk gates      │               │
│        │               + Featherless red-team check  │               │
│        ├─────────────────────────────────────────────┤               │
│        │ 6. ACT        alpaca order submit           │               │
│        │               --client-order-id <det. key>  │               │
│        │               alpaca api POST /v2/orders    │               │
│        │                 (multi-leg "mleg")          │               │
│        ├─────────────────────────────────────────────┤               │
│        │ 7. RECORD     append decision to log        │               │
│        │               write state snapshot          │               │
│        │               git commit && push            │               │
│        └─────────────────────────────────────────────┘               │
│                                  │                                    │
│   Secrets: GitHub Actions Secrets (ALPACA_API_KEY, ALPACA_SECRET_KEY, │
│            FEATHERLESS_API_KEY). Never leave the runner.              │
└──────────────────────────────────┼───────────────────────────────────┘
                                   │  commits JSON
                                   ▼
                    ┌──────────────────────────────┐
                    │  git repo = state + audit log │
                    │  state/latest.json            │
                    │  state/decisions/*.json       │
                    │  state/equity.json            │
                    └──────────────┬───────────────┘
                                   │  build trigger
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│  TIER 2 — GLASS-BOX DASHBOARD  (100% static, zero secrets)            │
│  Vite + React + Tailwind + Recharts, on Vercel / GH Pages            │
│                                                                       │
│   · Live book: positions, per-leg greeks, aggregate Δ/ν/Θ vs budget   │
│   · Equity curve since inception                                      │
│   · ⏪ TIME-TRAVEL REPLAY: scrub the week, see what the agent saw,     │
│      what it considered, what it rejected, and its stated reasoning   │
│   · Desk Notes: the agent's own daily commentary                      │
│   · Risk panel: gates, caps, kill-switch state, NFP countdown         │
└──────────────────────────────────────────────────────────────────────┘
```

### 3.1 The key architectural idea

**The git repository is the agent's memory, its state store, and its audit trail — all three.**

Every run commits what it saw and why it acted. That single choice buys us:
- **No database, no backend** — honours the original constraint.
- **A tamper-evident audit trail** — commit history is timestamped and immutable-ish. This is the substance behind the "glass box" claim, not a marketing line.
- **A free replay data source** for the dashboard.
- **Trivial debugging** — `git log` *is* the agent's diary.
- **Judge-legible** — a judge can read the decision history in the public repo without running anything.

I have not seen this framing in any of the 12 published competitors. It is genuinely original and it falls straight out of the constraints we were given.

---

## 4. Frontend architecture

| Concern | Decision | Reasoning |
|---|---|---|
| Framework | **Vite + React + TypeScript** | Fastest cold start; no SSR needed for a static reader; Claude Code is highly productive here |
| Styling | **Tailwind** | Speed, and consistent density for a data-dense UI |
| Charts | **Recharts** (equity curve, greeks gauges) | Small, declarative, adequate |
| Data access | **`fetch()` on committed JSON** | No SDK, no keys, no CORS worries |
| State | **TanStack Query** or plain `useState` + a single fetch | Data is read-only and small; do not over-engineer |
| Routing | Single page + a replay timeline; hash routing if needed | Keeps GH Pages deployment trivial |
| Hosting | **Vercel** (preferred) or GH Pages | Gives us the required public "Application URL" |
| Secrets in frontend | **None. Ever.** | See §2.1(c) |

**Live vs snapshot data:** the dashboard shows the last committed snapshot, so it is as fresh as the last agent run (~15 min). That is *fine* and is worth stating openly in the demo — our strategy is deliberately latency-insensitive.
*If* we later want a true live view, the correct move is a single read-only serverless function (Vercel Edge) holding the key server-side — **not** keys in the browser. Deferred; probably unnecessary.

---

## 5. Data flow & state contract

Proposed shapes (to be finalised with Dev A before Dev B builds against them — **this contract is the parallelisation boundary**):

```
state/
  latest.json          # current book: positions, greeks, budget, equity, gates, kill-switch
  equity.json          # append-only equity curve points
  decisions/
    2026-08-31T1930Z.json   # one file per agent run
  notes/
    2026-08-31.md      # agent-authored desk note
```

`decisions/*.json` (sketch):
```jsonc
{
  "run_id": "2026-08-31T19:30:07Z",
  "trigger": "cron",
  "observed": { "clock": {...}, "regime": "...", "iv_rv": [...], "events": [...] },
  "considered": [ { "structure": "...", "score": 0.0, "rejected_because": "..." } ],
  "decided":    [ { "structure": "...", "legs": [...], "size": 0, "rationale": "..." } ],
  "gates":      [ { "gate": "max_book_delta", "passed": true, "value": 0, "limit": 0 } ],
  "acted":      [ { "client_order_id": "...", "alpaca_order_id": "...", "status": "..." } ],
  "errors":     []
}
```

> **This contract is the single most important thing to agree early.** Once it is frozen, Dev A and Dev B can work fully in parallel — Dev B builds the entire dashboard against a hand-written fixture file without waiting for the agent to exist.

---

## 6. Where MCP and the CLI each fit

Both are used, for honestly different jobs — this is a deliberate design position, not requirement-checkbox-ticking:

| | **Alpaca CLI** | **Alpaca MCP Server** |
|---|---|---|
| Role | The **unattended execution loop** | The **research & operator surface** |
| Why | Purpose-built for agents/cron/CI; JSON-first; `--client-order-id` idempotency; `--dry-run` preflight; no LLM in the hot path of an order | 50+ tools incl. native multi-leg `place_option_order`; lets us (and a judge) interrogate the live book in natural language from Claude Code |
| Runs where | GitHub Actions runner | Dev machine / demo |

**Design principle: the LLM never has direct execution authority.** It classifies regime, vetoes, and writes rationale. Order construction, sizing and submission are deterministic code behind hard gates. This is both good engineering and a strong thing to say on camera.

---

## 7. Scheduling

- **Primary:** GitHub Actions `schedule:` cron, at odd minutes (`:07`, `:23`, `:41`) to avoid top-of-hour queueing.
- **Cadence (proposed):** a pre-open run, 2–4 intraday runs, a pre-close run, per session. Deliberately sparse — the strategy does not need more.
- **Backstop:** `workflow_dispatch` for manual runs from a phone (GitHub mobile), since 19:00–01:30 IST is our night.
- **Tolerances the design must absorb** (per [research.md](research.md) §4): ±30 min drift, and **runs can be silently dropped**.
  - → Idempotent orders via deterministic `--client-order-id`.
  - → Reconcile-first: every run rebuilds intent from actual broker state.
  - → No strategy logic may depend on "the previous run happened."

---

## 8. Risk architecture (deterministic, outside the LLM)

| Gate | Purpose |
|---|---|
| Per-trade max loss (defined-risk structures only) | Hard floor per position |
| Per-book max loss / daily drawdown **kill switch** | If breached: flatten, stop opening, commit a `HALTED` state |
| Aggregate net delta / vega / theta bands | The core allocator constraint |
| Concentration cap per underlying | Prevents a single-name blowup |
| Liquidity gate (bid/ask non-zero, spread %, OI) | Also guarantees greeks are computable — see [research.md](research.md) §1.4 |
| DTE band (7–45) | Avoids the 0DTE no-greeks trap |
| Event rule (NFP, Fri 4 Sep 08:30 ET) | Reduce short gamma into the print |

Every gate evaluation is written to the decision log whether it passes or fails — that is what makes the glass-box claim real.

---

## 9. Tradeoffs considered

| Decision | Alternative | Why we chose it |
|---|---|---|
| GitHub Actions cron | Cloud Run / Railway / VM | Free, zero ops, and **every run is a public logged artifact** — the audit trail comes for free. Accepted cost: drift + dropped runs, absorbed by design. |
| Git-as-database | Supabase / Firebase | No backend, no auth, no secrets in the browser, immutable history. Cost: not real-time. Acceptable. |
| Static dashboard reading JSON | Browser calls Alpaca directly with CORS | Key exposure on a *published* account ID is an unacceptable risk (§2.1c) |
| CLI for execution, MCP for research | MCP for everything | An LLM in the order hot path is slower, costlier and less deterministic. CLI is what Alpaca built for this. |
| Diversified basket | SPY only | Halves the variance of a 4-day P&L, and 5 of 12 competitors are SPY-only |
| Defined-risk structures only | Naked short premium | Naked premium has the better win rate and the unbounded tail — into an NFP print, on a judged account. No. |
| Deterministic sizing, LLM as classifier/veto | LLM decides size and strikes | Explainability, reproducibility, and it is the honest engineering answer |

---

## 10. Open architecture questions

| # | Question | Needed by |
|---|---|---|
| A1 | Agent runtime language — **Python** (alpaca-py + MCP ecosystem) or **TypeScript** (shared types with the frontend)? My lean: Python for the agent, TS for the dashboard, JSON contract between them. | Before Stage 1 |
| A2 | Do we run the agent in a private repo and mirror to a public one, or run it all in public? Public is a stronger "glass box" story but leaks our logic mid-competition. My lean: **public** — originality is not our moat, execution is, and the transparency is the pitch. | Before Stage 1 |
| A3 | Do we need a serverless read-only proxy for a truly live dashboard, or is the committed snapshot enough? My lean: **snapshot is enough.** | Stage 3 |
| A4 | Freeze the `state/` JSON contract — who signs off? | **Today** — it is the parallelisation boundary |
