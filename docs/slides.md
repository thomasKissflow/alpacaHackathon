# Slide Deck — The Specialist

> 10 slides. Speaker notes under each. Aim ~3 min if the video is short-form; drop slides 8–9 first if you need to cut.
> **Design rule:** one idea per slide, big type, no paragraphs. The dashboard screenshots do the heavy lifting.

---

## 1 — Title

**THE SPECIALIST**
*An autonomous options market maker*

Alpaca AI Trading Agents Hackathon · Paper account `PA318JJN6DXK`
`github.com/thomasKissflow/alpacaHackathon`

> **Say:** "Everyone else built an agent that guesses the market. We built one that makes a market."

---

## 2 — The problem with predicting

> Visual: a big question mark over a candlestick chart, then a red ✗

- Nearly every trading agent asks: **"will it go up or down?"**
- Over a 4-day competition window, that is a **coin flip**
- 12 published submissions. At least 5 are SPY direction-guessers.

> **Say:** "We didn't want our result to depend on being right about the market. So we built something that doesn't need to be."

---

## 3 — What a market maker actually does

> Visual: currency-exchange booth → "BUY 82 / SELL 84"

A shop doesn't bet on prices. It buys at 82, sells at 84, keeps the difference — **whichever way the market moves.**

The Specialist does this with options:
```
buy  NVDA 227.5 put @ 3.20
sell NVDA 227.5 put @ 3.25     →  edge captured
```

> **Say:** "This is a real business, not a prediction. It's what the people on the other side of your trades do all day."

---

## 4 — The hard part: staying neutral

> Visual: two bars cancelling to ~zero

Buying a put creates directional exposure. So the agent **immediately hedges with the underlying stock**, every cycle.

| | |
|---|---|
| TSLA option delta | **−$17,246** |
| TSLA stock hedge | **+$17,188** |
| **Net exposure** | **−$58** |

Against a $60,000 cap.

> **Say:** "It's holding seventeen thousand dollars of directional risk and carrying almost none of it. That's the whole trick."

---

## 5 — Where the AI sits

> Visual: two columns, hard line between them

| **Featherless LLM decides** | **Deterministic code decides** |
|---|---|
| Which symbols to quote | Which strikes and expiries qualify |
| How wide to quote | The actual prices |
| Weight between the two modes | Position size |
| Reads gold news → risk regime | **Whether an order is placed at all** |

**The model has no execution authority.**

> **Say:** "An LLM that can size a position can end your account on one bad sample. Ours can only ever make the system more conservative."

---

## 6 — The News Agent

> Visual: real headlines → arrow → `regime: mixed` → arrow → wider quotes

Reads gold headlines from **Alpaca's News API** → **Featherless (Qwen2.5-72B)** → an *uncertainty regime*.

> *"Investor sentiment is split between tech rallies and increased interest in gold as a safe haven."* → `mixed`

`calm` 0.9× · `mixed` 1.0× · `turbulent` **1.35×** quote width

**It never picks a direction.** Turbulent news makes the agent charge *more* to provide liquidity.

> **Say:** "A market maker doesn't need to know which way gold goes. Only how nervous to be about being on the other side of a trade."

---

## 7 — It knows what's coming

> Visual: timeline — de-risk → 🔴 NFP → re-engage

Non-Farm Payrolls printed **inside** the competition window — one hour before the final session opened.

| Phase | Behaviour |
|---|---|
| T−20h | Quotes **1.6× wider**, no new short premium held across the print |
| T−45m → T+75m | **Blackout.** Places nothing. |
| T+75m | Re-engage at **0.85×** — event premium has collapsed |

> **Say:** "Every other input this agent uses is reactive. A scheduled release is the one thing it can know in advance. None of the twelve published competitors mention events at all."

---

## 8 — Risk gates that actually fire

> Visual: screenshot of the dashboard risk log

- Portfolio delta / vega / gamma caps — orders **clamped**, not just rejected
- **Naked-leg reconciliation** — paper multi-leg orders partial-fill ~10% at random; a half-filled vertical is a *naked short option*
- **Inventory cost floor** — never close a position below what we paid
- 2% daily drawdown circuit breaker · kill switch

> **Say:** "These aren't decorative. That log is every gate that fired last session."

---

## 9 — Built by breaking it

> Visual: terminal output of a real rejection

Found by running it live, not by reading docs:

- `account not eligible to trade uncovered option contracts` → **puts only**
- `cannot open a short sell while a long buy order is open` → **one side per contract**
- Alpaca can't compute Greeks for **0DTE** — division by zero on days-to-expiry
- Our market maker was **paying** the spread, not earning it — 33 round trips, −$85 gross. Fixed with the cost floor.

**63 tests**, several written because live running broke the code first.

> **Say:** "We'd rather show you the bugs we found than pretend there weren't any."

---

## 10 — Close

> Visual: full dashboard screenshot

**No server. No database.** A scheduled process, an append-only SQLite ledger, a static dashboard holding zero credentials.

Every decision the agent made is reconstructable from the ledger.

**`PA318JJN6DXK`** — the account is open for inspection.

> **Say:** "Everyone else built a bot that guesses the market. We built one that makes a market — and you can audit every decision it made."

---

## Cover image
Dark background. Large **THE SPECIALIST** wordmark. Beneath: *autonomous options market maker*. Behind it, faded, the dashboard's equity curve and the Greeks-vs-caps gauges. Small Alpaca + Featherless logos bottom-right.

## Video running order (3 min)
1. **0:00–0:20** — hook: "everyone predicts, we make a market" (slides 1–2)
2. **0:20–0:50** — the shop analogy + a real fill from the ledger (slides 3)
3. **0:50–1:20** — the hedge, with the −$58 number on screen (slide 4)
4. **1:20–1:50** — where the AI sits + News Agent live output (slides 5–6)
5. **1:50–2:20** — NFP timeline (slide 7)
6. **2:20–2:45** — **live dashboard walkthrough**, scroll the risk log and activity feed
7. **2:45–3:00** — close on the account ID (slide 10)

> Record the dashboard walkthrough as real screen capture, not a screenshot. Judges want to see it moving.
