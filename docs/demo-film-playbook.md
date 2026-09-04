# Demo-film playbook — record a perfect narrated product video (generalized)

A reusable recipe for turning **any** web app / prototype into a polished, narrated
walkthrough video — 1080p, 60fps, burned-in subtitles, chapters — recorded locally,
free, with no cloud services and no touching a live tenant.

> **How to use this in a new chat.** Paste this file and one line of intent, e.g.
> *"Make a demo film of the app at `path/to/app` — cover these modules/roles, ~7 min,
> start with a case-study slide."* The assistant should then follow §2 to plan the
> structure and §3–§10 to build it, applying every rule in §11–§12. This document is
> the spec; the assistant writes the recorder to match it.
>
> **➡️ For THIS project, the concrete brief — links, segment plan, narration script and
> the two ways this app differs from the playbook's assumptions — is in §14 at the end.
> Read §14 first, then come back and apply §2–§12.**

---

## 0 · The result you are aiming for

- One `.mp4`, **1920×1080, 60fps, H.264/yuv420p + AAC**, plus a sidecar `.srt`.
- Opens on a **case-study / title slide**, then the app, **module by module**.
- Every feature is shown by **actually clicking the real UI** with a **visible cursor** —
  never a scripted "guided tour" overlay, never a slideshow of screenshots.
- **Narration** (local neural TTS) with **subtitles burned into the picture**.
- **Chapter markers** so a viewer can jump between sections.
- Nothing stutters, nothing flashes white, no page loads between shots.

---

## 1 · The five golden rules (learned the hard way)

1. **Record module-by-module as separate short files, then merge.** Do **not** record
   one long continuous take. A 10-minute WebGL-heavy take crashes the headless browser
   ("Target page/context closed") intermittently and loses everything. Short (~20–60s)
   fresh-browser sessions are stable, fast, individually verifiable, and re-renderable
   in isolation. Concatenate at the end.
2. **Click the real controls.** Drive the app's own buttons/nav/inputs so the real UI
   responds. If the app has a "guided demo / spotlight" engine, **do not use it** — it
   hides the actual features behind a scripted overlay. Fire the real handlers.
3. **Fit the audio to the picture, not the picture to a plan.** Render each narration
   line to a WAV first and **measure** it. Record the screen action, note the wall-clock
   moment each line should start, then place each WAV at its mark. Hold each step at
   least as long as its narration so audio never bleeds into the next step.
4. **Everything local, everything free.** Piper (neural TTS, MIT, offline), Playwright
   (`recordVideo`), `ffmpeg-static`. No API keys, no per-render cost, nothing leaves the
   machine, no live/production data in the file.
5. **Cover the app until you're ready to show it.** The browser paints a white frame or
   two before CSS/JS; the app may boot in a light theme; navigations flash. A full-screen
   opaque cover + title-card-first entrances make every shot start clean.

---

## 2 · Requirement → film structure (the planning step)

Given an app and a one-line intent, decide the **segment list** before writing anything.

**Choose an axis:**
- **Role-wise** if the app has distinct personas with different screens (Developer,
  Approver, Finance…). One segment per persona journey; switch role via the app's own
  role picker (a real click).
- **Module-wise** if it's one role with many features. One segment per feature/screen.
- Usually a blend: a couple of hero role-journeys + a breadth tour of key modules.

**Standard skeleton (reorder/trim to the ask):**

| # | Segment | Kind | Purpose |
|---|---|---|---|
| 1 | Case study | slides | Problem · who it's for · the cost of the status quo |
| 2 | Login / entry | login | The front door → one real click into the app |
| 3…n | One per module/role | module | The feature, shown by real clicks |
| last | Close | slides | One-line thesis + who it's built on/by |

**Per-segment budget:** ~2–5 narration lines, ~20–60s each. A 12–15 segment film lands
around 6–8 min. Longer than that, split into more segments — never a longer single take.

**Pick which features to show:** favour the ones with a **visible state change**
(applying a fix, uploading data, a value recomputing, a celebration) over static
read-only screens. A live change is worth three dashboards. See §7.

**Write narration in the app's own vocabulary**, one idea per line, ~1 sentence
(~6–9s). The first line of a module = its title-card line (spoken over the card).

---

## 3 · Toolchain (versions & the quirks that bite)

