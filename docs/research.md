# Research Notes

> **Last updated:** 2026-08-29
> Everything here is sourced. Where I could not verify something, it is marked ⚠️ **UNVERIFIED**.

---

## 1. The Alpaca Stack — what we actually get

### 1.1 Alpaca CLI (`alpacahq/cli`)

**Why it matters:** satisfies hard requirement R2, and it is explicitly built for exactly our use case.

> "Alpaca CLI is designed for AI agents, scripts, and automation pipelines, not as an interactive trading terminal." — Alpaca docs

- Install: `go install github.com/alpacahq/cli/cmd/alpaca@latest` or `brew install alpacahq/tap/cli`
- Auth (preferred for CI/agents): `ALPACA_API_KEY`, `ALPACA_SECRET_KEY` env vars. Paper is the **default**; live requires explicit `ALPACA_LIVE_TRADE=true` opt-in.
- Every command emits **structured JSON on stdout** by default. Flags: `--csv`, `--jq '...'` (built-in jq!), `--quiet`, `--schema`, `--dry-run`, `--timeout`.
- Idempotency: `--client-order-id` — critical for a retrying/cron agent.

**Command surface relevant to us:**

```bash
# account & clock
alpaca account get
alpaca account portfolio          # equity curve + P&L  <-- great for the dashboard
alpaca account activity list      # fills, dividends
alpaca clock                      # is the market open?
alpaca calendar

# options contracts
alpaca option contracts --underlying-symbol SPY
alpaca option get --symbol-or-id SPY260918C00650000
alpaca option exercise --symbol-or-id <contract>
alpaca option do-not-exercise --symbol-or-id <contract>

# options market data
alpaca data option chain --underlying-symbol SPY
alpaca data option snapshot --symbol SPY260918C00650000     # includes greeks + IV
alpaca data option latest-quotes --symbol SPY260918C00650000

# orders
alpaca order submit --symbol AAPL --side buy --qty 10 --type limit \
  --limit-price 185.00 --client-order-id "$(uuidgen)" --dry-run
alpaca order list --status open
alpaca order cancel-all
alpaca position list / close / close-all

# raw escape hatch (this is how we place MULTI-LEG orders)
echo '{"order_class":"mleg","legs":[...]}' | alpaca api POST /v2/orders
```

**⚠️ Gap found:** the documented `alpaca order submit` examples cover **stock** orders. Multi-leg (`order_class: "mleg"`) option order placement is **not documented as a first-class CLI flag set**. The supported path is the raw `alpaca api POST /v2/orders` escape hatch.
- *Impact:* still fully satisfies R2 (it is the CLI binary), but our agent must construct mleg JSON itself.
- *Effort:* Low. *Risk:* Low, but **must be validated on day 1** with a `--dry-run` / tiny live paper order. This is Task T-004.

**Judge appeal:** Alpaca launched this CLI *for agentic AI*. Three Alpaca staff are judging. Using the CLI deeply — including `--client-order-id` idempotency, `--dry-run` preflight and `--jq` — is a direct, legible signal of "Technology Implementation".

---

### 1.2 Alpaca MCP Server (`alpacahq/alpaca-mcp-server`)

