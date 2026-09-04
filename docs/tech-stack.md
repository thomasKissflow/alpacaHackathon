# Tech Stack — The Specialist

> Every entry below is verified against the running code, not aspirational.
> **Last verified:** 2026-09-04

---

## 1. The AI model

| | |
|---|---|
| **Model** | `Qwen/Qwen2.5-72B-Instruct` — 72-billion-parameter open-weights instruct model |
| **Host** | **Featherless AI** (hackathon inference sponsor) |
| **Endpoint** | `https://api.featherless.ai/v1` — OpenAI-compatible |
| **Client** | `openai` Python SDK with `base_url` overridden |
| **Provider resolution** | `LLM_PROVIDER` env var, auto-detecting from whichever API key is present |

**Why this model:** `Meta-Llama-3.1-70B-Instruct` was the obvious first choice and turned out to be gated behind HuggingFace OAuth on Featherless — it returns 403. Qwen2.5-72B is ungated, comparable in capability, and verified working for both prompts.

**A fallback path to Anthropic** (`claude-sonnet-5`) exists in `agent/config.py` but is deliberately **unused** — `ANTHROPIC_API_KEY` is left empty so the provider resolves to Featherless. If an Anthropic key were set it would silently win, and the partner-technology integration would be decorative rather than real.

### What the model actually does — two jobs, neither touching an order

1. **MarketPlan** (`agent/llm_agent.py`) — reads the live book (equity, net Greeks vs caps, recent fill count, news regime) and returns strict JSON: which symbols to quote, target spread in bps per symbol, and the weight between the two modes.
2. **News Agent** (`agent/news_agent.py`) — reads gold-market headlines and classifies an **uncertainty regime** (`calm` / `mixed` / `turbulent`), which scales quote width 0.9× / 1.0× / 1.35×. It deliberately emits **no direction** — a test asserts the return type carries no directional field.
3. **Daily post-mortem** — narrates the session from the ledger.

Every LLM output passes through a deterministic clamp before it can affect an order, and both the proposal and the approved version are written to the ledger with a `was_clamped` flag.

> ⚠️ **Hard-won constraint:** Featherless drops the connection above roughly 1,200 characters of prompt. `_LLM_MAX_PROMPT_CHARS = 650` in `llm_agent.py`. Exceeding it makes the AI layer fail silently and fall back to deterministic stubs — which is exactly how it went unnoticed for a full session.

---

## 2. Alpaca — five distinct surfaces

| Surface | Used for | How |
|---|---|---|
| **Alpaca CLI** (Go binary) | Account and position telemetry in the unattended loop | `alpaca account get`, `alpaca position list` via subprocess, JSON on stdout |
| **Trading API** | Order submission — single-leg options, multi-leg spreads, equity hedges | `alpaca-py`: `LimitOrderRequest`, `MarketOrderRequest`, `OptionLegRequest`, `OrderClass.MLEG` |
| **Options Market Data API** | Chains, snapshots, Greeks, IV, NBBO | `get_option_chain`, `get_option_latest_quote` |
| **Stock Market Data API** | Underlying spot for hedging and moneyness | `get_stock_latest_quote` |
| **News API** | Gold headlines for the News Agent | Direct HTTPS to `data.alpaca.markets/v1beta1/news` |

Plus **`get_clock`** for market state and **`get_orders`** for reconciliation.

**Alpaca MCP Server** is used as the research and operator surface during development — interrogating the live book in natural language from Claude Code — and deliberately kept **out of the order path**, where an LLM would add latency and non-determinism.

**Data tier: free (Basic).** Indicative options feed, IEX equities, last 15 minutes of history restricted, 200 req/min. The strategy is deliberately latency-insensitive so this is tolerable by design rather than a compromise.

---

## 3. Runtime and language

| Layer | Choice |
|---|---|
| Agent | **Python 3.11+** |
| Dependencies | `alpaca-py`, `openai`, `python-dotenv`, `pytest` — **four packages** |
| Options pricing | **Hand-written Black-Scholes + Newton IV solver** (`agent/pricing.py`) — `import math`, nothing else. **No numpy, no scipy.** |
| State | **SQLite** — one append-only file with real foreign keys (fills → orders, hedges → the fill that triggered them) |
| Scheduling | **GitHub Actions cron** (3×/day) + a continuous local daemon (30s poll) for quote maintenance |
| CLI toolchain | **Go** — required to build the Alpaca CLI binary |