| Piece | What | Notes |
|---|---|---|
| **Piper** | local neural TTS → WAV | ONNX voice files ~60–120 MB. Default voice: `en_US-ryan-high` (warm, explanatory). Alternatives: `en_GB-alan-medium` (documentary), `en_US-lessac-high` (subtitle-clear). Avoid multi-speaker sets (`vctk`,`libritts`). |
| **Playwright** | drives the browser, `recordVideo` (WebM) | **Needs Node 20+** (Chromium refuses 18). |
| **ffmpeg-static** | audio mux, subtitle burn, concat, encode | Confirm the build has **libass** (`-filters | grep subtitles`). |

**Piper quirks:**
- **espeak-ng data path.** The published wheel bakes espeak's data path from *its* CI
  machine → every render fails unless `ESPEAK_DATA_PATH` points at a dir *containing*
  `espeak-ng-data`, set **before** importing piper (the C lib reads env once at init). A
  `say.py` wrapper that sets this and calls `PiperVoice.load(...).synthesize()` is the
  reliable interface: `python say.py <voice.onnx> <out.wav> "the line"`.
- **Pace.** `PIPER_LENGTH_SCALE ≈ 1.06–1.10` reads a shade slower — good when the viewer
  is also reading subtitles.

**Reuse, don't refetch.** If a previous project already has the Piper venv + voices +
`say.py` + `espeakroot`, and `playwright`/`ffmpeg-static` in a `node_modules`, run the
recorder from there and point it at the new app. (In this workspace: the Admin Ops repo
has all of it — `tools/piper/`, `assets/voices/`, `node_modules/`.)

---

## 4 · The stage (how the app is filmed)

**Serve over `http://`, not `file://`.** ES-module scripts (import maps, three.js) are
blocked over `file://` (CORS "origin null") and silently fall back. A tiny Node static
server over `127.0.0.1:<port>` fixes it. Classic scripts work either way; http is safe
for both.

**Film against seeded/prototype data, never the live tenant:** it's behind sign-in,
usually near-empty, and it's real data you don't want in a shared file. The *code* is
identical; only the rows differ.

**A "tour" page = the app + a thin film overlay.** Copy the app's entry HTML to
`tour.html` and add four fixed overlay elements + `window` hooks the recorder drives:

- `#film-fade` — full-screen cover, **`opacity:1` by default** (hides the boot). Reveal
  with `window.__fade(false)`.
- `#film-title` — the title-card layer (opaque radial-dark bg so nothing bleeds through).
- `#film-cap` — a small top-centre **section-label chip** (`window.__cap(label)`).
- `#film-cursor` — a visible arrow + click-pulse ring, moved via `window.__cursor(x,y)`
  and pulsed via `window.__cursorPulse()`.

Also in the tour page:
- **Dark `<html>` background** (`<html style="background:#0b0b0f">`) so the *first* paint
  before CSS is dark, not white. (This alone kills the white flash at every segment start.)
- **Hide the app's own demo/help bars** (`.demo{display:none!important}`) — narration is
  burned in instead.
- If the app is a classic (non-module) script, **append a tiny hook** exposing what the
  recorder needs to compose views out of shot, e.g.
  `window.__app = { setRole, go(view), ready:true }`. (Top-level `function`s are already
  global; `const`/`let` are not — expose them explicitly.)

**Cache-busting reality:** a `?v=` query only busts the HTML; linked JS/CSS are browser-
cached. When iterating, either hard-navigate fresh contexts (the segment recorder does —
each segment is a new context) or bust CSS via `link.href=…?b=Date.now()`.

---

## 5 · Recording one segment (the algorithm)

For each segment, a **fresh browser context** (stability), then:

1. **Render narration first.** For every line, Piper → WAV, measure its duration.
2. **Open the tour page**, wait until the app hook reports ready, pin/expand any nav so
   labels are legible. The `#film-fade` cover is still up (app hidden).
3. **Title card first.** Show `#film-title` over the cover; **compose the destination
   view behind it out of shot** (role switch, navigation — all real clicks, invisible
   under the card); hold for the title line; then **reveal** (fade the cover + card
   together). Result: *dark → title → the module screen* — never the page before the module.
4. **Steps.** For each step: show the section label, record the mark
   `t = now - t0 + lead`, run the real-click action (§6), then **hold** until the step's
   narration has fully played (`max(action time, narration dur) + beat`).
5. **Stop**, get the WebM (`page.video()`), close the context.
6. **Build the audio track:** an `anullsrc` bed the length of the take, each line
   `adelay`ed to its mark, `amix=…:normalize=0`.