- v2 is a **complete rewrite on FastMCP + OpenAPI**. 50+ tools across 9 toolsets.
- Run: `uvx alpaca-mcp-server` (stdio, default) or `--transport streamable-http --port 8000`.
- Env: `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `ALPACA_PAPER_TRADE` (default `true`), `ALPACA_TOOLSETS` (scope which tools are exposed).
- Options tools: `get_option_contracts`, `get_option_chain`, `get_option_snapshot` (greeks + IV), `get_option_latest_quote`, `place_option_order` (**single-leg AND multi-leg**), `exercise_options_position`, `do_not_exercise_options_position`.
- **Alpaca does not provide a hosted remote MCP server** — self-hosting only. Docker file included.

**Key architectural fact:** the MCP server *runs inside an MCP client* (Claude Desktop, Cursor, VS Code) — it is not a standalone daemon that decides things. An MCP server is a **tool surface, not an agent**. Something must drive it.

> **Implication:** "use MCP" does not by itself give us autonomy. Either (a) we drive MCP from our own agent loop (an LLM client we run headlessly), or (b) we use the CLI for the unattended loop. `place_option_order` supporting multi-leg natively is a genuine advantage of MCP over the CLI.
>
> **Recommendation:** use **both, for different jobs** — MCP for the reasoning/research surface, CLI for the deterministic unattended execution loop. This is defensible, idiomatic, and shows range. See [architecture.md](architecture.md).

---

### 1.3 Options trading on a paper account

- Options are **enabled by default** in the paper environment — no application, nothing to do.
- **Multi-leg (Level 3) is available in paper**: straddles, strangles, iron butterflies, iron condors, verticals. Submit via `POST /v2/orders` with `"order_class": "mleg"` and a `legs` array.
- Each leg carries its own strike/expiry/side.

**Why it matters:** defined-risk spreads (verticals, condors) are available to us. That is the difference between "sold a naked put and got lucky/destroyed" and "a risk-managed desk". Judges will notice.

---

### 1.4 Market data tiers — ⚠️ THE BIGGEST TECHNICAL CONSTRAINT

| | **Basic (free)** | **Algo Trader Plus ($99/mo)** |
|---|---|---|
| Options feed | **Indicative** (derived/calculated values) | **OPRA** (consolidated, all exchanges) |
| Options WS subscriptions | 200 quotes | 1,000 quotes |
| Historical data | **⚠️ blocked for the latest 15 minutes** | No restriction |
| Equities real-time | **IEX only** (~2-3% of volume) | All US exchanges (SIP) |
| API rate limit | **200 req/min** | 10,000 req/min |

**Consequences we must design around:**

1. **We are effectively trading on ~15-minute-stale reference data.** Any strategy needing sub-minute precision, tight scalping, or accurate fills at the touch is off the table. → *Design the strategy to be latency-insensitive.* This is a constraint that, handled well, becomes a design story.
2. **IEX-only equity quotes** are thin and can be unrepresentative for less liquid names. → *Stick to hyper-liquid underlyings* (SPY, QQQ, IWM, mega-caps).
3. **200 req/min** means we cannot brute-force scan thousands of contracts. → *Use `option chain` (one request returns many contracts) rather than per-contract loops.*
4. **Greeks / IV are not always available**, and the reason is not the plan:
   - Alpaca computes greeks with Black-Scholes and needs **non-zero bid AND ask** on the latest quote.
   - **0DTE contracts have no greeks at all** — days-to-expiry is in the denominator, so it is a division by zero.
   - IV calc is capped at 100 iterations; non-convergence → no IV.
   - → **Any strategy built on 0DTE greeks is dead on arrival.** Prefer 7–45 DTE. This single fact eliminates a whole class of otherwise-obvious hackathon ideas.

**Q4 for Thomas:** $99 for OPRA + 10,000 req/min. My view: **probably not worth it.** Our strategy should be latency-insensitive by design, and "we built an agent that works on the *free* tier" is a better story than "we bought our way out". But if we pick a strategy that scans wide chains, the 200 req/min limit may force it. Revisit after Q2.

---

### 1.5 Browser/CORS

- Alpaca enabled **CORS on Trading API v2 in 2019** — a browser *can* call the Trading API directly.
- **This does not make a frontend-only agent safe.** Any key shipped to a browser is public. On a *judged* account whose ID we publish, exposed keys mean anyone can trade our competition account. That is a P&L-destruction and disqualification risk, not a theoretical one.
- → **Never put Alpaca keys in the deployed frontend.** See [architecture.md](architecture.md) §3.

### 1.6 ⚠️ Paper environment fidelity — what the simulator does NOT model

Verified 2026-08-30 against https://docs.alpaca.markets/us/docs/paper-trading

Paper trading is **not** a faithful execution simulator. It explicitly does not model:

- Dividends
- **Market impact** of our orders
- **Price slippage** from latency
- **Order queue position**
- Borrow fees, regulatory fees
- Information leakage

And two behaviours that directly affect agent design:

| Documented behaviour | Consequence for us |
|---|---|
| **"Orders are filled only when they become marketable."** | A limit order resting away from the market will simply never fill. Our agent wakes every ~30 min — it must place *marketable* limit orders, and must detect and re-price or cancel unfilled working orders on each run, or it will silently do nothing all week. |
| **"Partial fills occur randomly 10% of the time when orders are eligible."** | 🔴 **This is the biggest newly-discovered risk in the project.** See below. |
| **"You can submit and receive a fill for an order that is much larger than the actual available liquidity."** | Our paper P&L will be *flattering* relative to reality. We should say so openly in the write-up rather than let an Alpaca judge point it out. |

#### 🔴 Partial fills on multi-leg orders — a naked-leg hazard

A defined-risk spread is only defined-risk **if all legs fill**. If a short vertical fills its short leg but not its long leg, the position is a **naked short option with theoretically unbounded loss** — on the account we are judged on, overnight, while we are asleep in IST.

Alpaca documents a **random 10% partial-fill rate**, so over a week of multi-leg orders this is close to a certainty rather than an edge case.

**Required mitigations (must be in Stage 1, not deferred):**
1. On every run, reconcile actual legs held against intended structures.
2. Detect any unpaired short leg and immediately either complete the structure or flatten it.
3. Never treat "order submitted" as "position established" — only the reconciliation step may update intended state.
4. Alert loudly (commit a `DEGRADED` state) when a naked leg is detected.

This single finding justifies the reconcile-first design in [architecture.md](architecture.md) §3 far more concretely than cron drift did.

---

## 2. Competitor Analysis — 12 submissions already public

The hackathon page lists submissions live. This is unusually good intelligence. As of 2026-08-29:

| # | Project | Team | Approach | Stack tags |
|---|---|---|---|---|
| 1 | **AEGIS-Q** | Team V | Bounded AI picks a *pre-validated* bull/bear spread — or abstains. Deterministic code owns sizing, max loss, execution, exits. | Alpaca, OpenAI, ElevenLabs |
| 2 | **BABIL** | BABIL | **Human-in-the-loop**; AI reasoning separated from execution authority; explicit human approval, kill switch | Alpaca, AI/ML API |
| 3 | **Tissue Regeneration & Genetic Factor Navigator** | Tissulogic | Maps tissue-engineering parameters to biotech equity/options execution | Alpaca, Gemini, Streamlit |
| 4 | **SPY Sentinel AI** | SPY Sentinel AI | SPY research agent; out-of-sample validation; risk gates; **refuses to trade without proven edge** | Alpaca, GitHub Copilot |
| 5 | **AlphaPilot AI** | Quantum Coders | SPY BUY/NO-TRADE signals → option selection → entry/exit/risk | Alpaca, Auto-GPT, AI/ML API +5 |
| 6 | **VibeHedge** | ShinyDataTech | xLSTM forecasting + FinRL-X risk gates + greeks; protective hedges; **Alpaca FastMCP on Cloud Run** | Alpaca, RL, Antigravity |
| 7 | **AlphaSwarm Sovereign Capital** | AlphaSwarm Sovereign | Multi-agent "hedge fund"; adversarial dialectic debate; chart vision; 1,000-path Monte Carlo risk gates | Alpaca, AI/ML API +5 |
| 8 | **NewsFlow Trader** | cubiczan | LLM reads headlines → scores → risk guard → orders; live Next.js dashboard | Alpaca |
| 9 | **Odysseus** | Odysseus | Agent discovers hypotheses, writes C# StockSharp strategies, backtests/optimises | Codex (**no Alpaca tag!**) |
| 10 | **Vega** | isquividet | Long-gamma SPY convexity via **MCP**; refuses unquotable fills; loss capped at premium; "48/48 claims reproduce from one command" | Alpaca |
| 11 | **a continual learning agent** | trueintrinsics | PX5000 hourly vol forecasts; ranks near-ATM **straddles** by predicted-vs-implied move | AgentOps, AI/ML API, RL |
| 12 | **Options Sniper** | primehack security team | Scans 7 tickers, scores **bull call spreads**, auto-exit | Alpaca |

### What the field looks like — patterns to avoid

**Heavily crowded (do NOT differentiate here):**
- **SPY-only.** At least 5 of 12 are SPY-centric. SPY is the default choice; it is not a differentiator.
- **"Risk gates".** Nearly every single entry uses this exact phrase. It is now table stakes, not originality. We must *have* them and must not *sell* on them.
- **"Refuses to trade / abstains when no edge."** AEGIS-Q, SPY Sentinel, Vega all lead with this. It has become the field's signature move — and it carries a hidden failure mode (see below).
- **Bull call spreads / simple verticals.** Options Sniper, AEGIS-Q.
- **A dashboard.** NewsFlow, others. Necessary, not sufficient.
- **Multi-agent debate.** AlphaSwarm has planted this flag hard.

**Visible weaknesses in the field (our openings):**
- **The abstention trap.** Judging criterion 1 rewards P&L *"and how effectively the strategy performs through its trading activity."* An agent that refuses to trade produces **no P&L and no activity** — it scores zero on the heaviest criterion while sounding responsible. Several entries are exposed to this. We should be *selective but always in the market*.
- **Single-instrument concentration.** SPY-only over 4 sessions is one bet, not a strategy. A diversified book has dramatically lower variance of outcome — which matters enormously when the sample is 4 days.
- **No portfolio-level risk management.** Almost every entry describes *per-trade* gates (max loss, position size). Almost none describes managing the **book's aggregate greeks** (net delta / vega / theta). That is what an actual options desk does, and it is a wide-open originality lane.
- **Nobody has mentioned the NFP print** on the final morning. Event-awareness is unclaimed.
- **Odysseus doesn't even list Alpaca** in its tags and is built on C#/StockSharp — likely weak on R1/R2/R3.
- **BABIL is explicitly human-in-the-loop**, which is in direct tension with R1 ("autonomous").

### What this tells us
The bar for "competent" is already met by ~6 teams. The bar for "wins" is: **positive P&L + genuine portfolio-level sophistication + a presentation that makes the process auditable.** See [brainstorming.md](brainstorming.md).

---

## 3. Featherless AI (sponsor)

- OpenAI-compatible API. Base URL `https://api.featherless.ai/v1`; `GET /v1/models`; Bearer auth.
- 37,000+ open-source models; large context (up to 256K).
- $25 per-request credits with code `ALPACA26`, **first-come first-served — claim immediately.**
- Published rates ≈ $0.102 / M input tokens, $0.493 / M output tokens → $25 is a *lot* of headroom for a 5-day agent.
- **Partner-prize rule:** "to be eligible for partner prizes, the relevant partner technology must be integrated into a project submitted under the hackathon challenge." 1st place carries $300 in Featherless credits.

