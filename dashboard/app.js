/*
 * Static dashboard. Reads data/dashboard.json -- a single JSON snapshot that
 * agent/dashboard_export.py regenerates from the SQLite ledger every cycle.
 * No backend, no Alpaca keys in the browser, and deliberately NO order-entry
 * controls: the agent is fully autonomous, so there is nothing here for a
 * human to click "buy" or "sell" on.
 *
 * Want the frontend to poll Alpaca directly instead (e.g. for a local demo
 * recording)? See dashboard/alpaca-direct.example.js -- deliberately NOT
 * wired in by default, because embedding a secret key in shipped JS lets
 * anyone who opens dev tools trade on your paper account and corrupt the
 * P&L judges will read.
 */

const DATA_URL = "../data/dashboard.json";

async function fetchSnapshot() {
  const res = await fetch(`${DATA_URL}?t=${Date.now()}`);
  if (!res.ok) throw new Error(`failed to load dashboard.json: ${res.status}`);
  return res.json();
}

function fmtMoney(n) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return n.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}
function fmtSigned(n) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return `${n >= 0 ? "+" : ""}${fmtMoney(n)}`;
}
function fmtTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
function fmtAge(iso) {
  if (!iso) return "—";
  const s = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  return `${Math.floor(s / 3600)}h`;
}
function pnlColor(n) { return n >= 0 ? "var(--green)" : "var(--red)"; }
function esc(s) { return String(s ?? "").replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c])); }

// ==================================================== candlestick chart ===
// Hand-rolled canvas renderer (no charting library) so there's no CDN
// version-compatibility gamble on demo day. Candles are REAL OHLC data --
// agent/dashboard_export.py buckets real equity snapshots by time, it does
// not fabricate price action. Moving averages are simple averages of that
// same real equity series; "volume" is real trade-activity count per
// bucket (fills + hedges + new orders), not fabricated share volume.

function _sma(values, window) {
  const out = new Array(values.length).fill(null);
  for (let i = window - 1; i < values.length; i++) {
    let sum = 0;
    for (let j = i - window + 1; j <= i; j++) sum += values[j];
    out[i] = sum / window;
  }
  return out;
}

function _setupCanvasDPR(canvas) {
  const dpr = window.devicePixelRatio || 1;
  const cssWidth = canvas.parentElement.clientWidth || canvas.width;
  const cssHeight = canvas.height / (canvas.width / cssWidth) || canvas.height;
  const targetHeight = canvas.dataset.cssHeight ? parseInt(canvas.dataset.cssHeight, 10) : canvas.height;
  canvas.style.width = cssWidth + "px";
  canvas.style.height = targetHeight + "px";
  canvas.width = cssWidth * dpr;
  canvas.height = targetHeight * dpr;
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx, width: cssWidth, height: targetHeight };
}