**No server. No database service. No ORM. No web framework.**

---

## 4. Frontend

| | |
|---|---|
| Dashboard | Vanilla **HTML + CSS + JavaScript** — 148 / 387 / 417 lines |
| Charting | **Chart.js 4** via jsDelivr CDN |
| Data source | One static `data/dashboard.json` snapshot, exported each cycle |
| Hosting | **GitHub Pages** |
| Credentials in the browser | **None.** Ever. |

No React, no Vite, no Tailwind, no npm toolchain, no build step.

---

## 5. Infrastructure and tooling

- **Git / GitHub** — the repo is the agent's state store *and* its audit trail
- **GitHub Actions** — scheduled cycles; installs the Alpaca CLI via Go on each run
- **GitHub Pages** — dashboard hosting
- **pytest** — **63 tests**, zero live API calls in the suite
- **Claude Code** — the development environment throughout
- `publish.sh` — pushes dashboard snapshots on an interval
- `preflight.py` — read-only account/data/eligibility check that places no orders

**Scale:** ~3,255 lines of Python, 719 lines of tests, 2,442 lines of documentation.

---

## 6. Deliberate non-choices

Worth stating, because each was considered and rejected for a reason:

| Not used | Why |
|---|---|
| **Supabase / Postgres / Firebase** | We need a long-running process, not storage. SQLite is one file and needs no service. |
| **React / Next.js / Vite** | A read-only dashboard doesn't need a build step or an npm toolchain. |
| **numpy / scipy / pandas** | Black-Scholes is fifteen lines of `math`. Fewer dependencies, faster cold start in CI. |
| **A backtesting framework** | The competition window was four sessions. Time was better spent on live correctness. |
| **LangChain / agent frameworks** | The agent loop is observe → reconcile → orient → decide → gate → act → record. A framework would obscure it. |
| **MCP in the execution path** | An LLM between signal and order adds latency and non-determinism where neither is acceptable. |

---

## 7. Future tech stack — what we'd add with more time

### Immediate (days)
- **Real-time WebSocket quotes** instead of REST polling — Alpaca streams options quotes over `wss://stream.data.alpaca.markets`. Removes the 30-second blind spot between cycles, which is exactly the window in which a market maker gets picked off.
- **OPRA feed** (Algo Trader Plus, $99/mo) — full consolidated options data and 10,000 req/min instead of 200. The indicative feed and its 15-minute restriction are the biggest data constraint on quote quality.
- **Idempotent `client_order_id`** derived from a deterministic key — currently a real gap; matters the moment the scheduler retries.
- **A proper per-mode subledger** — P&L attribution is currently an approximation. Real mark-to-market accounting per strategy.

### Near-term (weeks)
- **Avellaneda–Stoikov optimal market-making** — the canonical model for inventory-aware quote skewing. Our cost floor is a crude first approximation of what that framework does rigorously.
- **A proper volatility surface** (SVI or SABR fit) instead of per-contract Black-Scholes IV — enables relative-value quoting across strikes rather than treating each contract independently.
- **Cloud Run or Fly.io** for the daemon, replacing a laptop with `caffeinate`.
- **Time-travel replay UI** — the ledger already has every timestamped row; it needs a frontend. Probably React + `sql.js` querying the SQLite file directly in the browser.
- **Prometheus + Grafana** for agent telemetry, or OpenTelemetry traces per cycle.

### Longer-term
- **Fine-tuned small model** for regime classification — a 7B fine-tune would be faster and cheaper than a 72B general model for what is fundamentally a 3-class labelling task.
- **Reinforcement learning for quote skew** — inventory management is a natural RL problem, though it needs far more data than a hackathon provides.
- **Cross-venue / dispersion strategies** — selling rich single-name IV against cheap index IV. Elegant, and blocked today only by data quality.
- **Multi-account portfolio allocation** — running several risk profiles in parallel and allocating between them on realised Sharpe.

---

## 8. Suggested submission tags

`Alpaca` · `Featherless` · `Qwen2.5` · `Python` · `Options Trading` · `Market Making` · `Algorithmic Trading` · `SQLite` · `GitHub Actions` · `Chart.js` · `MCP` · `Autonomous Agents`
