import { esc, lineChart, frontierChart, stackedBars, driftChart, rangeChart, barChart, reliabilityChart, miniFan, histogramChart, qqChart, bindTooltips } from "./charts.js?v=8";

const app = document.getElementById("app");
let D = null;

// ---------- formatting ----------
const pct = (v, d = 0) => (v == null ? "—" : (v * 100).toFixed(d) + "%");
const pts = (v, d = 1) => (v * 100).toFixed(d);
const money = (v) => (v == null ? "—" : (v < 0 ? "-$" : "$") + Math.abs(Math.round(v)).toLocaleString("en-CA"));
const compact = (v) => {
  const a = Math.abs(v);
  if (a >= 1e6) return "$" + (v / 1e6).toFixed(a >= 1e7 ? 0 : 1) + "M";
  if (a >= 1e3) return "$" + Math.round(v / 1e3) + "K";
  return "$" + Math.round(v);
};
const num = (v) => Number(v).toLocaleString("en-CA");
const status = (s) => `<span class="st ${s.toLowerCase()}">${esc(s.charAt(0) + s.slice(1).toLowerCase())}</span>`;
const GROUP_COLOR = { Equity: "var(--s1)", "Real assets": "var(--s2)", "Fixed income": "var(--s3)", Cash: "var(--s4)" };
const GROUP_TEXT = { Equity: "#fff", "Real assets": "#fff", "Fixed income": "#fff", Cash: "#0b0b0b" };
const GROUP_ORDER = ["Equity", "Real assets", "Fixed income", "Cash"];
const nameOf = (code) => D.assumptions.asset_classes.find((a) => a.code === code).name;
const profileName = (id) => D.model_portfolios.find((p) => p.id === id).name;
const hh = (id) => D.households.find((h) => h.profile.id === id);
const riskOf = (id) => (D.risk_metrics || []).find((r) => r.id === id);

function pageHead(eyebrow, title, text) {
  return `<div class="page-head"><div class="wrap"><div class="eyebrow">${esc(eyebrow)}</div><h2>${esc(title)}</h2>${text ? `<p>${text}</p>` : ""}</div></div>`;
}
function inShort(items) {
  return `<div class="inshort"><h3>In short</h3><ul>${items.map(([big, text]) => `<li><span class="big">${big}</span>${text}</li>`).join("")}</ul></div>`;
}
function tile(label, value, delta) {
  return `<div class="tile"><div class="label">${esc(label)}</div><div class="value">${value}</div>${delta ? `<div class="delta">${delta}</div>` : ""}</div>`;
}
function table(head, rows, opts = {}) {
  const th = head.map((h) => `<th class="${h.r ? "r" : ""}">${esc(h.t ?? h)}</th>`).join("");
  return `<div class="table-wrap"><table${opts.cls ? ` class="${opts.cls}"` : ""}><thead><tr>${th}</tr></thead><tbody>${rows.join("")}</tbody></table></div>`;
}
const tr = (cells, cls = "") => `<tr class="${cls}">${cells.map((c) => (typeof c === "object" && c !== null ? `<td class="${c.r ? "r num" : ""}">${c.v}</td>` : `<td>${c}</td>`)).join("")}</tr>`;
const R = (v) => ({ v, r: true });

function orderCounts() {
  let total = 0, blocked = 0, review = 0;
  for (const r of D.rebalances) for (const o of r.result.orders) { total++; if (o.status === "BLOCK") blocked++; if (o.status === "REVIEW") review++; }
  return { total, blocked, review };
}

