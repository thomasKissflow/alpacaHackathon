# FINAL VIDEO SCRIPT — The Specialist
**Target 2:50. Screen recording + voiceover. No talking head.**

---

## PREP — 10 minutes, do this first

- [ ] Dashboard open: https://thomaskissflow.github.io/alpacaHackathon/dashboard/
- [ ] Second tab: the GitHub repo, on the file list
- [ ] Terminal visible with the daemon log (or `docs/` open)
- [ ] Notifications off, bookmarks bar hidden, 1080p
- [ ] **Re-read the equity + fill numbers off your dashboard and swap them into the script below**
- [ ] One practice run. Then record.

**Current numbers (verify before you speak them):** equity **$99,515**, day P&L **−$485**, **70 fills**, **95 hedges**, **100 risk events**.

---

## 0:00 – 0:15 · HOOK

**SHOW:** Title slide → cut to dashboard top (equity + stat cards)

> "Almost every AI trading agent asks the same question — is the market going up, or down?
>
> Over a four-day competition, that's a coin flip.
>
> So we built one that doesn't have to answer it. **The Specialist doesn't predict the market. It makes a market.**"

*(pause 1 beat)*

---

## 0:15 – 0:45 · WHAT IT DOES

**SHOW:** Scroll to **Quote / hedge activity feed**. Let it scroll — density is the point.

> "Think of a currency exchange booth. It doesn't bet on the dollar — it buys at 82, sells at 84, and keeps the difference either way.
>
> Our agent does that with options. It quotes a price to buy and a price to sell on SPY, QQQ, Apple, Nvidia, Tesla and gold — and earns the spread between them.
>
> That's seventy real fills from last session. No forecast anywhere in it."

---

## 0:45 – 1:10 · THE HEDGE ← your strongest moment

**SHOW:** **Specialist Mode inventory** table. Point at the two rows: option delta and stock hedge.

> "But buying an option creates directional risk. So every time it gets filled, it instantly hedges with the underlying stock.
>
> Look at this. The option position carries **minus seventeen thousand dollars** of delta. The stock hedge carries **plus seventeen thousand**.
>
> Net exposure: **fifty-eight dollars.**"

*(pause)*

> "It's holding real risk and carrying almost none of it. That's the whole trick."

---

## 1:10 – 1:40 · WHERE THE AI IS

**SHOW:** **MarketPlan** panel, then the **post-mortem** panel.

> "So where's the AI?
>
> An open-weights model — Qwen 72B running on Featherless — reads the live book and decides **which contracts to quote, and how wide**.
>
> It also reads gold-market headlines from Alpaca's news API and judges how *uncertain* the news flow is — calm, mixed, or turbulent. Turbulent news makes the agent charge more to provide liquidity.
>
> Notice what it never does. **It never picks a direction, and it never places an order.** Strikes, sizing, prices — deterministic code, behind hard risk limits.
>
> An LLM that can size a position can end your account on one bad sample. Ours can only ever make it more careful."

---

## 1:40 – 2:00 · IT KNOWS WHAT'S COMING

**SHOW:** the risk-gate log line mentioning Non-Farm Payrolls

> "Everything else this agent reads is reactive — prices that already moved.
>
> A scheduled economic release is the one thing it can know in advance. And Non-Farm Payrolls printed **inside** this competition window, an hour before the final session.
>
> So it widened its quotes, stopped opening new risk, went silent across the print — then re-engaged once the uncertainty premium collapsed.
>
> It has no opinion on the jobs number. Only that uncertainty is scheduled, priced, then resolved."

---

## 2:00 – 2:20 · BUILT BY BREAKING IT

**SHOW:** scroll the **Risk gate event log**

> "These gates aren't decorative — that's every one that fired last session.
>
> And most of this exists because running it live broke it first. Alpaca rejects naked short calls. It rejects a resting bid and ask on the same contract. It can't compute Greeks for same-day expiries at all.
>
> And the one that mattered most — we read our own fill tape and found our market maker was **paying** the spread instead of earning it. Thirty-three round trips, minus eighty-five dollars. We fixed it with an inventory cost floor and wrote a test that replays the exact failure.
>
> Sixty-three tests. Several exist because the market embarrassed us first."

---

## 2:20 – 2:40 · WHERE THIS GOES

**SHOW:** GitHub repo file list, or a simple roadmap slide

> "This is an MVP, and the road from here is concrete.
>
> Streaming quotes over WebSocket instead of polling — that closes the thirty-second window where a market maker gets picked off. A real volatility surface instead of pricing each contract alone. And Avellaneda–Stoikov, the standard model for inventory-aware quoting — our cost floor is a rough first approximation of what it does properly.
>
> And this isn't only a hackathon toy. Liquidity provision is a real business. The same loop — quote, hedge, respect a risk budget, log every decision — is what desks run on. Scaled down, it's how a retail trader could earn spread instead of paying it. Scaled up, it's a market-making book."

---

## 2:40 – 2:50 · CLOSE

**SHOW:** slow scroll of the full dashboard, end on the header

> "No server. No database. A scheduled process, an append-only ledger, and a static page that holds no credentials. Every decision is reconstructable.
>
> Everyone else built a bot that guesses the market. We built one that **makes** a market — and you can audit every decision it made.
>
> Account `PA318JJN6DXK`. It's open for inspection."

---

## IF THE P&L COMES UP

Don't apologise. Say:

> "We're slightly negative on a four-day window — which is far too short for any options strategy to show statistical significance, and we haven't pretended otherwise. What this account shows is a process running unattended and behaving exactly as specified."

## DELIVERY

- **Slow down.** ~430 words over 2:50 is comfortable. Nerves make you rush.
- Pause after each section — easier to edit, and the points land.
- **The −$58 net delta is the moment.** Say it slowly, let it sit.
- If a section fumbles, re-record that section only.

## IF YOU NEED TO CUT TO 2 MINUTES
Drop **2:00–2:20** (Built by breaking it). Keep hook, hedge, AI, NFP, future, close.

## TWO LINES TO MEMORISE
> "We built one that makes a market."
> "An LLM that can size a position can end your account on one bad sample."