function renderCandleChart(snapshot) {
  const candles = snapshot.equity_candles || [];
  const priceCanvas = document.getElementById("candle-price");
  const volCanvas = document.getElementById("candle-volume");
  priceCanvas.dataset.cssHeight = "280";
  volCanvas.dataset.cssHeight = "56";

  const { ctx: pctx, width: W, height: PH } = _setupCanvasDPR(priceCanvas);
  const { ctx: vctx, width: _VW, height: VH } = _setupCanvasDPR(volCanvas);
  pctx.clearRect(0, 0, W, PH);
  vctx.clearRect(0, 0, W, VH);

  if (candles.length === 0) {
    pctx.fillStyle = "#8b93a7";
    pctx.font = "12px -apple-system, sans-serif";
    pctx.fillText("Waiting for enough equity history to draw a candle…", 12, PH / 2);
    document.getElementById("ma-legend").innerHTML = "";
    return;
  }

  const RIGHT = 58, LEFT = 6, TOP = 10, BOTTOM = 18;
  const plotW = W - LEFT - RIGHT;
  const plotH = PH - TOP - BOTTOM;

  let lo = Math.min(...candles.map((c) => c.l));
  let hi = Math.max(...candles.map((c) => c.h));
  if (hi === lo) { hi += 1; lo -= 1; }
  const pad = (hi - lo) * 0.12;
  lo -= pad; hi += pad;

  const n = candles.length;
  const slot = plotW / n;
  const bodyW = Math.max(2, Math.min(16, slot * 0.62));
  const xAt = (i) => LEFT + slot * i + slot / 2;
  const yAt = (price) => TOP + plotH - ((price - lo) / (hi - lo)) * plotH;

  // grid + price labels
  pctx.strokeStyle = "#171b27";
  pctx.fillStyle = "#8b93a7";
  pctx.font = "10.5px SFMono-Regular, Menlo, monospace";
  pctx.textBaseline = "middle";
  const gridLines = 4;
  for (let g = 0; g <= gridLines; g++) {
    const price = lo + ((hi - lo) * g) / gridLines;
    const y = yAt(price);
    pctx.beginPath();
    pctx.moveTo(LEFT, y);
    pctx.lineTo(LEFT + plotW, y);
    pctx.lineWidth = 1;
    pctx.stroke();
    pctx.fillText("$" + price.toLocaleString(undefined, { maximumFractionDigits: 0 }), LEFT + plotW + 6, y);
  }

  // candles
  for (let i = 0; i < n; i++) {
    const c = candles[i];
    const up = c.c >= c.o;
    const color = up ? "#2fd096" : "#ff5c72";
    const x = xAt(i);
    pctx.strokeStyle = color;
    pctx.fillStyle = color;
    pctx.lineWidth = 1;
    pctx.beginPath();
    pctx.moveTo(x, yAt(c.h));
    pctx.lineTo(x, yAt(c.l));
    pctx.stroke();
    const yOpen = yAt(c.o), yClose = yAt(c.c);
    const bodyTop = Math.min(yOpen, yClose);
    const bodyH = Math.max(1.4, Math.abs(yClose - yOpen));
    pctx.fillRect(x - bodyW / 2, bodyTop, bodyW, bodyH);
  }

  // moving average overlays
  const closes = candles.map((c) => c.c);
  const maSpecs = [
    { window: Math.min(5, n), color: "#4f8cff", label: `MA${Math.min(5, n)}` },
    { window: Math.min(10, n), color: "#8b7bff", label: `MA${Math.min(10, n)}` },
  ].filter((m, idx, arr) => m.window >= 2 && (idx === 0 || m.window !== arr[0].window));

  const legend = document.getElementById("ma-legend");
  legend.innerHTML = maSpecs.map((m) => `<span><span class="sw" style="background:${m.color}"></span>${m.label}</span>`).join("");

  for (const spec of maSpecs) {
    const series = _sma(closes, spec.window);
    pctx.strokeStyle = spec.color;
    pctx.lineWidth = 1.4;
    pctx.beginPath();
    let started = false;
    for (let i = 0; i < n; i++) {
      if (series[i] === null) continue;
      const x = xAt(i), y = yAt(series[i]);
      if (!started) { pctx.moveTo(x, y); started = true; } else { pctx.lineTo(x, y); }
    }
    pctx.stroke();
  }

  // time labels (a handful, evenly spaced)
  pctx.fillStyle = "#8b93a7";
  const labelEvery = Math.max(1, Math.ceil(n / 6));
  for (let i = 0; i < n; i += labelEvery) {
    const d = new Date(candles[i].t);
    const label = d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
    pctx.fillText(label, xAt(i) - 14, TOP + plotH + 12);
  }

  // volume bars, aligned to the same x mapping
  const volByTime = Object.fromEntries((snapshot.activity_volume || []).map((v) => [v.t, v.v]));
  const maxVol = Math.max(1, ...candles.map((c) => volByTime[c.t] || 0));
  for (let i = 0; i < n; i++) {
    const c = candles[i];
    const v = volByTime[c.t] || 0;
    const up = c.c >= c.o;
    const x = xAt(i);
    const h = (v / maxVol) * (VH - 4);
    vctx.fillStyle = up ? "rgba(47,208,150,0.55)" : "rgba(255,92,114,0.55)";
    vctx.fillRect(x - bodyW / 2, VH - h, bodyW, h);
  }
}

