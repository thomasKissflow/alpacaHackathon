# Morning Brief — Fri 4 Sep 2026

> Written overnight while you slept. **Read this first.**
> Deadline **today 20:30 IST**. Market opens **19:00 IST**. NFP prints **18:00 IST**.

---

## TL;DR

**One major bug found and fixed: the market maker was losing money on every round trip.** 63 tests pass. Write-ups (both versions) and full slide content are written. The idea is genuinely differentiated and the engineering is strong — but **P&L is our weak criterion and cannot be fixed in 90 minutes**, so the submission has to win on the other four.

---

## 🔴 The big finding: the core economics were inverted

I analysed Thursday's real fills. **33 round trips. Gross spread captured: −$85.**

A market maker that loses on its round trips is being picked off, not making a market. The actual tape:

```
18:38:17  buy  @ 11.10
18:38:22  → agent quotes SELL at 10.92    (18¢ BELOW its own cost)
18:39:26  sell @ 10.95                     LOSS
18:41:47  buy  @ 11.10
18:43:06  sell @ 10.90                     LOSS
```

**Cause:** `_quote_put` priced *both* sides purely off the current market mid. The position's average cost was fetched and never used. So the moment it held inventory, it quoted the closing side at whatever the mid had drifted to — flattening at a loss, every time. It was *paying* the spread it was supposed to earn.

**Fix:** `apply_inventory_cost_floor()` — the closing side is never quoted below cost plus a minimum edge (25bps of mid, minimum one tick). Opening is still priced off the market, because that is where the edge comes from. If the market doesn't come back, we simply don't fill and keep the inventory — which is safe precisely because every fill is delta-hedged, so holding is a vol/theta position, not a directional bet.

**Verified by replaying the real tape through it:** 5 of 13 loss-making fills prevented; the completed round trip realises +$5 instead of a loss.

**Tradeoff you should know about:** fewer fills. Losing money on all of them was worse. **Set to 10bps (D-017)** so closes happen more readily while still guaranteeing positive edge. If fills still look sparse mid-session, the knob is `min_close_edge_bps` in `agent/config.py`.

---

## ✅ Verified working

| Check | Result |
|---|---|
| Test suite | **63 passed** |
| Strike selection, all 7 symbols | All select valid **OTM** puts, incl. GLD and IAU |
| Delta cap raise | **SPY and QQQ now fit** ($31k / $34k vs $60k cap) — they were completely blocked before |
| Gold quote quality | GLD spread **3.6%** — better than TSLA (5.3%) and AAPL (8.3%) |
| Featherless | Live, `source='llm'`, real symbols and rationale |
| News Agent | Live on real Alpaca headlines → regime `mixed` |
| NFP posture for today | de-risk → blackout 18:00–19:15 → **re-engage 19:15–20:30** ✅ |

**Friday timeline is correct:** the agent sits out the print and the volatile open, then trades actively for the 75 minutes before the deadline.

---

## ⚠️ Known weaknesses (do not be surprised by these)

1. **P&L is negative** — Thursday closed at **$99,513 (−0.49%)**. One session of history against competitors who have had a week. The cost-floor fix should improve the economics but 90 minutes cannot build a track record.
2. ~~**IAU's market is 11.5% wide**~~ — **RESOLVED (D-017):** IAU dropped, GLD retained.
3. **The SPY bull put spread has a poor credit/risk ratio** — $50 credit against $450 max loss (1:9). Entered when IV was low. Not worth changing now.
4. **Social workstream skipped** (your call). That forfeits one of five judging criteria *and* a separately-winnable $500 + Algo Trader Plus. **If you find a spare hour, this is still the highest return-per-hour work available** — the competition for it is thin because most teams ignore it.

---

## 🏆 Is this winnable? — honest assessment

**Where we are strong:**
- **Creativity & Originality — very strong.** Market making is market *microstructure*, not prediction. None of the 12 published competitors touch it. "Everyone built a bot that guesses the market; we built one that makes a market" is a genuinely differentiated line.
- **Technology Implementation — very strong.** CLI + Trading API + Options Market Data + News API + MCP + Featherless. Three Alpaca staff are judging, and the write-up cites platform constraints only discoverable by running it.
- **Presentation — potentially strong,** but entirely dependent on a video that does not exist yet.

**Where we are weak:**
- **P&L — poor.** One partial session, negative. Unfixable now.
- **Social — zero** unless you reverse that decision.

**Verdict:** a top-3 finish is plausible **if** judges weight the four controllable criteria comparably to P&L. If P&L dominates, we will not place — a team that has been live since Monday with a lucky long-gamma book will beat us on that axis no matter what we do. The rational play is exactly what we've done: be the most *interesting and rigorous* submission in the field, and be honest about the P&L rather than dressing it up. Several competitors lead with "refuses to trade when no edge is proven" — they will have *no* activity to show. We have 70 fills, 95 hedges and a working risk log.

---

## ▶️ Your morning, in order

1. **`git pull`** — everything below is already pushed.
2. **`python3 preflight.py`** — confirm the account is still clean and reachable.
3. **Record the video.** This is the single highest-value remaining task. Full running order in [slides.md](slides.md). **Budget 4 hours.**
4. **Cover image + slides** — content is written, just needs designing.
5. **19:00 IST: restart the agent** so the final session trades:
   ```
   caffeinate -is python3 -m agent.daemon
   ```
   plus `./publish.sh` in a second terminal.
6. **Watch the first cycles** — gold quoting, `[news] gold regime ...`, and `cost floor` lines are all new and have never run in a live session.
7. **Submit by 19:45 IST.** Checklist in [submission-checklist.md](submission-checklist.md).

---

## 📦 What I produced overnight

| File | What |
|---|---|
| `agent/specialist_mode.py` | Inventory cost floor — the big fix |
| `tests/test_inventory_cost_floor.py` | 8 tests, incl. the exact live failure case |
| `docs/write-up-onepage.md` | **714 words** — strict one-pager for the submission field |
| `docs/write-up.md` | Full ~1,340-word version for the long description |
| `docs/slides.md` | 10 slides with speaker notes, cover-image spec, 3-min video running order |
| `docs/MORNING-BRIEF.md` | This file |

**Resolved since:** IAU dropped, `min_close_edge_bps` = 10 (D-017). **Still open:** reinstate the social workstream?
