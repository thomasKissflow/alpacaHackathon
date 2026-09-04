# Video Script — The Specialist

> **Target: 3 minutes.** Judges watch a lot of these; the first 15 seconds decide whether they lean in.
> **Format:** screen recording with voiceover. No talking head needed. Do not read this word-for-word — know each beat and say it naturally.
> **Record the dashboard walkthrough live.** Movement beats static screenshots.

---

## Before you hit record — 15 min of prep

- [ ] Dashboard open at https://thomaskissflow.github.io/alpacaHackathon/dashboard/ — **fresh data loaded**
- [ ] A terminal with the daemon running, so you can show real log lines
- [ ] Second browser tab: the GitHub repo
- [ ] Close Slack/mail; silence notifications
- [ ] Screen at 1080p or higher; hide bookmarks bar
- [ ] Do **one** practice run start-to-finish before the real take

---

## 0:00–0:20 — The hook

**SHOW:** Slide 1 (title), then cut to a candlestick chart with a question mark.

> "Almost every AI trading agent asks the same question: *is the market going up, or down?*
>
> Over a four-day competition, that's a coin flip.
>
> So we built something that doesn't have to answer it. **The Specialist doesn't predict the market. It makes a market.**"

**Beat.** Let that land.

---

## 0:20–0:50 — What that actually means

**SHOW:** Simple graphic — a currency exchange booth, "BUY 82 / SELL 84". Then cut to the real fill in your activity feed.

> "Think of a currency exchange at an airport. It doesn't bet on the dollar. It buys at 82, sells at 84, and keeps the difference — whichever way the market moves.
>
> Our agent does exactly that with options. Here's a real pair of fills from last night: it bought a Nvidia put at 3.20, and sold the same contract at 3.25.
>
> No forecast. No opinion. Just the spread."

**SHOW:** scroll the Quote / hedge activity feed so they see it's dense and real.

---

## 0:50–1:20 — The hard part

**SHOW:** Slide 4 — the two bars cancelling. Then the Specialist Mode inventory table on the dashboard.

> "But buying that put creates directional risk. If the market moves, we lose.
>
> So every single time the agent gets filled, it immediately hedges with the underlying stock.
>
> Look at these numbers. The options position carries **minus seventeen thousand dollars** of delta. The stock hedge carries **plus seventeen thousand**. Net exposure: **fifty-eight dollars.**
>
> It's holding real risk, and carrying almost none of it. That's the whole trick — and it's what lets it hold inventory patiently instead of dumping at a loss."

---

## 1:20–1:50 — Where the AI sits

**SHOW:** Slide 5 (two columns). Then the MarketPlan / post-mortem panel on the dashboard.

> "Now — where's the AI?
>
> An open-weights model on Featherless reads the live book and decides **which contracts to quote and how wide**. It also reads gold-market headlines from Alpaca's news API and classifies how *uncertain* the news flow is — calm, mixed, or turbulent. Turbulent news makes the agent charge more to provide liquidity.
>
> Notice what it never does: **it never picks a direction, and it never places an order.** Strikes, sizing, prices, and whether to trade at all — that's deterministic code behind hard risk gates.
>
> An LLM that can size a position can end your account on one bad sample. Ours can only ever make the system more conservative."

---

## 1:50–2:20 — It knows what's coming

**SHOW:** Slide 7 — the NFP timeline.

> "Everything else this agent reads is reactive — prices that have already moved.
>
> A scheduled economic release is the one thing it can know in advance. And Non-Farm Payrolls — the biggest data release of the month — printed **inside** this competition window, an hour before the final session opened.
>
> So twenty hours before the print, the agent widens its quotes and stops opening new short premium. Across the release itself, it places nothing. Then once the number is out and the uncertainty premium has collapsed, it re-engages and quotes tighter.
>
> It has no opinion on the jobs number. Only on the fact that uncertainty is scheduled, priced, and then resolved."

---

## 2:20–2:50 — Built by breaking it

**SHOW:** the risk-gate event log, scrolling. Then a terminal with a real rejection message.

> "These risk gates aren't decorative — that log is every gate that fired last session.
>
> And most of what's in this system exists because running it live broke it first. Alpaca rejects naked short calls, so we quote puts only. It rejects a resting bid and ask on the same contract, so we quote one side at a time. It can't compute Greeks for same-day expiries at all.
>
> And the one that mattered most: our market maker was **paying** the spread instead of earning it — it was flattening inventory below its own cost. Thirty-three round trips, minus eighty-five dollars. We found it, fixed it, and wrote a test that replays the exact failure.
>
> Sixty-three tests. Several of them exist because the market embarrassed us first."

---

## 2:50–3:00 — Close

**SHOW:** full dashboard, scrolling slowly top to bottom. End on the account ID.

> "No server. No database. A scheduled process, an append-only ledger, and a static dashboard that holds no credentials. Every decision the agent made is reconstructable.
>
> Everyone else built a bot that guesses the market. We built one that **makes** a market — and you can audit every decision it made.
>
> The account is `PA318JJN6DXK`. It's open for inspection."

---

## Delivery notes

- **Slow down.** Nervous recording runs fast. Aim for a measured pace — you have three minutes for ~450 words, which is comfortable.
- **Pause after each section.** Easier to edit, and it gives the point room.
- **Don't apologise for the P&L.** If you mention it: *"a four-day window is far too short for statistical significance — what this account shows is a process running unattended and behaving exactly as specified."* Confidence, not defensiveness.
- **The −$58 net delta number is your single most impressive moment.** Land it clearly.
- **If a take goes wrong, restart that section** rather than the whole video.

## Two lines worth memorising

> "We built one that makes a market."
> "An LLM that can size a position can end your account on one bad sample."