// ---------- overview ----------
function overview() {
  const m = D.meta;
  const daniel = hh("H3");
  const scores = D.households.map((h) => h.health.score);
  const lo = D.households.find((h) => h.health.score === Math.min(...scores));
  const hi = D.households.find((h) => h.health.score === Math.max(...scores));
  const bal = D.model_portfolios.find((p) => p.id === "balanced");
  const balRisk = riskOf("balanced");
  const oc = orderCounts();
  const model = D.validation.calibration.worlds.find((w) => w.id === "model");
  const sim = D.api.latency.find((l) => l.label.startsWith("Monte Carlo"));
  const cards = [
    ["1 · Client plans", "Will this client&#8217;s money last?", `Simulates ${num(m.paths_per_plan)} possible markets for each household and counts how often the savings last to age 95.`,
      `<b>${pct(daniel.plan.probability_of_success)}</b> chance Daniel&#8217;s plan lasts to 95`, "#/clients?h=H3"],
    ["2 · Financial health", "How healthy are the finances?", "Scores each household from 0 to 100 on six clear rules and ranks the next steps that would raise the score most.",
      `<b>${Math.round(lo.health.score)} to ${Math.round(hi.health.score)}</b> range of scores across six households`, "#/clients?h=H5"],
    ["3 · Portfolios", "Which mix fits each risk level?", "Builds five model portfolios on an efficient frontier and reports the standard risk metrics an investment team expects.",
      `<b>${pct(bal.volatility, 1)}</b> volatility, ${pct(balRisk.var95_1y, 1)} one-year VaR (Balanced)`, "#/portfolios"],
    ["4 · Trading", "Which orders keep accounts on target, safely?", "Turns drift and deposits into whole-unit orders, then runs six pre-trade checks before anything could reach a desk.",
      `<b>${oc.total}</b> orders generated, ${oc.blocked} held back by checks`, "#/trading?a=A5"],
    ["5 · Validation", "Can we trust the probabilities?", "Tests whether predicted probabilities match outcomes, how they converge, and how they move under stress.",
      `<b>${model.brier.toFixed(3)}</b> Brier score vs ${model.brier_if_calibrated.toFixed(3)} if perfectly calibrated`, "#/validation"],
    ["6 · API", "How would other systems use it?", "Exposes every model through a validated REST API, so the platform calls one tested implementation.",
      `<b>${sim.p50_ms.toFixed(0)} ms</b> median for a 5,000-path plan`, "#/api"],
  ];
  const map = [
    ["Portfolio optimization", "Efficient frontier, five model portfolios, risk parity, stability tests", "#/portfolios", "Portfolios"],
    ["Monte Carlo simulations", `${num(m.paths_per_plan)} paths per household, wealth ranges by age, what-if grid`, "#/clients", "Client plans"],
    ["Financial health scores", "0&#8211;100 score, six components, ranked next steps", "#/clients", "Client plans"],
    ["Probability assessment models", "Convergence, calibration (Brier score), stress tests", "#/validation", "Validation"],
    ["Trading algorithms", "Tolerance-band rebalancing, whole-unit orders, six pre-trade checks", "#/trading", "Trading"],
    ["Back tests", `Four rebalancing policies on ${D.backtest.n_histories} simulated 25-year histories`, "#/trading", "Trading"],
    ["API services", "Flask REST API, JSON Schema validation, standard error format", "#/api", "API"],
    ["Data from various sources", "Data-quality checks before any model runs", "#/validation", "Validation"],
    ["Best practices", `${D.tests.passed} automated tests, fixed seeds, model inventory`, "#/validation", "Validation"],
  ];
  const chipRow = (label, items) => `<div style="margin-bottom:14px"><div class="small muted" style="margin-bottom:6px">${esc(label)}</div><div class="chips">${items.map((i) => `<span class="chip">${i}</span>`).join("")}</div></div>`;
  return `
  <section class="hero"><div class="wrap">
    <div>
      <span class="pill">Preliminary version · mock data</span>
      <h1>A working prototype of the <em>quantitative engine</em> behind a digital wealth platform</h1>
      <p class="lede">I built it to show, rather than tell, how I would do the Senior Software Quantitative Engineer job at RBC. It plans clients&#8217; goals, builds and rebalances their portfolios, scores their financial health and tests its own numbers, all behind a tested Python API.</p>
      <div class="actions"><a class="btn primary" href="#/clients?h=H3">See a client plan</a><a class="btn ghost" href="#/" data-scroll="tour">Take the 2-minute tour</a></div>
    </div>
    <div class="stack" style="gap:16px">
    <div class="glance">
      <h3>At a glance</h3>
      <dl>
        <dt>What</dt><dd>Python engine, REST API and this site</dd>
        <dt>For</dt><dd>RBC · Senior Software Quantitative Engineer (R-0000186840)</dd>
        <dt>Data</dt><dd>Mock: six fictional households and accounts</dd>
        <dt>Proof</dt><dd>${D.tests.passed} automated tests passing; probabilities checked for calibration</dd>
        <dt>Built by</dt><dd>Tiago Costa, Waterloo, ON · <a href="https://www.linkedin.com/in/tiagonbc">LinkedIn</a></dd>
      </dl>
    </div>
    <a class="preview" href="#/clients?h=H3" aria-label="Open Daniel's plan">
      <div class="preview-head"><span>Live from the engine</span><b>Daniel&#8217;s plan: ${pct(daniel.plan.probability_of_success)} chance it lasts to 95</b></div>
      ${miniFan({ title: "Daniel's projected wealth", x: daniel.plan.ages, lo: daniel.plan.percentiles["5"], hi: daniel.plan.percentiles["95"], lo2: daniel.plan.percentiles["25"], hi2: daniel.plan.percentiles["75"], mid: daniel.plan.percentiles["50"], marker: daniel.profile.retirement_age })}
      <div class="preview-foot"><span>Age ${daniel.profile.age}</span><span>Retires at ${daniel.profile.retirement_age}</span><span>Age ${daniel.profile.plan_to_age}</span></div>
    </a>
    </div>
  </div></section>
  <main><div class="wrap">
    <section class="block">
      <h2 class="section-title">What it does, in six questions</h2>
      <div class="cards5">${cards.map(([n, q, d, res, href]) => `<a class="qcard" href="${href}"><span class="n">${n}</span><h3>${q}</h3><p>${d}</p><div class="result">${res}</div><span class="go">Open &#8594;</span></a>`).join("")}</div>
    </section>
    <section class="block" id="tour">
      <h2 class="section-title">Two-minute tour</h2>
      <ol class="tour">
        <li><b><a href="#/clients?h=H3">Client plans → Daniel</a></b>The chance his money lasts, the range of outcomes by age, and what saving more or retiring later would change.</li>
        <li><b><a href="#/trading?a=A5">Trading → Priya&#8217;s TFSA</a></b>A client restriction and a stale price: watch the pre-trade checks hold the risky orders back.</li>
        <li><b><a href="#/validation">Validation → calibration</a></b>Do plans called 70% likely succeed about 70% of the time? And what happens when the assumptions are wrong?</li>
        <li><b><a href="#/phase-in">Phase-in plan</a></b>How I would get up to speed with the team, the platform and RBC&#8217;s way of working in year one.</li>
      </ol>
    </section>
    <section class="block grid2">
      <div class="panel"><h3>Mapped to the job posting</h3><p class="sub">Each line of the role description has working code behind it.</p>
        ${table(["Posting asks for", "Built here", ""], map.map(([a, b, href, label]) => tr([a, b, `<a href="${href}">${label}</a>`])), { cls: "map" })}</div>
      <div class="panel"><h3>Toolkit and standards</h3><p class="sub">Industry-standard tools, methods and metrics, so a reviewer recognizes every piece.</p>
        ${chipRow("Languages and libraries", ["Python " + esc(m.python), "NumPy", "SciPy (SLSQP)", "Flask", "JSON Schema", "pytest", "Docker"])}
        ${chipRow("Methods", ["Mean-variance optimization", "Monte Carlo simulation", "Risk parity", "Michaud resampling", "Tolerance-band rebalancing", "Calibration testing"])}
        ${chipRow("Metrics", ["Probability of success", "Sharpe", "Sortino", "VaR / CVaR 95%", "Max drawdown", "Calmar", "Tracking error", "Turnover", "Brier score"])}
        ${chipRow("Standards", ["OpenAPI 3.1", "RFC 9457 errors", "OSFI Guideline E-23 inventory fields"])}
        <p class="note" style="margin-top:4px">Clients, accounts and market assumptions are mock; only the SPY statistics use real market data. Nothing here is advice. Built with an AI coding agent working under tests; the design, checks and review are mine.</p>
      </div>
    </section>
  </div></main>`;
}

// ---------- client plans ----------
function clients(q) {
  const H = hh(q.get("h") || "H3") || D.households[0];
  const p = H.profile, plan = H.plan, hs = H.health;
  const tabs = D.households.map((h) => `<button class="tab" aria-pressed="${h.profile.id === p.id}" data-h="${h.profile.id}">${esc(h.profile.name)}<small>${esc(h.profile.summary)}</small></button>`).join("");
  const facts = [
    ["Age", p.retired ? `${p.age} (retired at ${p.retirement_age})` : `${p.age}, retiring at ${p.retirement_age}`],
    ["Gross income", money(p.gross_income)],
    ["Investable assets", `${money(H.investable_total)} <span class="muted small">(${Object.entries(p.investable).map(([k, v]) => `${k} ${compact(v)}`).join(", ")})</span>`],
    [p.retired ? "Contributions" : "Monthly saving", p.retired ? "none" : money(p.monthly_contribution)],
    ["Retirement spending", `${money(p.retirement_spending)} a year, today&#8217;s dollars`],
    ["Pensions and benefits", `${money(p.retirement_other_income)} a year`],
    ["Model portfolio", profileName(p.risk_profile)],
  ];
  const meters = hs.components.map((c) => `
    <div class="meter-row" data-tip="${esc(`<b>${c.name}</b><br>${c.rule}`)}">
      <div><div class="name">${esc(c.name)}</div><div class="disp">${esc(c.display)}</div></div>
      <div class="meter" aria-hidden="true"><i style="width:${(c.points / c.max) * 100}%"></i></div>
      <div class="pts">${c.points.toFixed(1)} / ${c.max}</div>
    </div>`).join("");
  const actions = hs.next_best_actions.length
    ? `<ol class="actions">${hs.next_best_actions.map((a) => `<li>${esc(a.action)} <span class="muted small">(${esc(a.component)}, up to +${a.points.toFixed(1)} pts)</span></li>`).join("")}</ol>`
    : `<p class="muted">No action needed: every component is at full points.</p>`;
  const top = hs.next_best_actions[0];
  const P = plan.percentiles;
  const fan = lineChart({
    title: "Projected wealth by age", x: plan.ages, height: 320,
    bands: [
      { name: "5th to 95th percentile", lo: P["5"], hi: P["95"], color: "var(--seq-3)", opacity: 0.16 },
      { name: "25th to 75th percentile", lo: P["25"], hi: P["75"], color: "var(--seq-4)", opacity: 0.26 },
    ],
    series: [{ name: "Median", values: P["50"], color: "var(--s1)" }],
    markers: p.retired ? [] : [{ x: p.retirement_age, label: "Retirement" }],
    yMin: 0, yFmt: compact, xFmt: String, xTipFmt: (a) => "Age " + a, tipFmt: money, xLabel: "Age", yLabel: "Wealth, today's dollars",
  });
  const g = H.what_if;
  const base = p.retired ? { r: 2, c: g.cols.indexOf(profileName(p.risk_profile)) } : { r: 0, c: 1 };
  const heat = `<div class="table-wrap"><table class="heat"><thead><tr><th>${esc(g.row_label)} \\ ${esc(g.col_label)}</th>${g.cols.map((c) => `<th class="r">${esc(c)}</th>`).join("")}</tr></thead><tbody>
    ${g.rows.map((rl, i) => `<tr><td>${esc(rl)}</td>${g.cells[i].map((v, j) => `<td class="cell ${i === base.r && j === base.c ? "base" : ""}" style="background:color-mix(in srgb, var(--s1) ${Math.round(v * 85)}%, #ffffff);color:${v > 0.55 ? "#fff" : "var(--ink)"}" data-tip="${esc(`<b>${rl}, ${g.col_label.toLowerCase()} ${g.cols[j]}</b><br>Probability of success: ${pct(v)}`)}">${pct(v)}</td>`).join("")}</tr>`).join("")}
  </tbody></table></div>
  <p class="note">The outlined cell is the current plan. Every cell uses the same ${num(plan.n_paths)} simulated markets, so differences come from the choices, not from chance.</p>`;

  return `${pageHead("Monte Carlo planning · financial health", "Client plans", "Six fictional households. For each one the engine answers two questions: will the money last, and how healthy are the finances today? Pick a household.")}
  <main><div class="wrap">
    <div class="tabs" role="group" aria-label="Household">${tabs}</div>
    ${inShort([
      [pct(plan.probability_of_success), `chance ${esc(p.name)}&#8217;s money lasts to age ${p.plan_to_age}, across ${num(plan.n_paths)} simulated markets`],
      [`${Math.round(hs.score)}<span class="muted" style="font-size:16px"> / 100</span>`, `financial health score: <b>${esc(hs.band)}</b>`],
      top ? [`+${top.points.toFixed(0)} pts`, `available from the best next step, on ${esc(top.component.toLowerCase())}: ${esc(top.action.charAt(0).toLowerCase() + top.action.slice(1))}`] : ["None", "no action needed: every component is at full points"],
    ])}
    <div class="grid-side">
      <div class="stack">
        <div class="panel"><h3>${esc(p.name)}</h3><p class="sub">${esc(p.summary)}</p>
          <div class="table-wrap"><table>${facts.map(([k, v]) => `<tr><td class="muted">${k}</td><td>${v}</td></tr>`).join("")}</table></div>
        </div>
        <div class="panel">
          <h3>Financial health</h3>
          <div style="display:flex;align-items:baseline;gap:12px;margin:10px 0 6px"><span class="hero-figure">${Math.round(hs.score)}</span><span><b>${esc(hs.band)}</b><br><span class="muted small">out of 100</span></span></div>
          ${meters}
          <h4 style="margin-top:16px">Next best actions</h4>
          ${actions}
        </div>
      </div>
      <div class="stack">
        <div class="tiles">
          ${tile("Probability of success", pct(plan.probability_of_success), `±${pts(plan.standard_error)} pts standard error`)}
          ${tile(p.retired ? "Median wealth today" : "Median wealth at retirement", compact(plan.median_at_retirement), "today&#8217;s dollars")}
          ${tile("Median wealth at " + p.plan_to_age, compact(plan.median_at_end), `10th percentile ${compact(plan.p10_at_end)}`)}
          ${tile("Spending at 90% success", money(plan.spending_at_90), `plan asks for ${money(p.retirement_spending)}`)}
        </div>
        <div class="panel"><h3>Projected wealth</h3><p class="sub">The darker band holds the middle half of outcomes; the lighter band, 90% of them. Today&#8217;s dollars, after a ${pct(D.assumptions.fee, 2)} fee and ${pct(D.assumptions.inflation, 1)} inflation.${plan.median_depletion_age ? ` When the money does run out, it is at a median age of ${Math.round(plan.median_depletion_age)}.` : ""}</p>${fan}</div>
        <div class="panel"><h3>What if?</h3><p class="sub">Probability of success as two choices change.</p>${heat}</div>
      </div>
    </div>
    <p class="note">Method: correlated returns for nine asset classes, rebalanced yearly; contributions at the start of each working year, withdrawals (spending minus pensions and benefits) at the start of each retired year; no taxes. API: <code class="inline">POST /api/v1/plans/simulate</code>, <code class="inline">POST /api/v1/health-score</code>.</p>
  </div></main>`;
}

// ---------- portfolios ----------
function portfolios() {
  const mps = D.model_portfolios;
  const ac = D.assumptions.asset_classes;
  const labelPos = { conservative: { dx: -10, dy: 18, anchor: "end" }, moderately_conservative: { dx: 10, dy: 16, anchor: "start" },
    balanced: { dx: -10, dy: -10 }, growth: { dx: -10, dy: -10 }, aggressive_growth: { dx: -10, dy: -12 } };
  const fr = frontierChart({
    frontier: D.frontier,
    points: [
      ...mps.map((p) => ({ x: p.volatility, y: p.expected_return, color: "var(--s1)", label: p.name, ...labelPos[p.id],
        tip: `<b>${p.name}</b><br>Expected return ${pct(p.expected_return, 2)}<br>Volatility ${pct(p.volatility, 1)}<br>Sharpe ${p.sharpe.toFixed(2)}` })),
      { x: D.risk_parity.volatility, y: D.risk_parity.expected_return, color: "var(--s2)", label: "Risk parity", dx: 10, dy: 4, anchor: "start",
        tip: `<b>Risk parity</b> (risky assets, no constraints)<br>Expected return ${pct(D.risk_parity.expected_return, 2)}<br>Volatility ${pct(D.risk_parity.volatility, 1)}` },
    ],
    assets: ac.map((a) => ({ x: a.volatility, y: a.expected_return, label: a.code, ...({ INTL: { dx: -8, dy: 16, anchor: "end" } }[a.code] || {}), tip: `<b>${a.name}</b><br>Expected return ${pct(a.expected_return, 1)}<br>Volatility ${pct(a.volatility, 1)}` })),
  });
  const groups = (w) => GROUP_ORDER.map((gname) => ({ name: gname, color: GROUP_COLOR[gname], textColor: GROUP_TEXT[gname],
    value: ac.filter((a) => a.group === gname).reduce((s, a) => s + (w[a.code] || 0), 0) }));
  const stack = stackedBars({
    w: 560, padL: 150, title: "Allocation by asset group",
    rows: [...mps.map((p) => ({ label: p.name, parts: groups(p.weights) })), { label: "Risk parity", parts: groups(D.risk_parity.weights) }],
    legend: GROUP_ORDER.map((gname) => ({ name: gname, color: GROUP_COLOR[gname], kind: "box" })),
  });
  const wTable = table(["Asset class", { t: "Bounds", r: true }, ...mps.map((p) => ({ t: p.name, r: true }))],
    ac.map((a) => tr([esc(a.name), R(`${pct(a.bounds[0])}–${pct(a.bounds[1])}`), ...mps.map((p) => R(p.weights[a.code] > 0.0005 ? pct(p.weights[a.code], 1) : "–"))])));
  const riskT = table(["Model portfolio", { t: "Return a year", r: true }, { t: "Volatility", r: true }, { t: "Sharpe", r: true }, { t: "Sortino", r: true },
    { t: "1-yr VaR 95%", r: true }, { t: "1-yr CVaR 95%", r: true }, { t: "Max drawdown", r: true }, { t: "Calmar", r: true }, { t: "Losing years", r: true }],
    mps.map((p) => { const r = riskOf(p.id); return tr([esc(p.name), R(pct(r.cagr, 1)), R(pct(r.volatility, 1)), R(r.sharpe.toFixed(2)), R(r.sortino.toFixed(2)),
      R(pct(r.var95_1y, 1)), R(pct(r.cvar95_1y, 1)), R(pct(r.max_drawdown, 1)), R(r.calmar.toFixed(2)), R(pct(r.prob_losing_year))], p.id === "balanced" ? "hl" : ""); }));
  const statsT = table(["Model portfolio", { t: "Volatility budget", r: true }, { t: "Expected return", r: true }, { t: "Equity", r: true },
    { t: "Below start after 1 yr", r: true }, { t: "after 5 yrs", r: true }, { t: "after 10 yrs", r: true }],
    mps.map((p) => { const b = D.probability_below_start[p.id]; return tr([esc(p.name), R(pct(p.target_vol, 1)), R(pct(p.expected_return, 2)), R(pct(p.equity_share)), R(pct(b["1"])), R(pct(b["5"])), R(pct(b["10"]))]); }));
  const rs = D.resampling;
  const range = rangeChart({ w: 560, rows: rs.rows.map((r) => ({ label: nameOf(r.asset), base: r.base, mean: r.mean, lo: r.p5, hi: r.p95 })) });
  const sens = table(["Expected return raised by 0.5 pts", { t: "Largest weight change", r: true }, { t: "Turnover", r: true }],
    D.sensitivity.map((s) => tr([esc(nameOf(s.asset)), R(pts(s.max_weight_change, 1) + " pts"), R(pct(s.turnover, 1))])));
  const cma = table(["Asset class", "Group", { t: "Expected return", r: true }, { t: "Volatility", r: true }, "Mock fund"],
    ac.map((a) => tr([esc(a.name), esc(a.group), R(pct(a.expected_return, 1)), R(pct(a.volatility, 1)), esc(a.fund)])));
  const lo = mps[0], hi = mps[mps.length - 1], bal = riskOf("balanced");
  return `${pageHead("Portfolio optimization · risk metrics", "Model portfolios", "Five model portfolios, from Conservative to Aggressive growth. Each is the highest expected return for its risk budget under the same rules, measured with the standard metrics an investment team uses.")}
  <main><div class="wrap">
    ${inShort([
      ["5", `model portfolios, from ${pct(lo.expected_return, 1)} to ${pct(hi.expected_return, 1)} expected return for ${pct(lo.volatility)} to ${pct(hi.volatility)} volatility`],
      [pct(bal.var95_1y, 1), "one-year 95% value at risk for Balanced: in one year out of twenty, the loss could be larger than this"],
      [pct(bal.max_drawdown, 0), "median worst fall from a peak for Balanced over 25 simulated years"],
    ])}
    <div class="panel"><h3>Risk metrics</h3><p class="sub">Medians across ${D.backtest.n_histories} simulated 25-year monthly histories after fees, plus 50,000 simulated one-year outcomes for value at risk. Risk-free rate ${pct(D.assumptions.risk_free, 1)}. Definitions are in the <a href="#/about">glossary</a>.</p>${riskT}</div>
    <div class="panel"><h3>Efficient frontier</h3><p class="sub">Each point on the line is the least risky mix for its expected return, under the policy rules. The model portfolios sit on it; single asset classes sit below it.</p>${fr}</div>
    <div class="panel"><h3>What a client asks: how likely am I to be below what I put in?</h3><p class="sub">Chance the portfolio is worth less than its starting value, after fees, at each horizon.</p>${statsT}</div>
    <div class="grid2 mt">
      <div class="panel"><h3>Allocation by asset group</h3><p class="sub">Risk parity, which gives each risky asset class an equal share of risk, is shown for comparison.</p>${stack}</div>
      <div class="panel"><h3>Weights by asset class</h3><p class="sub">The same bounds apply to every portfolio; equity is capped at 90%.</p>${wTable}</div>
    </div>
    <div class="grid2 mt">
      <div class="panel"><h3>How stable are the Balanced weights?</h3><p class="sub">Inputs re-estimated from ${rs.n} simulated ten-year histories, then re-optimized. A wide range means the weight owes more to estimation noise than to signal.</p>${range}</div>
      <div class="panel"><h3>Sensitivity to one input</h3><p class="sub">Optimized weights react strongly to expected returns. This is that reaction for Balanced, one asset class at a time.</p>${sens}</div>
    </div>
    <div class="panel mt"><h3>Capital market assumptions (mock)</h3><p class="sub">Annual, nominal, in Canadian dollars. Illustrative round numbers, not forecasts. Full correlation matrix: <code class="inline">GET /api/v1/assumptions</code>.</p>${cma}</div>
  </div></main>`;
}

// ---------- trading ----------
function trading(q) {
  const RB = D.rebalances.find((r) => r.account.id === (q.get("a") || "A2")) || D.rebalances[0];
  const a = RB.account, r = RB.result;
  const tabs = D.rebalances.map((x) => `<button class="tab" aria-pressed="${x.account.id === a.id}" data-a="${x.account.id}">${esc(x.account.owner)} · ${esc(x.account.type)}<small>${esc(x.result.status)}</small></button>`).join("");
  const codes = D.assumptions.asset_classes.map((c) => c.code);
  const post = r.post_drift || r.drift;
  const drift = driftChart({ w: 560, rows: codes.filter((c) => r.targets[c] > 0 || r.pre_weights[c] > 0).map((c) => ({ label: nameOf(c), pre: r.drift[c], band: r.bands[c], post: post[c] })) });
  const orders = r.orders.length ? table(["Order", { t: "Units", r: true }, { t: "Price", r: true }, { t: "Value", r: true }, "Status", "Pre-trade checks"],
    r.orders.map((o) => tr([`<b>${o.side}</b> ${esc(o.fund)}`, R(num(o.units)), R("$" + o.price.toFixed(2)), R(money(o.value)), status(o.status),
      `<details class="order"><summary class="small">${o.checks.filter((c) => c.status === "PASS").length} of ${o.checks.length} passed${o.checks.some((c) => c.status !== "PASS") ? " · " + o.checks.filter((c) => c.status !== "PASS").map((c) => esc(c.name)).join(", ") : ""}</summary>
        <div class="checks" style="margin-top:6px">${o.checks.map((c) => `<span>${status(c.status)} ${esc(c.id)} ${esc(c.name)}: ${esc(c.detail)}</span>`).join("")}</div></details>`])))
    : `<p class="muted">No orders: every asset class is inside its band and there is no cash flow to invest or raise.</p>`;
  const trig = { none: "None", bands: "Band breach", deposit: "Deposit", withdrawal: "Withdrawal" }[r.trigger];
  const P = D.rebalance_policy;
  const checksList = [
    ["C1", "Client restriction", "No new purchases in a restricted asset class; existing units may be sold."],
    ["C2", "Price freshness", "Quote no more than one business day old."],
    ["C3", "No short sale", "Never sell more units than are held."],
    ["C4", "Order size", `Orders above ${pct(P.max_order_share)} of the account go to review.`],
    ["C5", "Moves toward target", "Each order must reduce that asset class&#8217;s drift, a guard against sign errors."],
    ["C6", "Cash available", `Buys are funded by cash and sells, keeping a ${pct(P.cash_buffer, 1)} buffer.`],
  ];
  const bt = D.backtest;
  const byId = Object.fromEntries(bt.policies.map((p) => [p.id, p]));
  const pol = table(["Policy", { t: "Return a year", r: true }, { t: "Volatility", r: true }, { t: "Max drawdown", r: true }, { t: "Tracking error", r: true }, { t: "Turnover a year", r: true }, { t: "Rebalances a year", r: true }, { t: "Worst drift", r: true }],
    bt.policies.map((p) => tr([esc(p.name), R(pct(p.cagr, 2)), R(pct(p.volatility, 1)), R(pct(p.max_drawdown, 1)), R(pct(p.tracking_error, 2)), R(pct(p.turnover_per_year, 1)), R(p.rebalances_per_year.toFixed(1)), R(pts(p.worst_drift, 1) + " pts")], p.id === "bands" ? "hl" : "")));
  const months = bt.sample_equity_share.none.map((_, i) => i + 1);
  const colors = { none: "var(--s2)", annual: "var(--s3)", quarterly: "var(--s4)", bands: "var(--s1)" };
  const eq = lineChart({
    title: "Equity share in one simulated history", x: months, height: 280, padL: 54,
    series: bt.policies.map((p) => ({ name: p.name, values: bt.sample_equity_share[p.id], color: colors[p.id] })),
    refLines: [{ y: bt.target_equity_share, label: "Target " + pct(bt.target_equity_share) }],
    yFmt: (v) => Math.round(v * 100) + "%", xFmt: (m) => "Year " + Math.round(m / 12), xTicks: [60, 120, 180, 240, 300], xTipFmt: (m) => `Year ${Math.floor((m - 1) / 12) + 1}, month ${((m - 1) % 12) + 1}`, tipFmt: (v) => pct(v, 1),
  });
  const oc = orderCounts();
  return `${pageHead("Trading algorithms · backtests", "Rebalancing and orders", "Six mock accounts, each set up to test a different path through the engine: a deposit, a market rally, a taxable sale, a withdrawal, a client restriction, and nothing to do. Pick an account.")}
  <main><div class="wrap">
    ${inShort([
      [String(oc.total), `orders generated across six accounts; <b>${oc.blocked}</b> held back by pre-trade checks before reaching a desk`],
      [pct(byId.bands.turnover_per_year, 1), `turnover a year with tolerance bands, vs ${pct(byId.quarterly.turnover_per_year, 1)} for quarterly rebalancing`],
      [pct(byId.bands.tracking_error, 2), `tracking error with bands, vs ${pct(byId.none.tracking_error, 2)} if the account is never rebalanced`],
    ])}
    <div class="tabs" role="group" aria-label="Account">${tabs}</div>
    <div class="panel"><h3>${esc(a.owner)} · ${esc(a.type)} · ${esc(profileName(a.risk_profile))}</h3><p class="sub">${esc(a.story)}</p>
      <div class="tiles">
        ${tile("Account value", money(r.total_value), a.cash_flow ? `includes a ${a.cash_flow > 0 ? "deposit" : "withdrawal"} of ${money(Math.abs(a.cash_flow))}` : "no cash flow")}
        ${tile("Trigger", trig, r.breaches.length ? "breached: " + r.breaches.map(esc).join(", ") : "no band breached")}
        ${tile("Largest drift", `${pts(Math.max(...Object.values(r.drift).map(Math.abs)), 1)} → ${pts(r.max_post_drift, 1)} pts`, "before → after orders")}
        ${tile("Turnover", pct(r.turnover, 1), "of account value")}
        ${tile(a.type === "Non-registered" ? "Realized capital gain" : "Realized gain", a.type === "Non-registered" ? money(r.realized_gain) : "Not taxable", a.type === "Non-registered" ? "average-cost ACB method" : "registered account")}
      </div>
    </div>
    <div class="grid2 mt">
      <div class="panel"><h3>Drift from target</h3><p class="sub">Shaded: each asset class&#8217;s tolerance band (5 points or 25% of target, whichever is smaller). Black tick: where the orders leave it.</p>${drift}</div>
      <div class="panel"><h3>Orders and pre-trade checks</h3><p class="sub">${esc(r.status)}. Expand an order to see each check.</p>${orders}
        ${r.skipped && r.skipped.length ? `<p class="note">Not traded: ${r.skipped.map((s) => `${esc(s.code)} (${money(s.value)}, ${esc(s.reason)})`).join("; ")}.</p>` : ""}</div>
    </div>
    <div class="panel mt"><h3>The six pre-trade checks</h3><p class="sub">Whole units only, sells before buys, ${money(P.min_order)} minimum order; on a band rebalance, gaps under ${pct(P.min_trade_weight, 1)} of the account are left alone.</p>
      ${table(["Check", "Name", "Rule"], checksList.map(([id, n, rule]) => tr([id, esc(n), rule])))}
    </div>
    <div class="panel mt"><h3>Which rebalancing policy? A backtest</h3><p class="sub">Balanced portfolio, ${bt.n_histories} simulated ${bt.years}-year monthly histories, ${bt.cost_bps} bps per dollar traded. Medians across histories; tracking error is measured against a portfolio rebalanced every month at no cost.</p>${pol}
      <p class="note">Bands keep the account close to target at a fraction of the trading, because they act only when drift is large enough to matter.</p></div>
    <div class="panel mt"><h3>Equity share in one simulated history</h3><p class="sub">The same 25 years under each policy. Never rebalancing lets the equity share wander far from target.</p>${eq}</div>
  </div></main>`;
}

// ---------- validation ----------
function validation() {
  const V = D.validation;
  const conv = V.convergence;
  const convChart = lineChart({
    title: "Convergence", w: 560, x: conv.map((c) => c.paths), logX: true, height: 260, padL: 58, xTicks: conv.map((c) => c.paths),
    series: [
      { name: "Spread across 12 seeds (observed)", values: conv.map((c) => c.sd_across_seeds), color: "var(--s1)", dots: true },
      { name: "Binomial standard error (theory)", values: conv.map((c) => c.theoretical_se), color: "var(--s2)", dots: true },
    ],
    yMin: 0, yFmt: (v) => (v * 100).toFixed(1) + " pts", xFmt: (n) => (n >= 1000 ? n / 1000 + "K" : n), xTipFmt: (n) => num(n) + " paths", tipFmt: (v) => (v * 100).toFixed(2) + " pts", xLabel: "Paths per plan (log scale)",
  });
  const cal = V.calibration;
  const wc = { model: "var(--s1)", fat_tails: "var(--s3)", optimistic: "var(--s2)" };
  const rel = reliabilityChart({ w: 560, series: cal.worlds.map((w) => ({ name: w.name, color: wc[w.id], points: w.reliability })) });
  const calT = table(["Future world", { t: "Brier score", r: true }, { t: "If calibrated", r: true }, { t: "Mean predicted", r: true }, { t: "Mean realized", r: true }],
    cal.worlds.map((w) => tr([esc(w.name), R(w.brier.toFixed(3)), R(w.brier_if_calibrated.toFixed(3)), R(pct(w.mean_predicted, 1)), R(pct(w.mean_realized, 1))])));
  const person = hh(V.stress_household).profile;
  const stress = barChart({ w: 560, title: "Stress tests", rows: V.stress.map((s, i) => ({ label: s.case, value: s.probability_of_success, color: i === 0 ? "var(--s1)" : "var(--seq-3)" })), max: 1, fmt: (v) => pct(v), padL: 215 });
  const checks = table(["Data check", "Status", "Detail"], D.data_checks.map((c) => tr([esc(c.check), status(c.status), esc(c.detail)])));
  const inv = D.model_inventory.map((m) => `<div class="card"><h4>${esc(m.id)} · ${esc(m.name)}</h4><p class="muted small" style="margin-top:4px">Risk tier: ${esc(m.tier)} (illustrative)</p>
    <dl><dt>Purpose</dt><dd>${esc(m.purpose)}</dd><dt>Inputs</dt><dd>${esc(m.inputs)}</dd><dt>Outputs</dt><dd>${esc(m.outputs)}</dd><dt>Assumptions</dt><dd>${esc(m.assumptions)}</dd><dt>Limitations</dt><dd>${esc(m.limitations)}</dd><dt>Tests</dt><dd>${esc(m.tests)}</dd><dt>Monitoring</dt><dd>${esc(m.monitoring)}</dd></dl></div>`).join("");
  const T = D.tests;
  const testsT = table(["Test file", { t: "Tests", r: true }], Object.entries(T.per_file).map(([f, n]) => tr([`<code class="inline">${esc(f)}</code>`, R(n)])));
  const model = cal.worlds.find((w) => w.id === "model"), opt = cal.worlds.find((w) => w.id === "optimistic");
  const dc = D.data_checks;
  const atPaths = conv.find((c) => c.paths === D.meta.paths_per_plan) || conv[conv.length - 2];
  return `${pageHead("Probability models · data quality · best practices", "Validation", "A probability shown to a client is a claim about the future. These are the checks I would run before trusting one, and the ones that keep the code honest.")}
  <main><div class="wrap">
    ${inShort([
      [model.brier.toFixed(3), `Brier score when the world behaves like the model, against ${model.brier_if_calibrated.toFixed(3)} for a perfectly calibrated one: the probabilities can be trusted`],
      [`${pts(opt.mean_predicted - opt.mean_realized, 0)} pts`, "of overconfidence if returns come in 1.5 points lower than assumed: the assumptions are the risk to monitor"],
      [`${T.passed} / ${T.passed + T.failed}`, `automated tests passing; ${dc.filter((c) => c.status === "PASS").length} data checks pass and the planted stale price is caught`],
    ])}
    <div class="grid2">
      <div class="panel"><h3>Does the answer settle?</h3><p class="sub">${esc(person.name)}&#8217;s plan, run with 12 different seeds at each path count. The spread shrinks as theory predicts; at ${num(D.meta.paths_per_plan)} paths the probability is good to about ±${pts(atPaths.sd_across_seeds, 1)} points.</p>${convChart}</div>
      <div class="panel"><h3>Stress tests</h3><p class="sub">${esc(person.name)}&#8217;s probability of success under five scenarios, ${num(D.meta.paths_per_plan)} paths each.</p>${stress}
        <p class="note">Fatter tails at the same volatility barely move a ${person.plan_to_age - person.age}-year plan; lower returns, higher inflation and a bad first retirement year do.</p></div>
    </div>
    <div class="panel mt"><h3>Are the probabilities calibrated?</h3>
      <p class="sub">${num(cal.n_plans)} random plans. For each, the model predicts a probability of success from ${num(cal.n_paths)} paths; then one &#8220;real&#8221; future is drawn from three different worlds. A calibrated model&#8217;s 70% plans succeed about 70% of the time, so its points sit on the diagonal.</p>
      <div class="grid2"><div>${rel}</div><div>${calT}<p class="note">The Brier score is the average squared gap between the predicted probability and what happened (1 or 0); lower is better. &#8220;If calibrated&#8221; is the score a perfect model would get on the same predictions.</p></div></div>
    </div>
    <div class="panel mt"><h3>Data-quality checks</h3><p class="sub">Run before any model sees the inputs. The stale quote is planted on purpose; the pre-trade check blocks orders in it.</p>${checks}</div>
    <div class="panel mt"><h3>Model inventory</h3><p class="sub">One card per model, with the fields OSFI&#8217;s Guideline E-23 on model risk management (in force for federally regulated institutions from May 1, 2027) expects an inventory to hold. Tiers are illustrative.</p><div class="cards">${inv}</div></div>
    <div class="grid2 mt">
      <div class="panel"><h3>Automated tests</h3><p class="sub"><b>${T.passed} passing, ${T.failed} failing</b> at the last build. They cover constraints, closed-form checks, seeds, calibration, every pre-trade check and every API error path.</p>${testsT}</div>
      <div class="panel"><h3>Practices in the code</h3><ul class="small" style="margin:6px 0 0;padding-left:18px">
        <li>Fixed seeds and common random numbers: a change in output is a change in the model, never in luck.</li>
        <li>Closed-form checks: at zero volatility the simulator must match the hand calculation.</li>
        <li>Property tests: more saving never lowers success; more spending never raises it.</li>
        <li>Defence in depth: generated orders cannot short, and check C3 still verifies it.</li>
        <li>Validated inputs at the API boundary, structured errors, request IDs.</li>
        <li>One build script produces every number on this site from the code.</li></ul></div>
    </div>
  </div></main>`;
}

// ---------- api ----------
function api() {
  const L = D.api.latency;
  const endpoints = [
    ["GET", "/api/v1/status", "Service status and data-quality checks"],
    ["GET", "/api/v1/assumptions", "Capital market assumptions, correlations, bounds"],
    ["GET", "/api/v1/model-portfolios", "The five model portfolios"],
    ["POST", "/api/v1/portfolios/optimize", "Optimize for a risk profile or a volatility budget"],
    ["POST", "/api/v1/plans/simulate", "Monte Carlo goal projection (up to 50,000 paths)"],
    ["POST", "/api/v1/health-score", "Financial health score and next best actions"],
    ["POST", "/api/v1/accounts/rebalance", "Rebalance an account and run the pre-trade checks"],
    ["GET", "/api/v1/households", "List mock households"],
    ["GET", "/api/v1/households/{id}", "One mock household"],
    ["GET", "/api/v1/openapi.json", "OpenAPI 3.1 description"],
  ];
  const lat = table(["Call", { t: "Calls", r: true }, { t: "Median", r: true }, { t: "95th percentile", r: true }], L.map((l) => tr([esc(l.label), R(l.calls), R(l.p50_ms.toFixed(1) + " ms"), R(l.p95_ms.toFixed(1) + " ms")])));
  const samples = D.api.samples.map((s) => `<details style="margin-top:10px"><summary><b>${esc(s.method)}</b> <code class="inline">${esc(s.path)}</code> · ${esc(s.label)} · <span class="muted">HTTP ${s.status}</span></summary>
    ${s.request ? `<pre>${esc(typeof s.request === "string" ? s.request : JSON.stringify(s.request, null, 2))}</pre>` : ""}<pre>${esc(JSON.stringify(s.response, null, 2))}</pre></details>`).join("");
  const sim = L.find((l) => l.label.startsWith("Monte Carlo"));
  return `${pageHead("API services", "The REST API", "The models sit behind a Flask API, so the platform&#8217;s other services call one tested implementation instead of copying the maths.")}
  <main><div class="wrap">
    ${inShort([
      [String(endpoints.length), "REST endpoints over the same tested libraries, described in OpenAPI 3.1"],
      [sim.p50_ms.toFixed(0) + " ms", "median time for a 5,000-path Monte Carlo plan, measured locally"],
      ["400 · 422", "clear, structured errors for bad input or impossible plans, never a crash"],
    ])}
    <div class="grid2">
      <div class="panel"><h3>Endpoints</h3>${table(["Method", "Path", "Purpose"], endpoints.map(([m, p, d]) => tr([`<b>${m}</b>`, `<code class="inline">${esc(p)}</code>`, esc(d)])))}</div>
      <div class="panel"><h3>Engineering choices</h3><ul class="small" style="margin:6px 0 0;padding-left:18px">
        <li>Request bodies validated against JSON Schema (draft 2020-12); unknown fields rejected.</li>
        <li>Errors as <code class="inline">application/problem+json</code> (RFC 9457), naming the field that failed.</li>
        <li>Every response carries <code class="inline">X-Request-ID</code> and <code class="inline">X-Elapsed-Ms</code>.</li>
        <li>Simulation size capped at 50,000 paths so one call cannot starve the service.</li>
        <li>Model portfolios computed once and cached; simulations seeded and reproducible.</li>
        <li>Business-rule errors (a retired household with contributions) return 422, not 500.</li>
        <li>A test fails if a route is missing from the OpenAPI description.</li></ul></div>
    </div>
    <div class="panel mt"><h3>Latency</h3><p class="sub">Measured at build time with Flask&#8217;s test client on my machine: a sanity check, not a production benchmark.</p>${lat}</div>
    <div class="panel mt"><h3>Sample calls</h3><p class="sub">Real requests and responses captured at build time (long arrays trimmed).</p>${samples}</div>
    <div class="panel mt"><h3>Run it</h3>
      <pre>python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest                      # ${D.tests.passed} tests