// ================================================================ topbar ===

function renderTickers(tickers) {
  const strip = document.getElementById("ticker-strip");
  strip.innerHTML = "";
  const order = ["SPY", "QQQ", "AAPL", "NVDA", "TSLA"];
  const bySymbol = Object.fromEntries((tickers || []).map((t) => [t.symbol, t]));
  for (const sym of order) {
    const t = bySymbol[sym];
    const div = document.createElement("div");
    div.className = "ticker";
    if (!t) {
      div.innerHTML = `<span class="sym">${sym}</span><span class="px mono" style="color:var(--muted-2)">no mark yet</span>`;
      strip.appendChild(div);
      continue;
    }
    const chg = t.prev_close ? ((t.price - t.prev_close) / t.prev_close) * 100 : 0;
    const cls = chg > 0.005 ? "up" : chg < -0.005 ? "down" : "flat";
    const sign = chg > 0 ? "+" : "";
    div.innerHTML = `
      <span class="sym">${sym}</span>
      <span class="px mono">$${t.price.toFixed(2)}</span>
      <span class="chg ${cls} mono">${sign}${chg.toFixed(2)}%</span>
    `;
    strip.appendChild(div);
  }
}

function renderTopStatus(snapshot) {
  document.getElementById("updated-at").textContent = `Last cycle ${fmtTime(snapshot.generated_at)}`;

  const killBadge = document.getElementById("kill-switch-badge");
  if (snapshot.kill_switch_engaged) {
    killBadge.className = "badge danger";
    killBadge.innerHTML = `<span class="dot"></span>Kill Switch Engaged`;
  } else {
    killBadge.className = "badge ok";
    killBadge.innerHTML = `<span class="dot"></span>Risk Engine Online`;
  }
}

function renderFooter(snapshot) {
  const ageSec = (Date.now() - new Date(snapshot.generated_at).getTime()) / 1000;
  const feedStale = ageSec > 180;
  document.getElementById("feed-age").textContent = `· updated ${fmtAge(snapshot.generated_at)} ago`;
  document.getElementById("dot-feed").classList.toggle("bad", feedStale);

  const engineOk = !snapshot.kill_switch_engaged;
  document.getElementById("engine-status").textContent = engineOk ? "· nominal" : "· HALTED (kill switch)";
  document.getElementById("dot-engine").classList.toggle("bad", !engineOk);

  document.getElementById("health-feed").className = "row" + (feedStale ? " warn" : "");
  document.getElementById("health-engine").className = "row" + (engineOk ? "" : " bad");
}

// =============================================================== cockpit ===

function renderStats(snapshot) {
  const history = snapshot.account_history;
  const last = history[history.length - 1];
  document.getElementById("stat-equity").textContent = last ? fmtMoney(last.equity) : "—";

  const dayPnlEl = document.getElementById("stat-day-pnl");
  const specPnlEl = document.getElementById("stat-specialist-pnl");
  const convPnlEl = document.getElementById("stat-convexity-pnl");
  if (last) {
    dayPnlEl.textContent = fmtSigned(last.day_pnl);
    dayPnlEl.style.color = pnlColor(last.day_pnl ?? 0);
    specPnlEl.textContent = fmtSigned(last.specialist_pnl);
    specPnlEl.style.color = pnlColor(last.specialist_pnl ?? 0);
    convPnlEl.textContent = fmtSigned(last.convexity_pnl);
    convPnlEl.style.color = pnlColor(last.convexity_pnl ?? 0);
  }
}

// ================================================================== risk ===