7. **Subtitles:** generate ASS (§8) from the same marks (split long lines into rolling
   ~58-char cues).
8. **Mux → segment mp4:** scale/pad to 1920×1080, `fps=60`, `ass=<file>`, `libx264
   -crf 20 -preset veryfast`, AAC, `+faststart`. Run ffmpeg with `cwd` = the subs dir so
   the `ass=` filename needs no path-escaping.

Slides and login are variants of the same shape (slides = a sequence of title cards over
the cover; login = show the real entry page, then one real click through the door).

---

## 6 · Real clicks with a visible cursor

- **Move a real cursor, then fire the real handler.** Find the element, glide
  `#film-cursor` to its centre (CSS transition ≈ 0.5s), pulse, then trigger its actual
  click. Use `element.click()` (fires the handler, bypasses actionability intercepts) or
  Playwright's `click({force:true})` — plain `.click()` often times out because a fixed
  header/cursor overlaps the target.
- **Prefer real controls over their wrapper rows.** When matching by text, search
  `button, .btn, [role=button], chips` **first**, and only fall back to list-row
  containers (`.li`, `.row`). A parent row contains the button's text too and appears
  first in document order — matching it means you *select the row* instead of *clicking
  the button*, and the feature never fires. (This is the single most common "the click
  did nothing" bug.)
- **Navigation** via the app's real nav items; **role switching** via the app's real
  role picker — both are features worth showing.
- **Canvas/WebGL targets** can't be selected by DOM. Demo those through the surrounding
  real controls (view toggles, buttons) + camera drags (`mouse.down/move/up`), and narrate
  the parts you can't click.

---

## 7 · Show live changes (the thing that makes it a demo)

A demo earns its name when the viewer sees **state change in response to an action**.
For each module, find one and script it as a real click:
- apply a fix / remedy → a count drops, an element appears, a tier climbs;
- upload/paste data → a table or check **recomputes** live (before/after visible);
- toggle/energise → a visible celebration or status flip;
- ask the app's assistant → it answers / navigates on screen.

Verify the change actually happened (e.g. the "N issues" number moved), not just that the
button was clicked. If it didn't move, you probably clicked the wrapper row (§6).

---

## 8 · Subtitles (small, classy, always visible)

Burn them in — a sidecar `.srt` alone won't show in most players, and the user *will*
say "I don't see subtitles."

- **Use ASS, not `subtitles=…:force_style`.** The SRT path scales font against a default
  288px canvas, so sizes come out huge. An ASS file with explicit `PlayResX/Y: 1920/1080`
  makes `Fontsize` real pixels.
- **Classy default:** `Fontsize≈29`, `Bold=0`, off-white `&H00F2F2F2`, a subtle
  translucent box (`BorderStyle=3`, `BackColour≈&H64000000`, `Outline=10` for padding),
  `Alignment=2`, `MarginV≈60`. Split narration into rolling cues (~58 chars) so it reads a
  line or two at a time, not a wall of text.
- Also write the `.srt` sidecar for editing/translation/search.

---

## 9 · Title cards & transitions (no flashes, no page-peeking)

- **Cover-first.** `#film-fade` opaque on load + dark `<html>` bg = the app boot never
  shows.
- **Title card before the module.** Compose the module *behind* the card, then reveal —
  so the viewer never sees the page settle before the content.
- **Cards are a beat, not a lectern.** ~1.5–2.5s, painted *inside* the take (not
  concatenated), so the film never hard-cuts.
- Keep the picture gently moving on long holds (a slow scroll beats a frozen frame).

---

## 10 · Merge + chapters

- **Concat + re-encode once** to uniform CFR: `ffmpeg -f concat -safe 0 -i list.txt -r 60
  -pix_fmt yuv420p -c:v libx264 -crf 20 -c:a aac -movflags +faststart`. (Stream-copy
  concat works only if every part is byte-identical in codec params; a single re-encode is
  safer and cheap.)
- **Chapters:** write an ffmetadata file with one `[CHAPTER]` per segment
  (`TIMEBASE=1/1000`, `START`/`END` in ms from the segment offsets) and `-map_chapters`.
  Set the first chapter's START to 0.
- **zsh gotcha:** `for s in $LIST` does **not** word-split in zsh. Use an array:
  `LIST=(a b c); for s in $LIST`.

---

## 11 · Verify before you ship (per segment + final)

Check against the **file**, not intent:
- Exactly **1920×1080, 60fps, yuv420p, AAC** present.
- **First frame is dark**, not white (sample `-ss 0.1`).
- Each module: **title card first**, then the module (no page flash).
- **Live changes actually changed** (numbers moved / elements appeared).
- **Cursor is visible** landing on the controls it clicks.
- Subtitles present, small/legible, none absurdly short or past the end.
- Segment boundaries in the merged film are clean cuts.
- No frozen stretch that reads as a hang (4–5s reading a screen is fine; ~30s is a hang).

Sample frames with `ffmpeg -ss <t> -i seg.mp4 -frames:v 1 out.png` and actually look.

---

## 12 · Traps that cost real time (checklist)

- **One long take crashes.** Segment it. (§1)
- **Guided-demo overlay hides features.** Use real clicks. (§1, §6)
- **`file://` breaks ES modules** → silent fallback (e.g. no 3D). Serve over http. (§4)
- **White flash at every segment start** = browser's pre-CSS paint. Dark `<html>` bg. (§4,§9)
- **App page flashes before the module** = title card shown too late. Cover-first,
  compose behind the card, reveal. (§9)
- **Aggressive Chromium stability flags can break WebGL** in `recordVideo` (context
  exists but bloom/compositing doesn't paint). Keep launch args minimal
  (`--force-color-profile=srgb`); short segments don't need the heavy flags anyway.
- **Click hits the wrapper row, not the button** → feature silently doesn't fire. Prefer
  real controls in the finder. (§6)
- **Native `element.append(null/undefined)` renders the literal text "null"/"undefined".**
  If a demo screen shows a stray "null", it's an append of a falsy child — fix the source.
- **ASS via SRT force_style is giant.** Use an ASS file with explicit PlayRes. (§8)
- **60fps ≈ 2× the encode time** of 30fps (the real-time take is unchanged). Budget for it.
- **`page.evaluate` has no timeout** — a stalled main thread hangs the recorder with the
  camera rolling. Race every action; cap each segment at ~3× its narration length.
- **Node 18 can't run Playwright.** Use Node 20+ (`nvm use 20` or an explicit path).
- **Cache:** `?v=` busts only the HTML; JS/CSS stay cached. Fresh contexts per segment
  avoid it. (§4)
- **Don't film the live tenant.** Seeded/prototype data only. (§4)

---

## 13 · From nothing to a finished film (the loop)

```text
1. Plan segments from the requirement           (§2)
2. Build/point the tour page + overlays + hook  (§4)
3. Render ONE segment, verify frames            (§5, §11)
4. Fix, repeat for all segments (each isolated) (§5)
5. Concat + chapters → final mp4                (§10)
6. Verify the merged file end-to-end, then ship (§11)
```

Keep the **individual segment files** — re-cutting, reordering, or fixing one module
never means re-rendering the whole film.

---

*This playbook is deliberately app-agnostic. The specifics of any one app — its nav
selectors, its role picker, which buttons trigger live changes — are discovered per app;
the structure, timing, subtitle, transition, and merge techniques above are the constant.*

---
---

# 14 · PROJECT BRIEF — "The Specialist"

**This is the concrete job. Everything above is the method; this section is the subject.**

## 14.1 · Links & context

| | |
|---|---|
| **Repo** | https://github.com/thomasKissflow/alpacaHackathon |
| **Live dashboard (the app to film)** | https://thomaskissflow.github.io/alpacaHackathon/dashboard/ |
| **Local source** | `dashboard/index.html`, `dashboard/app.js`, `dashboard/style.css` |
| **Data it renders** | `data/dashboard.json` (static snapshot, no API keys, safe to film) |
| **Alpaca paper account** | `PA318JJN6DXK` |

**What it is:** an autonomous options **market-making** agent for the lablab.ai × Alpaca
hackathon. It does not predict market direction. It quotes a buy price and a sell price on
stock options, earns the spread between them, and cancels the resulting directional risk by
hedging with the underlying shares. A second strategy sells defined-risk option spreads.
An open-weights LLM (Qwen2.5-72B on Featherless) advises on *what to quote and how wide*
and classifies gold-news sentiment — but **never places an order**.

**Deeper context, if useful:** `docs/write-up-onepage.md`, `docs/tech-stack.md`,
`docs/MORNING-BRIEF.md` in the repo.

## 14.2 · ⚠️ Two ways this app breaks the playbook's assumptions

Read these before planning segments — they change §2, §6 and §7 materially.

**(a) There is no login, no roles, and almost nothing to click.**
The dashboard is a single read-only scrolling page. There is no nav, no role picker, no
buttons that mutate state. So:
- Skip the **login** segment entirely.
- The film axis is **section-wise**, not role-wise or module-wise.
- §6's "real clicks with a visible cursor" mostly becomes **cursor-guided scrolling and
  pointing**: glide `#film-cursor` to the row/gauge being narrated and pulse it there, then
  scroll. Keep the cursor — it's what makes it feel like a walkthrough — but do not invent
  clicks that do nothing.

**(b) The "live change" (§7) is not in the browser — it's in a terminal.**
The most important thing to show is the **agent actually running**. That is a CLI process,
not a web UI. Handle it as **terminal capture segments** intercut with dashboard segments:
- Record a real terminal (or a styled full-screen `<pre>` in the tour page replaying real
  captured output — either is acceptable; a real terminal is better).
- The three commands worth filming, in this order:
  1. `python3 preflight.py` — account reachable, market clock, ~10,000 SPY option contracts
     with live Greeks. Good, dense, credible output.
  2. `python3 -c "from agent import news_agent; r=news_agent.current_read(force=True); print(r.regime, '|', r.summary)"`
     — pulls real Benzinga headlines via Alpaca's news API and prints the LLM's verdict.
  3. `python3 -m agent.daemon` — the live loop. Shows cycles, quotes, hedges, and
     `[event]` / `[news]` / `cost floor` lines.
- **This is the film's "state change".** The dashboard proves the *result*; the terminal
  proves the *agent*. Give the terminal real screen time — the brief explicitly asks to
  showcase the backend running and the news inference.

## 14.3 · Actual dashboard structure (verified — film in this order)

Sections top to bottom, exactly as they appear:

| # | Section heading | What's in it | Worth filming? |
|---|---|---|---|
| 1 | **ACCOUNT** | Equity, Day P&L, Specialist P&L, Convexity P&L cards | ✅ opener |
| 2 | **Equity curve** | line chart, "since first snapshot" | ✅ brief |
| 3 | **Portfolio Greeks vs. risk gate caps** | 3 gauges — Net delta / vega / gamma, each `% of cap`. Subtitle reads *"deterministic, zero LLM in this path"* | ✅ **hero** |
| 4 | **Strategy Intent** | *"latest LLM MarketPlan, risk-gate approved"* — symbols, per-symbol target spread bps, mode weights, and the model's own rationale | ✅ **hero (the AI)** |
| 5 | **Specialist Mode inventory** | table: SYMBOL / MODE / QTY / DELTA $ / GAMMA / VEGA $ / THETA $ — contains both the option rows and the share-hedge rows | ✅ **hero (the hedge)** |
| 6 | **Convexity Mode positions** | UNDERLYING / TYPE / STATUS / ENTRY CREDIT / MAX LOSS | ✅ brief |
| 7 | **Working orders** | resting orders, often "0 resting" when closed | ⬜ skip if empty |
| 8 | **Recent fills & hedges** | long timestamped feed of `FILL` then `HEDGE` pairs | ✅ **hero (the proof)** |

**The single most important shot** is §5 + §3 together: in the inventory table the Tesla
*option* rows read roughly **−$21,334** and **−$18,506** of delta, and directly below the
Tesla *share* row reads about **+$39,945**. They cancel. The Net-delta gauge in §3 then
shows the leftover — around **$48, 0% of cap**. Film the table, then the gauge, and let the
narration connect them. That is the whole thesis in two shots.

**In §8, the pattern to hold on:** a `FILL` line immediately followed one second later by a
`HEDGE` line showing delta moving (e.g. `delta 55→110`). Scroll slowly enough that a viewer
sees the pairing repeat.

⚠️ **Numbers change.** Re-read the live JSON before writing narration and substitute
current figures — do not hard-code the ones above:
`curl -s https://thomaskissflow.github.io/alpacaHackathon/data/dashboard.json | python3 -m json.tool | head -60`

## 14.4 · Segment plan

| # | Segment | Kind | ~len |
|---|---|---|---|
| 1 | Title / thesis — "most bots guess; this one runs a shop" | slides | 25s |
| 2 | **Terminal:** preflight — the agent connecting to the live market | terminal | 35s |
| 3 | **Terminal:** news pull + LLM verdict on gold sentiment | terminal | 40s |
| 4 | Dashboard: ACCOUNT + equity curve | dashboard | 25s |
| 5 | Dashboard: **Strategy Intent** — the AI's plan and its own rationale | dashboard | 40s |
| 6 | Dashboard: **Specialist inventory** — the hedge cancelling out | dashboard | 45s |
| 7 | Dashboard: **Greeks vs caps** — the leftover risk, 0% of cap | dashboard | 30s |
| 8 | Dashboard: **Recent fills & hedges** — fill→hedge, over and over | dashboard | 35s |
| 9 | Dashboard: Convexity positions — the capped-loss second strategy | dashboard | 20s |
| 10 | **Terminal:** the daemon running a live cycle | terminal | 30s |
| 11 | Close — why this is better + account ID | slides | 25s |

**≈ 5 minutes.** Trim 9 and shorten 8 if a tighter cut is wanted. Do not exceed ~6 min.

## 14.5 · Narration script

Plain, concrete language. No jargon left unexplained. One idea per line.

**1 · Title**
> "This is The Specialist — an autonomous options trading agent."
> "Most trading bots try to guess whether the market goes up or down. Over a few days, that's a coin flip."
> "Ours doesn't guess. It runs a shop."
> "A shop buys at eighty, sells at a hundred, and keeps the difference — whichever way prices move. This agent does that with stock options."

**2 · Terminal — preflight**
> "Here's the agent connecting to the live market."
> "It's checking the trading account, the market clock, and the option data feed."
> "Ten thousand option contracts on the S&P alone, each with live pricing — that's what it picks from."

**3 · Terminal — news + AI**
> "Now the part that uses AI."
> "Alpaca's news API carries the Benzinga financial wire. The agent pulls the latest gold stories."
> "It sends the headlines to an open-source model — Qwen seventy-two B, running on Featherless."
> "The model answers one question: is the mood calm, mixed, or nervous?"
> "Nervous news makes the agent widen its prices — it charges more to trade when things look unstable."

**4 · Dashboard — account**
> "This is the dashboard. It reads a snapshot the agent writes after every cycle."
> "Account value, profit and loss, split between the two strategies it runs."

**5 · Dashboard — Strategy Intent**
> "This is the AI's actual plan, and it's written in the agent's own words."
> "It chose which symbols to quote, and how wide a price gap to leave on each one."
> "But notice — the AI never places a trade. It advises. Ordinary code does all the trading, behind fixed safety limits it cannot override."
> "An AI that can decide position sizes can empty an account on one bad answer. This one can only ever make it more cautious."

**6 · Dashboard — the hedge**
> "Here's the clever part."
> "When the agent sells someone an option, it's suddenly exposed — if the price moves the wrong way, it loses."
> "It never wanted that bet. It only wanted the small gap it earns."
> "So it instantly buys or sells the actual shares to cancel the exposure out."
> "Look — these option rows carry tens of thousands of dollars of risk. The share row directly below carries almost exactly the opposite."
> "They cancel."

**7 · Dashboard — Greeks vs caps**
> "And this is what's left over."
> "Three hard limits on how much risk the whole account can carry — and no AI touches any of them."
> "It handled forty thousand dollars of exposure and kept almost none of it. That's what lets it keep trading safely all day."

**8 · Dashboard — fills & hedges**
> "You can watch it happen here — every trade, in order."
> "A fill: it bought an option. One second later, a hedge: it bought shares, and the exposure moves."
> "Fill. Hedge. Fill. Hedge. All night, unsupervised, while we were asleep."

**9 · Dashboard — Convexity**
> "A second strategy runs alongside it, selling option spreads with a fixed maximum loss."
> "The worst case is known before the trade is placed. It can't blow up."

**10 · Terminal — daemon**
> "And this is the whole thing running."
> "Every cycle: check the market, reprice, re-hedge, write it all down."

**11 · Close**
> "So why is this better?"
> "A bot that guesses direction has to be right. This one earns a little every time someone trades with it, and hedges away the direction — so it doesn't care which way the market goes."
> "It isn't a prediction. It's a service."
> "Account P-A-3-1-8-J-J-N-6-D-X-K — open for inspection."

## 14.6 · Tone & style

- **Dark theme already** — the dashboard is dark, so §4/§9's white-flash problem is mostly
  solved, but still set the dark `<html>` background on the tour page.
- Voice: `en_US-ryan-high`, `PIPER_LENGTH_SCALE≈1.08`. Explanatory, unhurried, not hyped.
- Terminal segments: large monospace, high contrast, and **let real output scroll** —
  do not fake it.
- Slow down on two lines: *"They cancel."* and *"It's a service."* Leave a beat after each.