python -m flask --app api.app run     # http://127.0.0.1:5000/api/v1/status
python build_site.py                  # rebuild docs/data/engine.json

docker build -t wealth-engine .
docker run -p 8000:8000 wealth-engine # gunicorn on port 8000</pre></div>
  </div></main>`;
}

// ---------- phase-in ----------
const PHASES = [
  { when: "Before day one", sub: "between offer and start", team: ["Read RBC&#8217;s purpose and values and the latest annual report, Wealth Management sections first.", "Ask my manager for a 30-minute call: team, priorities, what a good first quarter looks like."],
    role: ["Refresh Flask and Django: my production APIs are FastAPI.", "Cloud and container fundamentals on the platform the team uses (AWS or Azure).", "Reread OSFI Guideline E-23 for how model changes are documented and approved."],
    delivery: ["Declare outside activities and personal trading accounts under the Code of Conduct, and set my own trading to fit the pre-clearance rules.", "Arrive with a list of questions and a setup checklist."],
    done: "I start with the paperwork done and my questions written down." },
  { when: "Weeks 1 to 2", sub: "learn", team: ["One-on-ones with my manager and each engineer: what they own, what slows them down.", "Join the team&#8217;s routines: stand-up, planning, reviews, demos."],
    role: ["Complete the mandatory training: conduct, privacy, information security, anti-money laundering.", "Get the development environment running; read the computational libraries end to end with their tests.", "Map the API services and who calls them."],
    delivery: ["Ship one small pull request, a test or a documentation fix, through the full review and release path."],
    done: "I can run the tests and one service locally, and one reviewed change of mine is merged." },
  { when: "Weeks 3 to 6", sub: "contribute", team: ["Pair with an engineer on a feature; review other people&#8217;s pull requests early and often.", "Learn the coding standards; write down any that live only in people&#8217;s heads."],
    role: ["Learn how a model change is validated and approved, how releases reach production and how incidents are handled.", "Learn the data sources behind the models and their known quirks."],
    delivery: ["Own a scoped ticket in a quantitative library, such as a faster Monte Carlo loop or a missing validation test, with tests and documentation."],
    done: "A change of mine in a computational library is in production." },
  { when: "Months 2 to 3", sub: "own", team: ["Walk the team through one library I have learned; teaching is how I check I understand it.", "Meet the partner teams: product, advice, model validation, data."],
    role: ["Follow a client end to end: profile to portfolio, plan, health score and orders, and where each number comes from."],
    delivery: ["Deliver one feature end to end.", "Propose one improvement from this prototype where it fits, such as calibration monitoring for success probabilities or a pre-trade check report."],
    done: "I own a component, and the team trusts my reviews on it." },
  { when: "Months 4 to 6", sub: "extend", team: ["Mentor through code reviews; help newer teammates get set up.", "Contribute to shared practices: test patterns, fixed seeds, model documentation templates."],
    role: ["Go deeper on the team&#8217;s cloud and container stack.", "Learn how the platform&#8217;s numbers are monitored once they are live."],
    delivery: ["Lead a small project through validation, for example a backtest framework for a new portfolio rule or a new probability model."],
    done: "I lead pieces of work, not only tickets." },
  { when: "Months 6 to 12", sub: "grow", team: ["Join an employee resource group and a community initiative.", "Build relationships across Wealth Management and Technology."],
    role: ["Sit the CFA Level I exam (May 2027).", "Bring machine learning in where it earns its place against a simpler model."],
    delivery: ["Agree a roadmap for the next year of the computational libraries with my manager."],
    done: "Year-one review: delivered, trusted, still learning." },
];

function phaseIn() {
  const values = [
    ["Client First", "Every number this code produces may be something a client acts on. I test it as if it were."],
    ["Integrity", "I would rather flag a doubtful number than ship it, and say plainly what a model cannot do."],
    ["Collaboration", "Ask early, review generously, and write things down so the next person does not have to ask."],
    ["Respect", "I am new to Canadian banking. The people who built the platform know things no document will tell me."],
    ["Excellence", "Tests, documentation and measured results, not opinions about quality."],
  ];
  const questions = [
    "Which part of the platform do clients feel most when it goes wrong?",
    "How does a model change get from a pull request to production, and who signs off?",
    "What would you want me to have shipped by the end of my first quarter?",
    "Where is the code least tested, and what has stopped the team from fixing it?",
    "Who outside the team should I meet in my first month?",
  ];
  return `${pageHead("Phase-in plan", "My first year on the team", "How I would get used to the team, the role and RBC&#8217;s way of working, and what I would deliver at each step. A plan to adjust with my manager in the first week, not a fixed script.")}
  <main><div class="wrap">
    ${inShort([
      ["Week 2", "first reviewed change merged, through the team&#8217;s full release path"],
      ["Month 3", "own a component end to end, and propose one improvement"],
      ["Month 12", "next year&#8217;s roadmap for the libraries agreed with my manager"],
    ])}
    <div class="panel"><div class="phases">
      ${PHASES.map((p) => `<div class="phase"><div class="when">${esc(p.when)}<small>${esc(p.sub)}</small></div><div>
        <div class="tracks"><div><h4>Team and culture</h4><ul>${p.team.map((x) => `<li>${x}</li>`).join("")}</ul></div>
        <div><h4>Role and platform</h4><ul>${p.role.map((x) => `<li>${x}</li>`).join("")}</ul></div>
        <div><h4>Delivery</h4><ul>${p.delivery.map((x) => `<li>${x}</li>`).join("")}</ul></div></div>
        <div class="done"><b>Done when:</b> ${esc(p.done)}</div></div></div>`).join("")}
    </div></div>
    <div class="grid2 mt">
      <div class="panel"><h3>RBC&#8217;s values, in this job</h3><p class="sub">RBC lists five shared values. This is what each would mean in my daily work.</p>
        ${table(["Value", "In practice"], values.map(([v, t]) => tr([`<b>${esc(v)}</b>`, esc(t)])))}</div>
      <div class="panel"><h3>Questions for my first one-on-ones</h3><ol class="actions">${questions.map((x) => `<li>${esc(x)}</li>`).join("")}</ol>
        <p class="note">I would also ask each person what they wish they had known in their first month.</p></div>
    </div>
  </div></main>`;
}

// ---------- about + glossary ----------
const GLOSSARY = [
  ["Probability of success", "Share of simulated markets in which the household&#8217;s money lasts to the planning age."],
  ["Monte Carlo simulation", "Running a plan through thousands of randomly generated market paths to see the range of outcomes, not one forecast."],
  ["Efficient frontier", "The set of portfolios with the highest expected return for each level of risk."],
  ["Volatility", "How much returns typically swing in a year (standard deviation)."],
  ["Sharpe ratio", "Return above cash per unit of volatility. Higher is better."],
  ["Sortino ratio", "Like Sharpe, but counts only downside swings as risk."],
  ["Value at risk (VaR 95%)", "A one-year loss that is exceeded in only one year out of twenty."],
  ["Conditional VaR (CVaR 95%)", "The average loss in those worst one-in-twenty years. Always at least the VaR."],
  ["Maximum drawdown", "The largest fall from a previous peak before recovering."],
  ["Calmar ratio", "Return a year divided by the size of the maximum drawdown."],
  ["Tracking error", "How far an account&#8217;s returns stray from its model portfolio, per year."],
  ["Turnover", "Share of the account traded in a year; more turnover means more cost."],
  ["Tolerance bands (5/25)", "Rebalance only when an asset class drifts more than 5 points or 25% of its target, whichever is smaller."],
  ["Risk parity", "A mix where each asset class contributes the same share of total risk."],
  ["Resampling", "Re-estimating the inputs from simulated histories and re-optimizing, to see how much of a weight is noise."],
  ["Brier score", "Average squared gap between predicted probabilities and actual 0/1 outcomes. Lower is better."],
  ["Calibration", "Whether events predicted at 70% happen about 70% of the time."],
  ["ACB", "Adjusted cost base: the average cost used in Canada to compute a capital gain."],
];

function about() {
  return `${pageHead("About", "Why I built this", "A resume cannot show how I would think about a client&#8217;s plan, a model portfolio or a pre-trade check. This can, and it is the kind of work the role describes.")}
  <main><div class="wrap">
    <div class="grid2">
      <div class="panel"><h3>Tiago Costa</h3><p class="sub">Electrical engineer from Brazil, based in Waterloo, Ontario. Since 2017 I have built and run systematic strategies with my own capital: research and backtests in Python, machine-learning models with walk-forward validation, the order management system that trades them on Brazil&#8217;s B3 exchange, and a FastAPI and PostgreSQL application that reconciles every trade. Before that I traded a bilateral power contract portfolio at EDP and led the launch of EDP Solar. Level I Candidate in the CFA Program (May 2027 exam).</p>
        <p class="sub" style="margin-bottom:0"><a href="https://www.linkedin.com/in/tiagonbc">linkedin.com/in/tiagonbc</a></p></div>
      <div class="panel"><h3>Read this first</h3><ul class="small" style="margin:6px 0 0;padding-left:18px">
        <li>This is a preliminary version. Every number comes from mock data (fictional households, accounts, funds and prices, and illustrative market assumptions), except the SPY statistics on the Statistics page, which use real total-return data from Norgate.</li>
        <li>It is independent work. RBC has not reviewed, endorsed or contributed to it, and it uses no RBC data, product, logo or methodology. The colours follow RBC&#8217;s public website.</li>
        <li>Health-score thresholds and rebalancing rules are common industry rules of thumb, chosen for the demonstration.</li>
        <li>Nothing here is financial advice.</li>
        <li>Built with an AI coding agent working under tests; the design, the checks and the review are mine.</li></ul></div>
    </div>
    <div class="panel mt"><h3>Glossary</h3><p class="sub">The metrics and methods on these pages, in plain language.</p>
      <dl class="gloss">${GLOSSARY.map(([t, d]) => `<dt>${esc(t)}</dt><dd>${d}</dd>`).join("")}</dl></div>
  </div></main>`;
}

// ---------- statistics ----------
const FREQ_LABEL = { daily: "Daily", monthly: "Monthly", annual: "Annual", outcome: "All paths" };
const FREQ_WORD = { daily: "days", monthly: "months", annual: "years", outcome: "paths" };
const statSeries = () => D.distributions.series;
const findSeries = (id) => statSeries().find((s) => s.id === id);

function fmtFor(unit, d) {
  if (unit === "money") return { v: (x) => compact(x), axis: (x) => compact(x), tip: (x) => compact(x) };
  const dec = d && d.stdev < 0.02 ? 2 : 1;
  return { v: (x) => (x * 100).toFixed(2) + "%", axis: (x) => (x * 100).toFixed(dec === 2 ? 1 : 0) + "%", tip: (x) => (x * 100).toFixed(dec) + "%" };
}

function readings(d) {
  const r = {};
  const sk = d.skewness, ku = d.excess_kurtosis;
  r.skewness = sk < -0.5 ? "Left-skewed: large losses are more common than gains of the same size" : sk > 0.5 ? "Right-skewed: a long tail of large values on the upside" : "Close to symmetric";
  r.excess_kurtosis = ku > 3 ? "Very fat tails: extreme values far more often than a normal curve predicts" : ku > 1 ? "Fat tails: extreme values more often than normal" : ku < -0.5 ? "Thin tails: fewer extremes than normal" : "Tails close to normal";
  const ratio = d.beyond_3sd / d.beyond_3sd_normal;
  r.beyond_3sd = d.beyond_3sd === 0 ? "None in this sample" : `${ratio.toFixed(1)}× the normal rate of ${(d.beyond_3sd_normal * 100).toFixed(2)}%`;
  r.jarque_bera_p = d.jarque_bera_p < 0.05 ? "Normality rejected at the 5% level" : "No evidence against normality at 5%";
  if (d.autocorr1 != null) r.autocorr1 = Math.abs(d.autocorr1) < 0.05 ? "Little memory: one period says almost nothing about the next" : d.autocorr1 < 0 ? "Mild reversal from one period to the next" : "Mild momentum from one period to the next";
  r.median = d.median > d.mean ? "Median above the mean: a few large losses pull the average down" : d.median < d.mean ? "Median below the mean: a few large values pull the average up" : "";
  r.cvar95 = d.kind === "return" ? "Average loss in the worst 5% of periods" : "";
  r.var95 = d.kind === "return" ? "Loss exceeded in only 5% of periods" : "";
  return r;
}

function statsTable(sA, dA, sB, dB) {
  const fA = fmtFor(sA.unit, dA), fB = sB ? fmtFor(sB.unit, dB) : null;
  const R = readings(dA);
  const isRet = dA.kind === "return";
  const rows = [
    ["Centre", null],
    ["Observations", "n", (v) => num(v)],
    ["Mean", "mean"], ["Median", "median"],
    ...(isRet && dA.ann_mean != null ? [["Mean, annualized", "ann_mean"]] : []),
    ["Spread", null],
    ["Standard deviation", "stdev"], ["Interquartile range (25th to 75th)", "iqr"],
    ...(isRet && dA.ann_vol != null ? [["Volatility, annualized", "ann_vol"]] : []),
    ["Shape", null],
    ["Skewness", "skewness", (v) => v.toFixed(2)],
    ["Excess kurtosis", "excess_kurtosis", (v) => v.toFixed(2)],
    ["Beyond 3 standard deviations", "beyond_3sd", (v) => (v * 100).toFixed(2) + "%"],
    ["Tails", null],
    ["Worst", "min"], ["1st percentile", "p1"], ["5th percentile", "p5"], ["95th percentile", "p95"], ["99th percentile", "p99"], ["Best", "max"],
    ...(isRet ? [["Value at risk, 95%", "var95"], ["Conditional VaR, 95%", "cvar95"]] : []),
    [isRet ? "Share of positive periods" : "Share of paths with money left", "share_positive", (v) => (v * 100).toFixed(1) + "%"],
    ["Tests", null],
    ["Jarque-Bera statistic", "jarque_bera", (v) => v >= 1e5 ? v.toExponential(2) : num(Math.round(v))],
    ["Jarque-Bera p-value", "jarque_bera_p", (v) => v < 0.0001 ? "< 0.0001" : v.toFixed(4)],
    ["Lag-1 autocorrelation", "autocorr1", (v) => (v == null ? "n/a (pooled)" : v.toFixed(3))],
  ];
  const cell = (d, f, key, fx) => { const v = d ? d[key] : undefined; return v === undefined ? "—" : (fx ? fx(v) : (v == null ? "n/a" : f.v(v))); };
  const head = ["Statistic", { t: sA.name, r: true }, ...(sB ? [{ t: sB.name, r: true }] : []), "What it means"];
  const body = rows.map(([label, key, fx]) => key === null
    ? `<tr><td colspan="${sB ? 4 : 3}" style="background:var(--panel-alt);font-weight:500;color:var(--ink-2);font-size:12.5px;text-transform:uppercase;letter-spacing:.05em">${label}</td></tr>`
    : tr([esc(label), R_(cell(dA, fA, key, fx)), ...(sB ? [R_(cell(dB, fB, key, fx))] : []), `<span class="small muted">${esc(R[key] || "")}</span>`]));
  return table(head, body);
}
const R_ = (v) => ({ v, r: true });

function statistics(q) {
  const spy = findSeries("spy");
  const groups = [...new Set(statSeries().map((s) => s.group))];
  const options = (sel, allowNone) => (allowNone ? `<option value="">None</option>` : "") + groups.map((g) => `<optgroup label="${esc(g)}">${statSeries().filter((s) => s.group === g).map((s) => `<option value="${s.id}"${s.id === sel ? " selected" : ""}>${esc(s.name)}</option>`).join("")}</optgroup>`).join("");
  const sid = q.get("s") || (spy ? "spy" : "mp_balanced");
  const cid = q.has("c") ? q.get("c") : (spy ? "ac_USEQ" : "");
  const short = spy ? inShort([
    [`${(spy.freqs.daily.beyond_3sd / spy.freqs.daily.beyond_3sd_normal).toFixed(1)}×`, `as many SPY daily moves beyond 3 standard deviations as a normal curve predicts (${(spy.freqs.daily.beyond_3sd * 100).toFixed(2)}% of days, not 0.27%)`],
    [spy.freqs.monthly.skewness.toFixed(2), "skewness of SPY monthly returns: losses come in larger steps than gains"],
    [`${(spy.freqs.annual.median * 100).toFixed(1)}% vs ${(spy.freqs.annual.mean * 100).toFixed(1)}%`, "SPY median year against its mean year: the average is pulled down by a few bad years"],
  ]) : "";
  return `${pageHead("Statistics · distributions", "Return distributions", "Pick any series to see its whole distribution, not just its average: centre, spread, skewness, fat tails and a normality test, side by side with another series if you like.")}
  <main><div class="wrap">
    ${short}
    <div class="panel">
      <div class="st-controls">
        <label>Series<select id="st-series">${options(sid, false)}</select></label>
        <div><span class="st-lab">Frequency</span><div class="seg" id="st-freq" role="group" aria-label="Frequency"></div></div>
        <label>Compare with<select id="st-compare">${options(cid, true)}</select></label>
        <div class="st-toggles"><label class="chk"><input type="checkbox" id="st-normal" ${q.get("n") === "0" ? "" : "checked"}> Normal curve</label>
          <label class="chk"><input type="checkbox" id="st-log" ${q.get("l") === "1" ? "checked" : ""}> Log scale</label></div>
      </div>
      <p class="small muted" id="st-source" style="margin:10px 0 0"></p>
    </div>
    <div class="panel mt"><h3 id="st-title">Distribution</h3><p class="sub" id="st-sub"></p><div id="st-chart"></div></div>
    <div class="grid2 mt">
      <div class="panel"><h3>Normal Q-Q plot</h3><p class="sub">Each dot is a percentile. On the line, the data behave like a normal distribution; dots bending away at the ends mean fatter tails than normal.</p><div id="st-qq"></div></div>
      <div class="panel"><h3>What it means for the engine</h3><div id="st-insight" style="color:var(--ink-2);font-size:14.5px"></div></div>
    </div>
    <div class="panel mt"><h3>Statistics</h3><p class="sub">Every figure is computed from the full sample at build time.</p><div id="st-table"></div></div>
    <p class="note">SPY statistics are derived from Norgate Data total-return prices; only summary statistics, histograms and quantiles are published here, not the price series. Simulated series come from the mock capital market assumptions. Not investment advice.</p>
  </div></main>`;
}

function mountStatistics(q) {
  const $ = (id) => document.getElementById(id);
  const state = { s: $("st-series").value, f: q.get("f") || "", c: $("st-compare").value };
  const draw = () => {
    const sA = findSeries(state.s);
    const freqs = Object.keys(sA.freqs);
    if (!freqs.includes(state.f)) state.f = freqs.includes("monthly") ? "monthly" : freqs[0];
    $("st-freq").innerHTML = freqs.map((f) => `<button type="button" class="seg-b" aria-pressed="${f === state.f}" data-f="${f}">${FREQ_LABEL[f]}</button>`).join("");
    const dA = sA.freqs[state.f];
    let sB = state.c ? findSeries(state.c) : null;
    let dB = sB && sB.unit === sA.unit ? (sB.freqs[state.f] || null) : null;
    const note = sB && !dB ? ` (${esc(sB.name)} has no ${FREQ_LABEL[state.f].toLowerCase()} data or different units, so it is not compared)` : "";
    if (!dB) sB = null;
    const f = fmtFor(sA.unit, dA);
    $("st-source").innerHTML = `<b>Source:</b> ${esc(sA.source)}${dA.span && !sA.source.includes(dA.span) ? " · " + esc(dA.span) : ""}${sB ? ` &nbsp;|&nbsp; <b>Compared:</b> ${esc(sB.source)}` : ""}${note}`;
    $("st-title").textContent = `${sA.name} · ${FREQ_LABEL[state.f].toLowerCase()}`;
    const above = dA.hist.above ? ` The top 1% (${num(dA.hist.above)} paths above ${f.v(dA.hist.edges[dA.hist.edges.length - 1])}) is left off the chart so the rest stays readable; the statistics include it.` : "";
    $("st-sub").innerHTML = `${num(dA.n)} ${FREQ_WORD[state.f]}. Bars show how often each range occurs; hover a bar to compare it with what a normal curve would expect.${$("st-log").checked ? " Log scale makes the rare extremes visible." : ""}${above}`;
    const P = { name: sA.name, edges: dA.hist.edges, counts: dA.hist.counts, n: dA.n, mean: dA.mean, median: dA.median, sd: dA.stdev, color: "var(--s1)" };
    const C = sB ? { name: sB.name, edges: dB.hist.edges, counts: dB.hist.counts, n: dB.n, color: "var(--s2)" } : null;
    const clip = C ? [Math.min(dA.min, dB.p1), Math.max(dA.max, dB.p99)] : null;
    $("st-chart").innerHTML = histogramChart({ primary: P, compare: C, clip, normal: $("st-normal").checked, logY: $("st-log").checked,
      fmtX: f.axis, fmtTip: f.tip, unitWord: FREQ_WORD[state.f], xLabel: sA.unit === "money" ? "Wealth at the planning age, today's dollars" : "Return per period" });
    $("st-table").innerHTML = statsTable(sA, dA, sB, dB);
    $("st-qq").innerHTML = qqChart({ w: 520, height: 320, fmt: f.axis, series: [{ name: sA.name, color: "var(--s1)", ...dA.qq }, ...(sB ? [{ name: sB.name, color: "var(--s2)", ...dB.qq }] : [])] });
    const insight = [];
    if (sA.id === "spy" || (sB && sB.id === "spy")) {
      const real = sA.id === "spy" ? dA : dB, model = sA.id === "spy" ? dB : dA;
      if (model) insight.push(`Real SPY ${FREQ_WORD[state.f]} show skewness ${real.skewness.toFixed(2)} and excess kurtosis ${real.excess_kurtosis.toFixed(2)}; the simulated series shows ${model.skewness.toFixed(2)} and ${model.excess_kurtosis.toFixed(2)}. The engine&#8217;s lognormal returns are close to normal, so on their own they understate crashes.`);
      else insight.push(`Real SPY ${FREQ_WORD[state.f]} show skewness ${real.skewness.toFixed(2)} and excess kurtosis ${real.excess_kurtosis.toFixed(2)}: not a normal distribution.`);
      insight.push(`That is why the <a href="#/validation">Validation</a> page stress-tests fatter tails (Student t) and lower returns, and why the planner&#8217;s probabilities are checked for calibration rather than trusted.`);
    } else if (sA.unit === "money") {
      insight.push(`Wealth outcomes are strongly right-skewed (skewness ${dA.skewness.toFixed(2)}): a few very good markets produce large balances, so the median (${compact(dA.median)}) is the fairer &#8220;typical&#8221; outcome than the mean (${compact(dA.mean)}).`);
      insight.push(`${(100 - dA.share_positive * 100).toFixed(1)}% of paths end with nothing left: that is the plan&#8217;s failure rate, and the reason the client plan reports a probability, not a single number.`);
    } else {
      insight.push(`Simulated returns are close to normal by construction (skewness ${dA.skewness.toFixed(2)}, excess kurtosis ${dA.excess_kurtosis.toFixed(2)}). Compare with SPY to see what real markets add.`);
    }
    if (dA.kind === "return" && dA.median > dA.mean) insight.push(`The median (${f.v(dA.median)}) sits above the mean (${f.v(dA.mean)}): a typical period is better than the average one, because the average carries the occasional large loss.`);
    $("st-insight").innerHTML = insight.map((t) => `<p style="margin:0 0 8px">${t}</p>`).join("");
    const qs = new URLSearchParams({ s: state.s, f: state.f, c: state.c || "", n: $("st-normal").checked ? "1" : "0", l: $("st-log").checked ? "1" : "0" });
    history.replaceState(null, "", `#/statistics?${qs}`);
  };
  $("st-series").addEventListener("change", (e) => { state.s = e.target.value; draw(); });
  $("st-compare").addEventListener("change", (e) => { state.c = e.target.value; draw(); });
  $("st-normal").addEventListener("change", draw);
  $("st-log").addEventListener("change", draw);
  $("st-freq").addEventListener("click", (e) => { const b = e.target.closest("[data-f]"); if (b) { state.f = b.dataset.f; draw(); } });
  draw();
}