function renderGauges(snapshot) {
  const row = document.getElementById("gauge-row");
  row.innerHTML = "";
  const totals = { delta_dollars: 0, gamma: 0, vega_dollars: 0 };
  for (const p of snapshot.inventory) {
    totals.delta_dollars += p.delta_dollars || 0;
    totals.gamma += p.gamma || 0;
    totals.vega_dollars += p.vega_dollars || 0;
  }
  const gauges = [
    { label: "Net delta", value: totals.delta_dollars, cap: snapshot.risk_config.max_net_delta_dollars, fmt: fmtMoney },
    { label: "Net vega", value: totals.vega_dollars, cap: snapshot.risk_config.max_net_vega_dollars, fmt: fmtMoney },
    { label: "Net gamma", value: totals.gamma, cap: snapshot.risk_config.max_net_gamma_shares_per_dollar, fmt: (n) => n.toFixed(1) },
  ];
  for (const g of gauges) {
    const pct = Math.max(-100, Math.min(100, (g.value / g.cap) * 100));
    const usedPct = Math.min(100, Math.abs(g.value) / g.cap * 100);
    const danger = usedPct > 85;
    const div = document.createElement("div");
    div.className = "gauge";
    // position: 0% cap -> left edge, 0 value -> center, +cap -> right edge
    const dotLeft = 50 + pct / 2;
    const fillFrom = pct >= 0 ? 50 : dotLeft;
    const fillTo = pct >= 0 ? dotLeft : 50;
    div.innerHTML = `
      <div class="gauge-head">
        <span class="gauge-label">${g.label}</span>
        <span class="gauge-pct">${usedPct.toFixed(0)}% of cap</span>
      </div>
      <div class="gauge-track">
        <div class="gauge-mid"></div>
        <div class="gauge-fill ${danger ? "danger" : ""}" style="left:${fillFrom}%; width:${Math.max(0, fillTo - fillFrom)}%"></div>
        <div class="gauge-dot" style="left:${dotLeft}%"></div>
      </div>
      <div class="gauge-bounds"><span>−${g.fmt(g.cap)}</span><span>${g.fmt(g.value)}</span><span>+${g.fmt(g.cap)}</span></div>
    `;
    row.appendChild(div);
  }
}

// ============================================================== strategy ===

function renderIntent(snapshot) {
  const card = document.getElementById("intent-card");
  const plan = snapshot.latest_plan;
  if (!plan) {
    card.innerHTML = `<div style="color:var(--muted)">No MarketPlan generated yet</div>`;
    return;
  }
  const approved = plan.approved;
  const sw = approved.mode_weights?.specialist ?? 0.5;
  const cw = approved.mode_weights?.convexity ?? 0.5;

  const symbolChips = (approved.symbols || []).map((s) => {
    const bps = approved.target_spread_bps?.[s];
    return `<span class="chip">${esc(s)}${bps !== undefined ? `<span class="w">${bps}bps</span>` : ""}</span>`;
  }).join("");

  card.innerHTML = `
    <div class="intent-head">
      <span class="intent-source ${plan.source === "llm" ? "llm" : "fallback"}">${plan.source === "llm" ? "LLM-generated" : "deterministic fallback"}</span>
      <span style="font-size:10.5px;color:var(--muted-2)" class="mono">${fmtTime(plan.ts)}${plan.was_clamped ? " · clamped by risk gate" : ""}</span>
    </div>
    <div class="intent-field">
      <div class="k">Active basket</div>
      <div class="intent-symbols">${symbolChips || '<span style="color:var(--muted)">none</span>'}</div>
    </div>
    <div class="intent-field">
      <div class="k">Mode allocation</div>
      <div class="weight-bar"><div class="specialist" style="width:${sw * 100}%"></div><div class="convexity" style="width:${cw * 100}%"></div></div>
      <div class="weight-legend">
        <span><span class="dot" style="background:var(--accent)"></span>Specialist ${(sw * 100).toFixed(0)}%</span>
        <span><span class="dot" style="background:var(--purple)"></span>Convexity ${(cw * 100).toFixed(0)}%</span>
      </div>
    </div>
    <div class="intent-field">
      <div class="k">Thesis</div>
      <div class="v">${esc(approved.rationale) || "—"}</div>
    </div>
  `;
}

