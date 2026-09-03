/*
 * Static dashboard. Reads data/dashboard.json -- a single JSON snapshot that
 * agent/dashboard_export.py regenerates from the SQLite ledger every cycle.
 * No backend, no Alpaca keys in the browser. Assumes this site is served
 * with the repo root as web root (GitHub Pages: Settings > Pages > Deploy
 * from branch > / (root)), so "../data/..." resolves to "<repo-root>/data/...".
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
  return new Date(iso).toLocaleString();
}

function pnlColor(n) {
  return n >= 0 ? "var(--green)" : "var(--red)";
}

let equityChart;

function renderStats(snapshot) {
  const history = snapshot.account_history;
  const last = history[history.length - 1];
  document.getElementById("stat-equity").textContent = last ? fmtMoney(last.equity) : "—";
  document.getElementById("stat-updated").textContent = fmtTime(snapshot.generated_at);

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

function renderEquityChart(history) {
  const ctx = document.getElementById("equity-chart");
  const labels = history.map((s) => fmtTime(s.ts));
  const values = history.map((s) => s.equity);

  if (equityChart) equityChart.destroy();
  equityChart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [{
        label: "Equity ($)",
        data: values,
        borderColor: "#4f8cff",
        backgroundColor: "rgba(79,140,255,0.12)",
        fill: true,
        tension: 0.25,
        pointRadius: 0,
      }],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: "#8b93a7", maxTicksLimit: 8 }, grid: { color: "#232733" } },
        y: { ticks: { color: "#8b93a7" }, grid: { color: "#232733" } },
      },
    },
  });
}

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
    { label: "Net delta $", value: totals.delta_dollars, cap: snapshot.risk_config.max_net_delta_dollars, fmt: fmtMoney },
    { label: "Net vega $", value: totals.vega_dollars, cap: snapshot.risk_config.max_net_vega_dollars, fmt: fmtMoney },
    { label: "Net gamma", value: totals.gamma, cap: snapshot.risk_config.max_net_gamma_shares_per_dollar, fmt: (n) => n.toFixed(1) },
  ];
  for (const g of gauges) {
    const pct = Math.min(100, Math.abs(g.value) / g.cap * 100);
    const div = document.createElement("div");
    div.className = "gauge";
    div.innerHTML = `
      <div class="gauge-label">${g.label}</div>
      <div class="gauge-bar"><div class="gauge-fill ${pct > 85 ? "danger" : ""}" style="width:${pct}%"></div></div>
      <div class="gauge-value">${g.fmt(g.value)} / ±${g.fmt(g.cap)}</div>
    `;
    row.appendChild(div);
  }
}

function renderInventory(inventory) {
  const tbody = document.querySelector("#inventory-table tbody");
  tbody.innerHTML = "";
  const rows = [...inventory].sort((a, b) => b.symbol.localeCompare(a.symbol));
  for (const p of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${p.symbol}</td>
      <td>${p.mode}</td>
      <td>${p.qty}</td>
      <td>${fmtMoney(p.delta_dollars)}</td>
      <td>${(p.gamma ?? 0).toFixed(2)}</td>
      <td>${fmtMoney(p.vega_dollars)}</td>
      <td>${fmtMoney(p.theta_dollars)}</td>
    `;
    tbody.appendChild(tr);
  }
  if (rows.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="color:var(--muted)">Flat — no open inventory</td></tr>`;
  }
}

function renderActivityFeed(snapshot) {
  const events = [
    ...snapshot.quote_feed.map((o) => ({
      ts: o.ts, kind: o.status === "cancelled" ? "cancelled" : o.status === "rejected" ? "rejected" : "placed",
      text: `${o.mode} ${o.side} ${o.qty} ${o.symbol} @ ${o.limit_price ?? "mkt"} [${o.status}]${o.note ? " — " + o.note : ""}`,
    })),
    ...snapshot.fills.map((f) => ({
      ts: f.ts, kind: "filled",
      text: `FILL ${f.mode} ${f.side} ${f.qty} ${f.symbol} @ ${fmtMoney(f.fill_price)}`,
    })),
    ...snapshot.hedges.map((h) => ({
      ts: h.ts, kind: "hedge",
      text: `HEDGE ${h.side} ${h.qty} ${h.underlying} @ ${fmtMoney(h.price)} (delta ${h.delta_before?.toFixed(0)}→${h.delta_after?.toFixed(0)})`,
    })),
  ].sort((a, b) => new Date(b.ts) - new Date(a.ts)).slice(0, 150);

  const feed = document.getElementById("activity-feed");
  feed.innerHTML = "";
  for (const e of events) {
    const div = document.createElement("div");
    div.className = "feed-entry";
    div.innerHTML = `<div class="ts">${fmtTime(e.ts)}</div><span class="badge badge-${e.kind}">${e.kind}</span><span>${e.text}</span>`;
    feed.appendChild(div);
  }
  if (events.length === 0) feed.innerHTML = `<div class="feed-entry" style="color:var(--muted)">No activity yet</div>`;
}

// NOTE ON UNITS: ledger stores entry_credit per-share (e.g. 1.42) but
// max_loss_estimate already x100 (e.g. 358). Scale the credit by the 100x
// contract multiplier so both columns are total dollars per contract --
// otherwise the table reads "$1 credit vs $358 max loss" instead of the
// real ~1:2.5 risk/reward.
function renderConvexity(snapshot) {
  const tbody = document.querySelector("#convexity-table tbody");
  tbody.innerHTML = "";
  const all = [...snapshot.convexity_open, ...snapshot.convexity_closed];
  for (const c of all) {
    const tr = document.createElement("tr");
    const rightCol = c.status === "closed" ? fmtSigned(c.exit_pnl) : fmtMoney(c.max_loss_estimate);
    tr.innerHTML = `
      <td>${c.underlying}</td>
      <td>${c.strategy_type}</td>
      <td>${c.status}</td>
      <td>${fmtMoney((c.entry_credit ?? 0) * 100)}</td>
      <td style="color:${c.status === "closed" ? pnlColor(c.exit_pnl ?? 0) : "inherit"}">${rightCol}</td>
    `;
    tbody.appendChild(tr);
  }
  if (all.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" style="color:var(--muted)">No convexity positions yet</td></tr>`;
  }
}

function renderRiskFeed(events) {
  const feed = document.getElementById("risk-feed");
  feed.innerHTML = "";
  for (const e of events) {
    const div = document.createElement("div");
    div.className = "feed-entry";
    div.innerHTML = `<div class="ts">${fmtTime(e.ts)}</div><span class="badge badge-${e.event_type}">${e.event_type}</span><span>${e.reason}</span>`;
    feed.appendChild(div);
  }
  if (events.length === 0) feed.innerHTML = `<div class="feed-entry" style="color:var(--muted)">No rejections or clamps yet — risk gate hasn't had to intervene</div>`;
}

function renderPostmortems(postmortems) {
  const feed = document.getElementById("postmortem-feed");
  feed.innerHTML = "";
  for (const p of postmortems) {
    const div = document.createElement("div");
    div.className = "feed-entry postmortem-entry";
    div.innerHTML = `<div class="ts">${p.trade_date}</div><div class="postmortem-text">${p.text.replace(/\n/g, "<br>")}</div>`;
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
      <div class="ts">${fmtTime(p.ts)}</div>
      <span class="badge badge-${p.source}">${p.source}</span>
      <span>${approved.symbols.join(", ")} — specialist/convexity weight ${approved.mode_weights.specialist.toFixed(2)}/${approved.mode_weights.convexity.toFixed(2)}${p.was_clamped ? " (clamped)" : ""}</span>
    `;
    feed.appendChild(div);
  }
  if (plans.length === 0) feed.innerHTML = `<div class="feed-entry" style="color:var(--muted)">No MarketPlans generated yet</div>`;
}

async function refresh() {
  try {
    const snapshot = await fetchSnapshot();
    renderStats(snapshot);
    if (snapshot.account_history.length) renderEquityChart(snapshot.account_history);
    renderGauges(snapshot);
    renderInventory(snapshot.inventory);
    renderActivityFeed(snapshot);
    renderConvexity(snapshot);
    renderRiskFeed(snapshot.risk_events);
    renderPostmortems(snapshot.postmortems);
    renderPlans(snapshot.market_plans);
  } catch (err) {
    console.error(err);
  }
}

refresh();
setInterval(refresh, 30_000);