// ---------- design ----------
function design() {
  const sim = D.api.latency.find((l) => l.label.startsWith("Monte Carlo"));
  const T = D.tests;
  const flow = [
    { t: "Inputs", items: ["Capital market assumptions", "Client profiles and goals", "Holdings, cash and prices"], note: "Mock data in this prototype" },
    { t: "Data checks", items: ["Correlation matrix valid", "Weight bounds feasible", "Stale prices flagged", "Household inputs consistent"], note: "Run before any model" },
    { t: "Engine", items: ["Portfolio optimizer", "Monte Carlo planner", "Financial health score", "Rebalancer and pre-trade checks", "Backtests and risk metrics", "Validation"], note: "Python, NumPy, SciPy", accent: true },
    { t: "REST API", items: ["JSON Schema validation", "Standard error format", "Request IDs and timing", "OpenAPI 3.1"], note: `Flask · ${sim.p50_ms.toFixed(0)} ms median plan` },
    { t: "Consumers", items: ["Client and advisor apps", "Batch jobs and reports", "This site, through the build"], note: "All call the same code" },
  ];
  const arch = `<div class="arch">${flow.map((f, i) => `<div class="arch-node${f.accent ? " accent" : ""}"><span class="arch-step">${i + 1}</span><h4>${esc(f.t)}</h4><ul>${f.items.map((x) => `<li>${esc(x)}</li>`).join("")}</ul><p>${esc(f.note)}</p></div>${i < flow.length - 1 ? '<div class="arch-arrow" aria-hidden="true"></div>' : ""}`).join("")}</div>
    <div class="arch-rail"><span><b>Tests</b> ${T.passed} automated tests guard every layer, from the maths to the API&#8217;s error paths</span><span><b>Build</b> <code class="inline">build_site.py</code> runs every model and writes the one data file this site reads</span></div>`;
  const steps = [
    ["Request in", "A request ID is assigned (or echoed from the caller) and a timer starts."],
    ["Validate", "JSON Schema checks types, ranges and the 50,000-path cap; unknown fields are rejected with a 400."],
    ["Business rules", "Impossible plans, such as a retired household still contributing, return a 422."],
    ["Load the model", "Model portfolio weights come from a cache built once at start-up."],
    ["Simulate", "Seeded, correlated returns for nine asset classes, as one array of paths × years × assets."],
    ["Project", "Contributions, withdrawals, fees and inflation applied to every path at once (vectorized)."],
    ["Summarize", "Probability of success, standard error, wealth percentiles and spending at 90% success."],
    ["Respond", `JSON with <code class="inline">X-Request-ID</code> and <code class="inline">X-Elapsed-Ms</code>: about ${sim.p50_ms.toFixed(0)} ms for 5,000 paths.`],
  ];
  const modules = [
    ["data.py", "Inputs and data-quality checks", "validate_assumptions, build_accounts"],
    ["optimize.py", "Portfolio construction", "model_portfolios, efficient_frontier, risk_parity, resampled_weights"],
    ["simulate.py", "Monte Carlo goal planning", "simulate_plan, solve_spending, what_if_grid"],
    ["health.py", "Financial health score", "score_household"],
    ["rebalance.py", "Orders and pre-trade checks", "plan_rebalance, effective_targets"],
    ["backtest.py", "Rebalancing policy backtests", "compare_policies, run_policy"],
    ["risk.py", "Standard risk metrics", "risk_report"],
    ["validation.py", "Convergence, calibration, stress", "convergence, calibration, stress_tests"],
    ["api/app.py", "REST API over the libraries", "create_app, openapi_spec"],
    ["build_site.py", "Build pipeline for this site", "runs every model, writes engine.json"],
  ];
  const decisions = [
    ["Libraries first, a thin API", "All the maths lives in plain Python functions; the API only validates, calls and formats.", "The API, batch jobs, notebooks and this site share one tested implementation.", "Two layers to keep in step; the OpenAPI test catches drift."],
    ["Fixed seeds and common random numbers", "Every simulation takes a seed; what-if comparisons reuse the same paths.", "Same inputs give the same answer, so outputs can be audited and differences come from the levers, not luck.", "Seeds must be stored with results to reproduce them."],
    ["Plans in today&#8217;s dollars", "Returns are converted to real terms after fees before projecting.", "Clients think in today&#8217;s money; spending goals stay comparable across decades.", "Inflation is fixed; a stochastic inflation model is a later step."],
    ["Validate at the boundary", "JSON Schema on every request body; errors follow RFC 9457.", "Bad input never reaches the models, and callers get the exact field that failed.", "Schemas must evolve with the API; versioned under /api/v1."],
    ["Defence in depth on orders", "The generator cannot create a short sale, and check C3 still verifies it.", "A bug in one layer cannot send a harmful order alone.", "Some checks rarely fire; they are tested directly."],
    ["One build, zero hand-typed numbers", "A build script runs every model and writes one JSON file the site reads.", "Every figure on these pages traces back to code and a build time.", "The site shows a snapshot; the API serves live results."],
  ];
  const prod = [
    ["Scale", ["Queue large simulations as background jobs; keep interactive calls under a path cap.", "Cache results keyed by input hash and model version.", "Run stateless containers behind a load balancer on the bank&#8217;s cloud (AWS or Azure)."]],
    ["Reliability", ["Health checks and graceful timeouts on every service.", "Golden-file regression tests: a model change that moves outputs must be intended.", "Performance tests in the pipeline with latency budgets."]],
    ["Model governance", ["Version every model and its assumptions; record the version in each response.", "Inventory, validation sign-off and change control in the shape of OSFI E-23.", "Monitor calibration and score distributions once live."]],
    ["Observability", ["Structured logs keyed by request ID, without personal data.", "Metrics for p50 and p95 latency, error rates and blocked orders by check.", "Alerts on stale market data and drift in model outputs."]],
    ["Security and privacy", ["Authentication and authorization on every endpoint.", "Input limits, dependency scanning and secrets kept out of code.", "Client data minimized, encrypted and never written to logs."]],
    ["Delivery", ["Feature branches, pull requests and review before merge.", "Continuous integration runs tests, linting and type checks.", "Releases promoted through environments with sign-off."]],
  ];
  const lat = D.api.latency.find((l) => l.label.startsWith("Monte Carlo"));
  const nfr = [
    ["Latency", "A 5,000-path plan answers in under 300 ms (p95)", `${lat.p50_ms.toFixed(0)} ms median, ${lat.p95_ms.toFixed(0)} ms p95, measured locally`],
    ["Reproducibility", "Same inputs and seed give the same output", "Tested on every change"],
    ["Correctness", "Closed-form and property tests on every change", `${T.passed} tests, about ${Math.round(T.seconds)} s`],
    ["Input safety", "Invalid input never reaches a model", "JSON Schema; 400, 415 and 422 paths tested"],
    ["Capacity", "One call cannot starve the service", "Paths capped at 50,000 per request"],
    ["Traceability", "Every figure traces to code and inputs", "Build time and version on every page; production adds model version per response"],
  ];
  return `${pageHead("System design", "How it is built", "The architecture behind the prototype, the choices I made and why, and what I would change to run it at a bank&#8217;s scale.")}
  <main><div class="wrap">
    ${inShort([
      ["1", "source of truth: the Python libraries; the API, the batch build and this site all call them"],
      ["0", "numbers typed by hand: every figure on these pages is produced by the build"],
      [String(T.passed), "automated tests guard each layer, from the maths to the API&#8217;s error paths"],
    ])}
    <div class="panel"><h3>Architecture</h3><p class="sub">Data flows left to right. Checks run before the models; the engine is the only place where maths happens.</p>${arch}</div>
    <div class="grid2 mt">
      <div class="panel"><h3>One request, end to end</h3><p class="sub"><code class="inline">POST /api/v1/plans/simulate</code>, step by step.</p>
        <ol class="steps">${steps.map(([h, d]) => `<li><b>${h}</b><span>${d}</span></li>`).join("")}</ol></div>
      <div class="panel"><h3>Modules</h3><p class="sub">Small modules with one job each, so each can be tested on its own. Engine modules live in <code class="inline">wealth_engine/</code>.</p>
        ${table(["Module", "Job", "Entry points"], modules.map(([m, j, e]) => tr([`<code class="inline">${esc(m)}</code>`, esc(j), `<span class="small muted">${esc(e)}</span>`])))}</div>
    </div>
    <h2 class="section-title" style="margin-top:30px">Design decisions</h2>
    <div class="adrs">${decisions.map(([t, d, why, cost], i) => `<div class="adr"><span class="adr-n">D${i + 1}</span><h4>${t}</h4>
      <dl><dt>Decision</dt><dd>${d}</dd><dt>Why</dt><dd>${why}</dd><dt>Trade-off</dt><dd>${cost}</dd></dl></div>`).join("")}</div>
    <h2 class="section-title" style="margin-top:30px">From prototype to production</h2>
    <p class="muted" style="margin:-6px 0 14px;max-width:820px">What I would add to run this inside a bank. These are general engineering practices, not a description of RBC&#8217;s systems.</p>
    <div class="cards5">${prod.map(([t, items]) => `<div class="qcard"><h3>${t}</h3><ul class="small" style="margin:0;padding-left:18px;color:var(--ink-2)">${items.map((x) => `<li style="margin:4px 0">${x}</li>`).join("")}</ul></div>`).join("")}</div>
    <div class="panel mt"><h3>Non-functional requirements</h3><p class="sub">Targets are illustrative; the right column is what the prototype does today.</p>
      ${table(["Requirement", "Target", "Prototype today"], nfr.map(([a, b, c]) => tr([`<b>${a}</b>`, b, c])))}</div>
  </div></main>`;
}

