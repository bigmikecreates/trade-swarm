/* Trade-Swarm v0.1.0 Dashboard */

document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  loadConfig();
  loadExperiments();
  loadDiagramList();

  document.getElementById("bt-form").addEventListener("submit", runBacktest);
  document.getElementById("sig-form").addEventListener("submit", runSignal);
  document.getElementById("diagram-select").addEventListener("change", renderDiagram);

  mermaid.initialize({ startOnLoad: false, theme: "default" });
});

/* ---------- Tabs ---------- */

function initTabs() {
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
    });
  });
}

/* ---------- Dashboard: Config ---------- */

async function loadConfig() {
  try {
    const resp = await fetch("/api/config");
    const cfg = await resp.json();
    const el = document.getElementById("config-display");
    el.innerHTML = configHTML(cfg);

    const form = document.getElementById("bt-form");
    form.symbol.value = cfg.symbol;
    form.period.value = cfg.period;
    form.interval.value = cfg.interval;
    form.ema_fast.value = cfg.ema_fast;
    form.ema_slow.value = cfg.ema_slow;
    form.adx_threshold.value = cfg.adx_threshold;
    form.init_cash.value = cfg.init_cash;
    form.fee_rate.value = cfg.fee_rate;
  } catch (e) {
    document.getElementById("config-display").textContent = "Failed to load config.";
  }
}

function configHTML(cfg) {
  const lines = [
    ["Symbol", cfg.symbol],
    ["Period", cfg.period],
    ["Interval", cfg.interval],
    ["EMA", `${cfg.ema_fast} / ${cfg.ema_slow}`],
    ["ADX Filter", cfg.adx_threshold > 0 ? `ADX > ${cfg.adx_threshold}` : "Disabled"],
    ["Init Cash", `$${Number(cfg.init_cash).toLocaleString()}`],
    ["Fee Rate", `${(cfg.fee_rate * 100).toFixed(1)}%`],
  ];
  return lines.map(([l, v]) =>
    `<div class="config-line"><span class="label">${l}</span><span class="value">${v}</span></div>`
  ).join("");
}

/* ---------- Backtest ---------- */

let equityChart = null;
let priceChart = null;