**Why it matters / how to use it well:** a cheap, genuine role for an open model is the strongest play — e.g. Featherless-hosted model does high-volume, low-stakes work (news/filing summarisation, regime labelling, per-trade rationale generation) while a stronger model handles the consequential judgment. Integrating it *token-cheaply and honestly* beats bolting it on.
- **Complexity:** Low. **Effort:** ~2h. **Risk:** Low (it's an OpenAI-compatible call).

---

## 4. Scheduling / runtime research

We need something that runs unattended during **19:00–01:30 IST**.

| Option | Cost | Reliability | Notes |
|---|---|---|---|
| **GitHub Actions cron** | Free | ⚠️ **5–30 min delay typical; jobs can be silently dropped under load** | Runs are logged artifacts = free audit trail. Schedule at odd minutes (e.g. `:07`, `:23`) to dodge the top-of-hour stampede. |
| Cloud Run + Cloud Scheduler | ~free tier | High | More setup; VibeHedge already uses Cloud Run |
| Railway / Render cron | ~$5 | High | Simple, reliable |
| Fly.io machine | ~free tier | High | |
| Laptop cron | Free | ❌ Poor | Laptop must be awake 19:00–01:30 IST every night. Do not rely on this. |

**Design consequence:** whichever we pick, the strategy must tolerate a **±30 minute execution delay** and **skipped runs**. That means:
- No time-critical entries (no "buy at exactly 09:45 ET").
- Every run must be **idempotent** (`--client-order-id` derived from a deterministic key).
- Every run must be **self-healing**: reconcile actual positions vs intended state on each wake, rather than assuming the last run succeeded.

This is a genuinely good architectural story and it directly answers "how your agent manages positions."

---

## 5. Market calendar & events in the judging window

- Trading sessions: **Mon 31 Aug, Tue 1 Sep, Wed 2 Sep, Thu 3 Sep, Fri 4 Sep (partial)**. No US market holidays in the window (Labor Day is Mon 7 Sep, after the deadline).
- Regular hours 09:30–16:00 ET = **19:00–01:30 IST**.
- **🔴 Non-Farm Payrolls: Fri 4 Sep 2026, 08:30 ET** (18:00 IST) — the August employment report. Released **1 hour before the open**, and **2.5 hours before our submission deadline** (11:00 ET / 20:30 IST).
  - Confirmed via BLS schedule and multiple economic calendars.
  - Effect: index options will carry an elevated event premium into Thursday's close, and SPY will **gap** on Friday's open.
  - **Risk:** a short-premium book carries overnight gap risk into the single most violent scheduled print of the month, on the exact morning we are judged.
  - **Opportunity:** an agent that *knows* about the event and de-risks or positions for it is (a) demonstrably intelligent, (b) unclaimed by any of the 12 published competitors, and (c) a fantastic 20-second moment in the demo video.
- ⚠️ **UNVERIFIED:** ISM Manufacturing (typically 1st business day of the month, ~Tue 1 Sep, 10:00 ET) and ADP (typically Wed, ~2 Sep). Worth confirming before locking event rules. Also worth checking for large-cap earnings in the window (early September is a quiet earnings period, but retailers sometimes report).

---

## 6. Technical findings summary

| Finding | Impact | Confidence |
|---|---|---|
| CLI is purpose-built for agents/cron, JSON-first, has `--client-order-id` and `--dry-run` | Satisfies R2 elegantly; ideal for unattended loop | High |
| Multi-leg option orders not documented as CLI flags → use `alpaca api POST /v2/orders` | Small implementation task, must validate early | High |
| MCP server is a tool surface, not an agent; no hosted version | Cannot be the autonomy mechanism by itself | High |
| Multi-leg L3 enabled by default in paper | Defined-risk spreads available | High |
| Free tier = indicative options feed, IEX equities, last 15 min of history blocked, 200 req/min | Must design a latency-insensitive strategy | High |
| **0DTE contracts have no greeks** (division by zero on DTE) | Kills 0DTE-greek strategies; prefer 7–45 DTE | High |
| Greeks need non-zero bid AND ask | Illiquid contracts silently lack greeks → filter on quote quality | High |
| Alpaca Trading API allows CORS | Browser *can* call it — but keys would be public | High |
| GH Actions cron drifts 5–30 min and can drop runs | Strategy must be latency-insensitive + idempotent + self-healing | High |
| **Paper fills 10% partial at random** → multi-leg spreads can leave a **naked short leg** | Reconciliation + naked-leg detection is mandatory in Stage 1 | High |
| Paper fills only when marketable; no slippage, no market impact, infinite liquidity | Use marketable limits; expect flattering P&L — disclose it | High |
| NFP on Fri 4 Sep 08:30 ET, inside the window | Major risk + major unclaimed demo opportunity | High |
| 12 competitors already submitted; SPY + "risk gates" + "abstain" are saturated | Differentiate on portfolio-level risk & auditability | High |

---

## 7. Sources

- https://lablab.ai/ai-hackathons/alpaca-ai-trading-agents-hackathon
- https://github.com/alpacahq/cli — CLI repo & README
- https://docs.alpaca.markets/us/docs/alpacas-cli — CLI docs
- https://alpaca.markets/blog/alpaca-introduces-cli-for-trading-api/ — CLI announcement
- https://github.com/alpacahq/alpaca-mcp-server — MCP server
- https://docs.alpaca.markets/us/docs/alpaca-mcp-server — MCP docs
- https://docs.alpaca.markets/changelog/multi-leg-level-3-options-trading-in-paper — multi-leg in paper
- https://docs.alpaca.markets/us/docs/options-trading — options trading
- https://docs.alpaca.markets/us/docs/about-market-data-api — data plans & limits
- https://docs.alpaca.markets/us/docs/market-data-faq — greeks/IV availability
- https://docs.alpaca.markets/us/docs/paper-trading — paper account creation, balance, fill semantics
- https://docs.alpaca.markets/us/docs/authentication — Trading API auth headers
- https://docs.alpaca.markets/us/reference/issuetokens — OAuth2 token endpoint (Broker API partners; **not** our flow)
- https://alpaca.markets/blog/websocket-moc-cors/ — CORS enablement
- https://featherless.ai/docs/quickstart-guide — Featherless API
- https://www.bls.gov/news.release/empsit.nr0.htm — BLS employment situation schedule
- https://github.com/orgs/community/discussions/156282 — GH Actions cron delays