// ---------- router ----------
const routes = { "": overview, clients, portfolios, statistics, trading, validation, api, design, "phase-in": phaseIn, about };
const PAGES = [["", "Overview"], ["clients", "Client plans"], ["portfolios", "Portfolios"], ["statistics", "Statistics"], ["trading", "Trading"],
  ["validation", "Validation"], ["api", "API"], ["design", "Design"], ["phase-in", "Phase-in plan"], ["about", "About"]];

function render() {
  const raw = location.hash.replace(/^#\/?/, "");
  const [path, query] = raw.split("?");
  const fn = routes[path] || overview;
  let html = fn(new URLSearchParams(query || ""));
  const i = Math.max(0, PAGES.findIndex(([p]) => p === (routes[path] ? path : "")));
  const prev = PAGES[i - 1], next = PAGES[i + 1];
  const pn = `<nav class="prevnext" aria-label="Page">${prev ? `<a href="#/${prev[0]}"><small>Previous</small>&#8592; ${prev[1]}</a>` : "<span></span>"}${next ? `<a class="next" href="#/${next[0]}"><small>Next</small>${next[1]} &#8594;</a>` : "<span></span>"}</nav>`;
  const cut = html.lastIndexOf("</div></main>");
  if (cut > -1) html = html.slice(0, cut) + pn + html.slice(cut);
  app.innerHTML = html;
  if (path === "statistics") mountStatistics(new URLSearchParams(query || ""));
  document.querySelectorAll("nav.main a").forEach((a) => {
    const target = a.getAttribute("href").replace(/^#\/?/, "");
    if (target === path || (!routes[path] && target === "")) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  });
  document.getElementById("nav").classList.remove("open");
  document.querySelector(".menu-btn").setAttribute("aria-expanded", "false");
  document.title = (path ? (document.querySelector(`nav.main a[href="#/${path}"]`)?.textContent + " · ") : "") + "Wealth Engine Demonstration";
}

app.addEventListener("click", (e) => {
  const s = e.target.closest("[data-scroll]");
  if (s) { e.preventDefault(); document.getElementById(s.dataset.scroll)?.scrollIntoView({ behavior: "smooth" }); return; }
  const b = e.target.closest("[data-h],[data-a]");
  if (!b) return;
  const y = window.scrollY;
  location.hash = b.dataset.h ? `#/clients?h=${b.dataset.h}` : `#/trading?a=${b.dataset.a}`;
  requestAnimationFrame(() => window.scrollTo(0, y));
});
let lastPath = null;
window.addEventListener("hashchange", () => {
  const path = location.hash.split("?")[0];
  render();
  if (path !== lastPath) window.scrollTo(0, 0);
  lastPath = path;
});
document.querySelector(".skip").addEventListener("click", (e) => { e.preventDefault(); app.focus(); });
document.querySelector(".menu-btn").addEventListener("click", (e) => {
  const nav = document.getElementById("nav");
  const open = !nav.classList.contains("open");
  nav.classList.toggle("open", open);
  e.currentTarget.setAttribute("aria-expanded", String(open));
});

fetch("data/engine.json", { cache: "no-cache" }).then((r) => r.json()).then((d) => {
  D = d;
  document.getElementById("build-line").textContent = `Built ${d.meta.built_at} · version ${d.meta.version} · ${d.tests.passed} tests passing.`;
  lastPath = location.hash.split("?")[0];
  render();
  bindTooltips();
}).catch((err) => {
  app.innerHTML = `<div class="wrap loading">Could not load the engine output (${esc(err.message)}). Serve the docs folder over HTTP, for example: <code class="inline">python -m http.server -d docs</code>.</div>`;
});
