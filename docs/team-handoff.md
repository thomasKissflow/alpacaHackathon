# Team Handoff Notes

> **Read this first after `git pull`.** Fastest path from "just cloned" to "know what to do."
> **Last updated:** 2026-09-04 ~02:15 IST by Claude (working with Thomas)
> **Update rule:** whoever finishes a session updates this file before pushing.

---

> 📌 **New overnight (4 Sep):** read [MORNING-BRIEF.md](MORNING-BRIEF.md) first, then
> [video-script.md](video-script.md) if you are recording. Config is now: specialist basket
> SPY/QQQ/AAPL/NVDA/TSLA/**GLD** (IAU dropped — 11.5% wide market), convexity
> SPY/QQQ/IWM/GLD, delta cap **$60k**, `min_close_edge_bps` **10** (D-015/016/017) — it covers a
> major economics bug found and fixed in Specialist Mode (D-016), plus the finished write-ups
> and slide content.

## ⏰ Where we are

**Fri 4 Sep, ~02:15 IST. SUBMISSION DEADLINE TODAY 20:30 IST (~18h).**
US market opens **19:00 IST** — the final session is 19:00→20:30 IST, 90 minutes, and it is the last chance to add P&L.
**NFP prints 18:00 IST**, one hour before that open. The agent handles this itself (D-014).

The agent is **built, live-validated, and has traded**. Thursday's session: **69 fills, 93 hedges, 100 quotes, equity $99,513 (−0.49%)**. Daemon and `publish.sh` were stopped at the close — **both need restarting before 19:00 IST**.

---

## ✅ Done

- **Competition account is live and eligible.** `PA318JJN6DXK` — created fresh, verified $100,000 and **0 prior orders** before use. ID recorded in `docs/credentials.md`. R4/R5/R6 satisfied.
- **Alpaca CLI installed** at `~/.local/bin/alpaca` (built from source — this Mac has no brew/go; Go lives in `~/.local/go`). The `CLI unavailable, falling back to SDK` warning is gone, so **R2 is genuinely satisfied**.
- **The agent traded a real session** — Specialist Mode quoting and hedging, Convexity Mode holding 3 spreads.
- **Dashboard is live** at https://thomaskissflow.github.io/alpacaHackathon/dashboard/
- **The AI layer works** — see the critical note below.
- **NFP event rule** (D-014), **gold + News Agent + delta cap** (D-015).
- **One-page write-up drafted** — `docs/write-up.md`.
- **55 tests passing**, zero live API calls in the suite.

---

## 🔴 CRITICAL CONTEXT: the AI layer was silently dead until 2026-09-04

Every `market_plan` logged `source='fallback'` and every postmortem said `[LLM call failed]`. **Featherless had never once been called successfully.** Three independent bugs, all now fixed — do not undo any of them:

1. **`LLM_PROVIDER` resolved to `""`.** `os.environ.get(key, default)` returns `""` when the key exists but is empty, and `.env.example` ships a bare `LLM_PROVIDER=` line. Now empty/whitespace is treated as unset.
2. **The `openai` SDK could not reach Featherless** (`APIConnectionError`) while an identical direct request returned 200. `_call_featherless` now uses a direct `httpx` POST with 3 retries.
3. **⚠️ Featherless hard-disconnects above ~1,200 prompt characters.** Reproducible, always at exactly 15.1s. Measured: 700ch → 200 OK in 3.0s; 1,200 / 1,600 / 2,500ch → `RemoteProtocolError` every time.
   **→ `_LLM_MAX_PROMPT_CHARS = 650`. If you add anything to an LLM prompt, keep the total under that or the AI silently dies again.**

Verified working: `[llm_agent] Featherless OK (Qwen/Qwen2.5-72B-Instruct, 381 tokens)`, `source='llm'`.

---

## ▶️ Next actions, in order

**Before 19:00 IST (market open) — highest value first:**
1. **Restart the agent** (it must be running for the final session):
   ```
   caffeinate -is python3 -m agent.daemon
   ```
   and in a second terminal: `./publish.sh`
2. **Sanity check first**: `python3 preflight.py` — expects account reachable, market clock, Greeks on the free feed.
3. **Watch the first few cycles** for gold (`GLD`/`IAU`) quoting and `[news] gold regime ...`. Both are new and have never run in a live session.

**Presentation (this is now the bulk of the remaining work):**
4. **Video** — budget 4h, it always overruns. Two of five judging criteria ride on it.
5. **Slides**, **cover image**.
6. **Trim `docs/write-up.md`** to one page if they enforce it.
7. **Social posts** — up to 5, tag @lablabai + @AlpacaHQ. Separately winnable $500, thin competition.
8. **Submit by 19:45 IST**, not 20:25. Full field list in `docs/submission-checklist.md`.

---

## 🐛 Known issues / open risks

| Risk | Severity | Status |
|---|---|---|
| **`git push` failing** (`RPC failed; curl 52/56`) — network, not code. Commits stack up locally and Pages goes stale | **High** | Retry `git push origin main`. `publish.sh` also retries each cycle |
| Daemon + publish.sh currently STOPPED (market closed) | **High** | Must restart before 19:00 IST |
| Gold symbols and News Agent have never run in a live session | Medium | Watch the first cycles closely |
| P&L is negative (−0.49%); market-making hedge costs exceed captured spread so far | Medium | Expected for a short window; disclosed honestly in the write-up |
| Per-mode P&L attribution is an approximation (specialist = day P&L − convexity realised) | Low | Documented in the write-up |
| Paper fills are optimistic (no slippage/impact/queue) | Low | Disclosed in the write-up |
| Time-travel replay UI (T-030) never built | Low | Dropped deliberately; video matters more |
| Idempotent `client_order_id` (T-016/T-049) never added | Low | Dropped; only ~1 session remains |

---

## ⚠️ Things that will bite you if you don't know them

1. **Prompt budget is 650 chars.** See the AI section above.
2. **Quote OTM puts only.** A symmetric strike band picks in-the-money puts, whose delta approaches −1.0 — one ITM SPY contract is ~$75k of delta and the risk gate clamps every quote to zero.
3. **Alpaca rejects naked short calls** (`not eligible to trade uncovered option contracts`) — the agent quotes puts only, by design.
4. **Alpaca rejects a simultaneous resting bid + ask on the same contract** (wash-trade protection) — one side per contract per cycle.
5. **0DTE contracts have no Greeks** (days-to-expiry is in the Black-Scholes denominator). Stay in the 7–45 DTE band.
6. **Paper multi-leg orders partially fill ~10% of the time at random.** A half-filled vertical is a *naked short option*. `agent/reconcile.py` runs first every Convexity cycle for exactly this reason — don't reorder it.
7. **`day_start_equity` is keyed by (date, account).** It used to be date-only, which meant switching accounts mid-session reported P&L against the wrong baseline.
8. **Never commit `.env`.** Competition keys belong in `.env` locally and GitHub Actions Secrets — nowhere else.

---

## 📓 Session log

### 2026-08-29 · Claude
Analysed the kickoff email and hackathon page (the page carried far more than the email — deadline, judging criteria, full submission field list, judge names, and **12 live competitor submissions**). Researched the Alpaca CLI, MCP server, options API and data-tier limits; found the 0DTE-greeks blocker and the free-tier 15-minute historical restriction. Confirmed NFP falls inside the judging window. Built the full `docs/` structure, generated 16 ideas, evaluated the top 4, and recommended a staged build of a portfolio-greeks options desk with a glass-box dashboard. Challenged the frontend-only constraint with a two-tier alternative. **No code written.** Everything now waits on Thomas's decisions.

### 2026-09-04 · Claude, working with Thomas
Triage session. Found the agent had **never traded** — no commits since 31 Aug, `orders` table empty, dependencies never installed. Installed deps, built the Alpaca CLI from source (no brew/go on the machine), and wrote `preflight.py` (read-only eligibility/data check). Preflight caught that the account in use was the **retired dev account** — 17 prior orders, $99,742 equity — so a fresh $100k account was created and wired in before any judged trading. Agent then ran a live session: 69 fills, 93 hedges, −0.49%.

Fixed live, in order of severity: **the entire AI layer was dead** (three bugs — empty `LLM_PROVIDER`, openai SDK connection failure, and Featherless's ~1,200-char prompt ceiling); **Specialist Mode quoted in-the-money puts** so the risk gate clamped every quote to zero; **`day_start_equity` survived an account switch** and misreported P&L by $276; the dashboard **misrendered convexity credit** as `$1` vs `$358` max loss (missing 100x contract multiplier); and the LLM context **double-counted Greeks across time**, telling the model the book was 2x over its cap.

Built: `agent/event_calendar.py` (NFP rule, D-014), `agent/news_agent.py` (gold headlines → uncertainty regime, D-015), `publish.sh` (pushes dashboard snapshots — `cycle.py` wrote them to local disk only, so Pages 404'd), and `docs/write-up.md`. Added gold to the baskets and raised the delta cap to $60k (D-015). **55 tests passing.**

### 2026-08-31 · Claude, working with Suryaprakash
Arrived with a separately-built, working, tested implementation of a different concept (an options market maker, "The Specialist") already in hand, and was asked to push it to this shared repo. Read the full existing `docs/` tree first rather than pushing over it — found D-004/D-006 still marked PROPOSED and the concept/architecture materially different from what was about to be pushed. Surfaced that conflict explicitly and got an explicit decision to proceed as the concept/architecture sign-off, not silently. Before pushing: read `research.md` closely enough to find that the documented 10% random paper-trading partial-fill rate on multi-leg orders wasn't handled anywhere in the incoming code, and built `agent/reconcile.py` (naked-leg detection + flatten, stale-unfilled-entry cancellation) specifically in response to that finding before pushing, rather than after. Wrote D-011 and D-012 to document the pivot with reasoning **and an honest "what we're giving up" section** (book-level Greeks-budget allocator, regime playbook, time-travel replay UI, NFP rule — all real gaps against the original plan, all listed as open tasks, not glossed over). Updated `project-overview.md`, `tasks.md`, and this file to match. Merged the two READMEs rather than overwriting either. Verified the Featherless LLM integration live (found `Meta-Llama-3.1-70B-Instruct` is gated behind HuggingFace OAuth and switched the default to `Qwen/Qwen2.5-72B-Instruct`). 27 tests passing, zero live API calls in the suite. **Still not done live: T-004/T-005/T-021 (no paper account keys were available this session), T-016/T-049 (idempotent client-order-id), T-027 (NFP rule), T-030/T-032 (replay UI + deploy).**