// ============================================================ positions ===

function renderInventory(inventory) {
  const tbody = document.querySelector("#inventory-table tbody");
  tbody.innerHTML = "";
  const rows = [...inventory].sort((a, b) => b.symbol.localeCompare(a.symbol));
  for (const p of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="mono">${esc(p.symbol)}</td>
      <td>${esc(p.mode)}</td>
      <td class="mono num">${p.qty}</td>
      <td class="mono num" style="color:${pnlColor(p.delta_dollars || 0)}">${fmtMoney(p.delta_dollars)}</td>
      <td class="mono num">${(p.gamma ?? 0).toFixed(2)}</td>
      <td class="mono num">${fmtMoney(p.vega_dollars)}</td>
      <td class="mono num">${fmtMoney(p.theta_dollars)}</td>
    `;
    tbody.appendChild(tr);
  }
  if (rows.length === 0) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="7">Flat — no open inventory</td></tr>`;
  }
}

function renderConvexity(snapshot) {
  const tbody = document.querySelector("#convexity-table tbody");
  tbody.innerHTML = "";
  const all = [...snapshot.convexity_open, ...snapshot.convexity_closed];
  for (const c of all) {
    const tr = document.createElement("tr");
    const rightCol = c.status === "closed" ? fmtSigned(c.exit_pnl) : fmtMoney(c.max_loss_estimate);
    tr.innerHTML = `
      <td class="mono">${esc(c.underlying)}</td>
      <td>${esc(c.strategy_type)}</td>
      <td><span class="status-pill ${c.status}">${esc(c.status)}</span></td>
      <td class="mono num">${fmtMoney((c.entry_credit ?? 0) * 100)}</td>
      <td class="mono num" style="color:${c.status === "closed" ? pnlColor(c.exit_pnl ?? 0) : "var(--text)"}">${rightCol}</td>
    `;
    tbody.appendChild(tr);
  }
  if (all.length === 0) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="5">No convexity positions yet</td></tr>`;
  }
}

// ================================================================ orders ===

function renderWorkingOrders(snapshot) {
  const tbody = document.querySelector("#working-table tbody");
  tbody.innerHTML = "";
  const rows = snapshot.working_orders || [];
  document.getElementById("working-count").textContent = `${rows.length} resting`;
  for (const o of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="mono">${esc(o.symbol)}</td>
      <td><span class="side-pill ${o.side === "buy" ? "buy" : "sell"}">${esc(o.side).toUpperCase()}</span></td>
      <td class="mono num">${o.qty}</td>
      <td class="mono num">${o.limit_price !== null ? "$" + o.limit_price.toFixed(2) : "mkt"}</td>
      <td><span class="status-pill ${o.status}">${esc(o.status)}</span></td>
      <td class="mono">${fmtAge(o.ts)}</td>
    `;
    tbody.appendChild(tr);
  }
  if (rows.length === 0) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="6">No resting orders right now</td></tr>`;
  }
}

function renderActivityFeed(snapshot) {
  const events = [
    ...snapshot.fills.map((f) => ({
      ts: f.ts, kind: "filled",
      text: `FILL — ${esc(f.mode)} ${esc(f.side)} ${f.qty} ${esc(f.symbol)} @ ${fmtMoney(f.fill_price)}`,
    })),
    ...snapshot.hedges.map((h) => ({
      ts: h.ts, kind: "hedge",
      text: `HEDGE — ${esc(h.side)} ${h.qty} ${esc(h.underlying)} @ ${fmtMoney(h.price)} (delta ${h.delta_before?.toFixed(0)}→${h.delta_after?.toFixed(0)})`,
    })),
  ].sort((a, b) => new Date(b.ts) - new Date(a.ts)).slice(0, 100);

  const feed = document.getElementById("activity-feed");
  feed.innerHTML = "";
  for (const e of events) {
    const div = document.createElement("div");
    div.className = "feed-entry";
    div.innerHTML = `<span class="ts">${fmtTime(e.ts)}</span><span class="badge-tag badge-${e.kind}">${e.kind}</span><span class="txt">${e.text}</span>`;
    feed.appendChild(div);
  }
  if (events.length === 0) feed.innerHTML = `<div class="feed-entry" style="color:var(--muted)">No fills or hedges yet</div>`;
}

// ================================================================= risk ===

function renderRiskFeed(events) {
  const feed = document.getElementById("risk-feed");
  feed.innerHTML = "";
  for (const e of events) {
    const div = document.createElement("div");
    div.className = "feed-entry";
    div.innerHTML = `<span class="ts">${fmtTime(e.ts)}</span><span class="badge-tag badge-${e.event_type}">${esc(e.event_type)}</span><span class="txt">${esc(e.reason)}</span>`;
    feed.appendChild(div);
  }
  if (events.length === 0) feed.innerHTML = `<div class="feed-entry" style="color:var(--muted)">No rejections or clamps yet — risk gate hasn't had to intervene</div>`;
}