async function runBacktest(e) {
  e.preventDefault();
  const btn = document.getElementById("bt-run-btn");
  const status = document.getElementById("bt-status");
  btn.disabled = true;
  status.textContent = "Running backtest...";

  const form = document.getElementById("bt-form");
  const body = {
    symbol: form.symbol.value,
    period: form.period.value,
    interval: form.interval.value,
    ema_fast: parseInt(form.ema_fast.value),
    ema_slow: parseInt(form.ema_slow.value),
    adx_threshold: parseInt(form.adx_threshold.value),
    use_regime: form.use_regime.checked,
    init_cash: parseFloat(form.init_cash.value),
    fee_rate: parseFloat(form.fee_rate.value),
  };

  try {
    const resp = await fetch("/api/backtest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await resp.json();

    if (data.error) {
      status.textContent = "Error: " + data.error;
      btn.disabled = false;
      return;
    }

    status.textContent = "Done.";
    showBacktestResults(data);
    updateDashboard(data);
  } catch (err) {
    status.textContent = "Request failed: " + err.message;
  }
  btn.disabled = false;
}

function showBacktestResults(data) {
  document.getElementById("bt-results-card").style.display = "block";
  document.getElementById("bt-equity-card").style.display = "block";
  document.getElementById("bt-price-card").style.display = "block";

  document.getElementById("bt-metrics").innerHTML = metricsTableHTML(data.metrics);
  document.getElementById("bt-gate").innerHTML = gateHTML(data.gate);

  drawEquityChart(data.equity_curve);
  drawPriceChart(data.price_data, data.config);
}

function updateDashboard(data) {
  document.getElementById("dash-metrics").innerHTML = metricsTableHTML(data.metrics);
  document.getElementById("gate-display").innerHTML = gateHTML(data.gate);
}

function metricsTableHTML(m) {
  let rows = "";
  for (const [k, v] of Object.entries(m)) {
    const val = typeof v === "number" ? (Number.isInteger(v) ? v : v.toFixed(2)) : v;
    rows += `<tr><th>${k}</th><td>${val}</td></tr>`;
  }
  return `<table class="metrics-table">${rows}</table>`;
}

function gateHTML(g) {
  const row = (label, pass) =>
    `<div class="gate-row"><span class="gate-label">${label}</span><span class="${pass ? "pass" : "fail"}">${pass ? "PASS" : "FAIL"}</span></div>`;

  const t = g.thresholds;
  let html = "";
  html += row(`Sharpe >= ${t.min_sharpe}`, g.sharpe_pass);
  html += row(`Max DD <= ${t.max_drawdown_pct}%`, g.drawdown_pass);
  html += row(`Trades >= ${t.min_trades}`, g.trades_pass);
  html += `<div class="gate-overall ${g.gate_pass ? "pass" : "fail"}">${g.gate_pass ? "GATE PASSED" : "GATE FAILED"}</div>`;
  return html;
}

/* ---------- Charts ---------- */

const CHART_COLORS = {
  equity: "rgba(88, 166, 255, 1)",
  equityFill: "rgba(88, 166, 255, 0.08)",
  price: "rgba(201, 209, 217, 0.8)",
  emaFast: "rgba(63, 185, 80, 0.9)",
  emaSlow: "rgba(210, 153, 34, 0.9)",
  entryMarker: "rgba(63, 185, 80, 1)",
  exitMarker: "rgba(248, 81, 73, 1)",
};

function downsample(labels, datasets, maxPoints) {
  if (labels.length <= maxPoints) return { labels, datasets };
  const step = Math.ceil(labels.length / maxPoints);
  const newLabels = [];
  const newDatasets = datasets.map(ds => ({ ...ds, data: [] }));
  for (let i = 0; i < labels.length; i += step) {
    newLabels.push(labels[i]);
    newDatasets.forEach((ds, idx) => ds.data.push(datasets[idx].data[i]));
  }
  return { labels: newLabels, datasets: newDatasets };
}

function shortTimestamp(ts) {
  return ts.replace(/:\d{2}\+.*$/, "").replace("T", " ").substring(0, 16);
}

function drawEquityChart(eq) {
  const ctx = document.getElementById("equity-chart").getContext("2d");
  if (equityChart) equityChart.destroy();

  const labels = eq.timestamps.map(shortTimestamp);
  const datasets = [{
    label: "Equity",
    data: eq.values,
    borderColor: CHART_COLORS.equity,
    backgroundColor: CHART_COLORS.equityFill,
    fill: true,
    pointRadius: 0,
    borderWidth: 1.5,
    tension: 0.1,
  }];

  const ds = downsample(labels, datasets, 600);

  equityChart = new Chart(ctx, {
    type: "line",
    data: { labels: ds.labels, datasets: ds.datasets },
    options: chartOptions("Equity ($)"),
  });
}

function drawPriceChart(pd, config) {
  const ctx = document.getElementById("price-chart").getContext("2d");
  if (priceChart) priceChart.destroy();

  const labels = pd.timestamps.map(shortTimestamp);

  const entryPoints = pd.close.map((v, i) => pd.entries[i] ? v : null);
  const exitPoints = pd.close.map((v, i) => pd.exits[i] ? v : null);

  const datasets = [
    {
      label: "Close",
      data: pd.close,
      borderColor: CHART_COLORS.price,
      pointRadius: 0,
      borderWidth: 1,
      tension: 0.1,
      order: 3,
    },
    {
      label: `EMA ${config.ema_fast}`,
      data: pd.ema_fast,
      borderColor: CHART_COLORS.emaFast,
      pointRadius: 0,
      borderWidth: 1.2,
      tension: 0.1,
      order: 2,
    },
    {
      label: `EMA ${config.ema_slow}`,
      data: pd.ema_slow,
      borderColor: CHART_COLORS.emaSlow,
      pointRadius: 0,
      borderWidth: 1.2,
      tension: 0.1,
      order: 1,
    },
    {
      label: "Entry",
      data: entryPoints,
      backgroundColor: CHART_COLORS.entryMarker,
      borderColor: CHART_COLORS.entryMarker,
      pointRadius: 3,
      pointStyle: "triangle",
      showLine: false,
      order: 0,
    },
    {
      label: "Exit",
      data: exitPoints,
      backgroundColor: CHART_COLORS.exitMarker,
      borderColor: CHART_COLORS.exitMarker,
      pointRadius: 3,
      pointStyle: "crossRot",
      showLine: false,
      order: 0,
    },
  ];

  const ds = downsample(labels, datasets, 600);

  priceChart = new Chart(ctx, {
    type: "line",
    data: { labels: ds.labels, datasets: ds.datasets },
    options: chartOptions("Price"),
  });
}

function chartOptions(yLabel) {
  return {
    responsive: true,
    maintainAspectRatio: true,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { labels: { color: "#8b949e", font: { size: 11 } } },
      tooltip: { backgroundColor: "#161b22", titleColor: "#c9d1d9", bodyColor: "#c9d1d9", borderColor: "#30363d", borderWidth: 1 },
    },
    scales: {
      x: {
        ticks: { color: "#8b949e", maxTicksLimit: 10, font: { size: 10 } },
        grid: { color: "rgba(48,54,61,0.4)" },
      },
      y: {
        title: { display: true, text: yLabel, color: "#8b949e" },
        ticks: { color: "#8b949e", font: { size: 10 } },
        grid: { color: "rgba(48,54,61,0.4)" },
      },
    },
  };
}

/* ---------- Signal ---------- */

