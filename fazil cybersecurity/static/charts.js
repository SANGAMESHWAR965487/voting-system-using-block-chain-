/**
 * charts.js
 * ---------
 * All chart rendering for the analytics dashboard.
 * Expects window.ANALYTICS to be set by visualize.html before this script runs.
 */

const PALETTE = ["#378ADD", "#1D9E75", "#D85A30", "#7F77DD", "#BA7517", "#888780"];
let activePos  = null;
let barInst    = null;

// ── Helpers ──────────────────────────────────────────────────────────────────

function $(id) { return document.getElementById(id); }

function makeLegend(labels, colors) {
    return labels.map((l, i) =>
        `<span class="legend-item">
            <span class="legend-dot" style="background:${colors[i]}"></span>${l}
         </span>`
    ).join("");
}

// ── Tabs ─────────────────────────────────────────────────────────────────────

function buildTabs() {
    const row = $("pos-tabs");
    if (!row) return;
    row.innerHTML = "";
    Object.keys(window.ANALYTICS.vote_data).forEach(pos => {
        const b = document.createElement("button");
        b.className = "tab-btn" + (pos === activePos ? " active" : "");
        b.textContent = pos;
        b.onclick = () => { activePos = pos; buildTabs(); renderBar(); };
        row.appendChild(b);
    });
}

// ── Bar chart ─────────────────────────────────────────────────────────────────

function renderBar() {
    const titleEl = $("bar-title");
    const legEl   = $("bar-legend");
    const canvas  = $("barChart");
    if (!canvas) return;

    if (titleEl) titleEl.textContent = activePos + " — vote split";

    const cands  = window.ANALYTICS.vote_data[activePos] || [];
    const labels = cands.map(c => c.name);
    const vals   = cands.map(c => c.votes);
    const colors = PALETTE.slice(0, cands.length);

    if (legEl) legEl.innerHTML = makeLegend(
        labels.map((l, i) => `${l} (${vals[i]})`), colors
    );

    if (barInst) { barInst.destroy(); barInst = null; }

    barInst = new Chart(canvas, {
        type: "bar",
        data: {
            labels,
            datasets: [{
                data: vals,
                backgroundColor: colors,
                borderRadius: 6,
                borderSkipped: false
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { display: false }, ticks: { color: "#8888aa" } },
                y: {
                    beginAtZero: true,
                    grid: { color: "rgba(255,255,255,.07)" },
                    ticks: { color: "#8888aa", stepSize: 1,
                             precision: 0 }
                }
            }
        }
    });
}

// ── Line chart ────────────────────────────────────────────────────────────────

function renderLine() {
    const canvas = $("lineChart");
    if (!canvas) return;
    const { labels, counts } = window.ANALYTICS.hourly_data;
    new Chart(canvas, {
        type: "line",
        data: {
            labels,
            datasets: [{
                data: counts,
                borderColor: "#378ADD",
                backgroundColor: "rgba(55,138,221,.15)",
                fill: true,
                tension: 0.4,
                pointRadius: 3,
                pointBackgroundColor: "#378ADD"
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { display: false }, ticks: { color: "#8888aa", maxRotation: 0 } },
                y: { grid: { color: "rgba(255,255,255,.07)" }, ticks: { color: "#8888aa" } }
            }
        }
    });
}

// ── Doughnut chart ────────────────────────────────────────────────────────────

function renderDept() {
    const canvas = $("deptChart");
    if (!canvas) return;
    const { labels, counts } = window.ANALYTICS.dept_data;
    new Chart(canvas, {
        type: "doughnut",
        data: {
            labels,
            datasets: [{
                data: counts,
                backgroundColor: PALETTE,
                borderWidth: 0,
                hoverOffset: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: "62%",
            plugins: {
                legend: {
                    position: "right",
                    labels: { color: "#8888aa", font: { size: 11 }, boxWidth: 10, padding: 8 }
                }
            }
        }
    });
}

// ── ML Predictions ────────────────────────────────────────────────────────────

function renderPredictions() {
    const el = $("predictions");
    if (!el) return;
    let html = '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px;">';

    Object.entries(window.ANALYTICS.predictions).forEach(([pos, cands]) => {
        html += `<div class="card"><p class="card-title">${pos}</p>`;
        cands.forEach((c, i) => {
            const pct = c.probability;
            html += `
                <div class="pred-wrap">
                    <div class="pred-head">
                        <span class="pred-name">${c.name}
                            ${c.predicted_winner ? '<span class="winner-tag">leading</span>' : ''}
                        </span>
                        <span class="pred-info">${c.votes} votes</span>
                    </div>
                    <div class="bar-track">
                        <div class="bar-fill" style="width:${pct}%;background:${PALETTE[i % PALETTE.length]};"></div>
                    </div>
                    <div class="pred-pct">${pct}%</div>
                </div>`;
        });
        html += "</div>";
    });

    html += "</div>";
    el.innerHTML = html;
}

// ── Insights ──────────────────────────────────────────────────────────────────

function renderInsights() {
    const el = $("insights");
    if (!el) return;
    const iconMap = { info: "ℹ", warn: "⚠", ok: "✓", alert: "✗" };
    el.innerHTML = window.ANALYTICS.insights.map(ins =>
        `<div class="insight ${ins.type}">
            <span class="insight-icon">${iconMap[ins.type] || "•"}</span>
            <span class="insight-text">${ins.text}</span>
        </div>`
    ).join("");
}

// ── Init ──────────────────────────────────────────────────────────────────────

function initDashboard() {
    if (!window.ANALYTICS) {
        console.error("window.ANALYTICS not set — check visualize.html");
        return;
    }
    activePos = Object.keys(window.ANALYTICS.vote_data)[0] || "President";
    buildTabs();
    renderBar();
    renderLine();
    renderDept();
    renderPredictions();
    renderInsights();
}

// Run after DOM + Chart.js are ready
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initDashboard);
} else {
    initDashboard();
}