function renderPostmortems(postmortems) {
  const feed = document.getElementById("postmortem-feed");
  feed.innerHTML = "";
  for (const p of postmortems) {
    const div = document.createElement("div");
    div.className = "postmortem-entry";
    div.innerHTML = `<div class="ts">${esc(p.trade_date)}</div><div class="txt">${esc(p.text).replace(/\n/g, "<br>")}</div>`;
    feed.appendChild(div);
  }
  if (postmortems.length === 0) feed.innerHTML = `<div class="feed-entry" style="color:var(--muted)">No post-mortems written yet</div>`;
}

function renderPlans(plans) {
  const feed = document.getElementById("plan-feed");
  feed.innerHTML = "";
  for (const p of plans) {
    const approved = JSON.parse(p.approved_json);
    const div = document.createElement("div");
    div.className = "feed-entry";
    div.innerHTML = `
      <span class="ts">${fmtTime(p.ts)}</span>
      <span class="badge-tag badge-${p.source}">${esc(p.source)}</span>
      <span class="txt">${(approved.symbols || []).join(", ")} — specialist/convexity ${(approved.mode_weights?.specialist ?? 0).toFixed(2)}/${(approved.mode_weights?.convexity ?? 0).toFixed(2)}${p.was_clamped ? " (clamped)" : ""}</span>
    `;
    feed.appendChild(div);
  }
  if (plans.length === 0) feed.innerHTML = `<div class="feed-entry" style="color:var(--muted)">No MarketPlans generated yet</div>`;
}

// ================================================================ scroll ===

function setupScrollSpy() {
  const links = [...document.querySelectorAll(".nav-item")];
  const sections = links.map((l) => document.querySelector(l.getAttribute("href"))).filter(Boolean);
  window.addEventListener("scroll", () => {
    let idx = 0;
    sections.forEach((s, i) => { if (s.getBoundingClientRect().top < 120) idx = i; });
    links.forEach((l, i) => l.classList.toggle("active", i === idx));
  }, { passive: true });
}

// ================================================================== main ===

async function refresh() {
  try {
    const snapshot = await fetchSnapshot();
    renderTickers(snapshot.tickers);
    renderTopStatus(snapshot);
    renderStats(snapshot);
    renderCandleChart(snapshot);
    renderGauges(snapshot);
    renderIntent(snapshot);
    renderInventory(snapshot.inventory);
    renderConvexity(snapshot);
    renderWorkingOrders(snapshot);
    renderActivityFeed(snapshot);
    renderRiskFeed(snapshot.risk_events);
    renderPostmortems(snapshot.postmortems);
    renderPlans(snapshot.market_plans);
    renderFooter(snapshot);
  } catch (err) {
    console.error(err);
  }
}

setupScrollSpy();
refresh();
setInterval(refresh, 30_000);