async function runSignal(e) {
  e.preventDefault();
  const btn = document.getElementById("sig-run-btn");
  const status = document.getElementById("sig-status");
  btn.disabled = true;
  status.textContent = "Generating signal...";

  const form = document.getElementById("sig-form");
  const body = {
    symbol: form.symbol.value,
    period: form.period.value,
    interval: form.interval.value,
  };

  try {
    const resp = await fetch("/api/signal", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await resp.json();

    if (data.error) {
      status.textContent = "Error: " + data.error;
      btn.disabled = false;
      return;
    }

    status.textContent = "Done.";
    showSignalResult(data);
  } catch (err) {
    status.textContent = "Request failed: " + err.message;
  }
  btn.disabled = false;
}

function showSignalResult(sig) {
  document.getElementById("sig-result-card").style.display = "block";

  const badge = document.getElementById("sig-direction-badge");
  badge.className = "direction-badge " + sig.direction;
  badge.textContent = sig.direction.toUpperCase();

  const items = [
    ["Strength", sig.strength.toFixed(4)],
    ["Confidence", sig.confidence.toFixed(4)],
    ["Asset", sig.asset],
    ["EMA 20", sig.indicators.ema20.toFixed(5)],
    ["EMA 50", sig.indicators.ema50.toFixed(5)],
    ["ADX", sig.indicators.adx.toFixed(2)],
    ["RSI", sig.indicators.rsi.toFixed(2)],
    ["Timestamp", sig.timestamp.substring(0, 19)],
  ];

  document.getElementById("sig-details").innerHTML = items.map(([l, v]) =>
    `<div class="signal-item"><div class="sig-label">${l}</div><div class="sig-value">${v}</div></div>`
  ).join("");
}

/* ---------- Experiments ---------- */

async function loadExperiments() {
  try {
    const resp = await fetch("/api/experiments");
    const data = await resp.json();

    const versionLabel = document.getElementById("exp-version-label");
    if (versionLabel && data.version) {
      versionLabel.textContent = data.version;
    } else if (versionLabel) {
      versionLabel.textContent = "unknown";
    }

    if (!data.rows || data.rows.length === 0) {
      document.getElementById("exp-table-container").innerHTML =
        data.version
          ? `<p>No experiments recorded for ${data.version} yet.</p>`
          : "<p>No experiment log found for the current branch.</p>";
      return;
    }

    const headers = Object.keys(data.rows[0]);
    let html = '<div class="exp-table-wrapper"><table class="exp-table"><thead><tr>';
    headers.forEach(h => { html += `<th>${h}</th>`; });
    html += "</tr></thead><tbody>";
    data.rows.forEach(row => {
      html += "<tr>";
      headers.forEach(h => {
        let val = row[h] || "";
        if (val === "NO") val = `<span class="fail">NO</span>`;
        if (val === "YES") val = `<span class="pass">YES</span>`;
        html += `<td>${val}</td>`;
      });
      html += "</tr>";
    });
    html += "</tbody></table></div>";
    document.getElementById("exp-table-container").innerHTML = html;
  } catch (e) {
    document.getElementById("exp-table-container").textContent = "Failed to load experiments.";
  }
}

/* ---------- Diagrams ---------- */

async function loadDiagramList() {
  try {
    const resp = await fetch("/api/diagrams");
    const diagrams = await resp.json();
    const select = document.getElementById("diagram-select");

    const categories = {};
    diagrams.forEach(d => {
      if (!categories[d.category]) categories[d.category] = [];
      categories[d.category].push(d);
    });

    for (const [cat, items] of Object.entries(categories)) {
      const group = document.createElement("optgroup");
      group.label = cat.replace("_", " ").toUpperCase();
      items.forEach(d => {
        const opt = document.createElement("option");
        opt.value = d.path;
        opt.textContent = d.name;
        group.appendChild(opt);
      });
      select.appendChild(group);
    }
  } catch (e) {
    console.error("Failed to load diagrams:", e);
  }
}

let mermaidCounter = 0;

async function renderDiagram() {
  const select = document.getElementById("diagram-select");
  const container = document.getElementById("mermaid-container");
  const card = document.getElementById("diagram-render-card");

  if (!select.value) {
    card.style.display = "none";
    return;
  }

  card.style.display = "block";
  container.innerHTML = "Loading...";

  try {
    const resp = await fetch("/api/diagrams/" + select.value);
    const data = await resp.json();

    if (data.error) {
      container.textContent = "Error: " + data.error;
      return;
    }

    const mmdContent = data.content
      .replace(/^---[\s\S]*?---\s*\n/, "");

    mermaidCounter++;
    const id = "mermaid-diagram-" + mermaidCounter;
    const { svg } = await mermaid.render(id, mmdContent);
    container.innerHTML = svg;
  } catch (e) {
    container.textContent = "Failed to render diagram: " + e.message;
  }
}
