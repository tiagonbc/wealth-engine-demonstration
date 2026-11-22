// Small SVG chart helpers. Every chart returns an HTML string; hover is wired
// once, by delegation, in bindTooltips(). Colours come from CSS variables so
// light and dark mode share one code path.

const registry = new Map();
let uid = 0;

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
export { esc };

function lin(d0, d1, r0, r1) {
  const k = (r1 - r0) / ((d1 - d0) || 1);
  const f = (v) => r0 + (v - d0) * k;
  f.inv = (p) => d0 + (p - r0) / k;
  return f;
}
function logScale(d0, d1, r0, r1) {
  const a = Math.log10(d0), b = Math.log10(d1);
  return (v) => r0 + (Math.log10(v) - a) * (r1 - r0) / (b - a);
}
export function coverTicks(min, max, count = 5) {
  // ticks whose first is <= min and last is >= max, so no point falls outside the axes
  const t = niceTicks(min, max, count);
  const step = t.length > 1 ? t[1] - t[0] : (max - min) || 1;
  while (t[0] > min + 1e-12) t.unshift(+(t[0] - step).toFixed(10));
  while (t[t.length - 1] < max - 1e-12) t.push(+(t[t.length - 1] + step).toFixed(10));
  return t;
}
export function niceTicks(min, max, count = 5) {
  const span = max - min || 1;
  const step0 = span / count;
  const mag = Math.pow(10, Math.floor(Math.log10(step0)));
  const err = step0 / mag;
  const step = (err >= 7.5 ? 10 : err >= 3.5 ? 5 : err >= 1.5 ? 2 : 1) * mag;
  const out = [];
  for (let v = Math.ceil(min / step) * step; v <= max + step * 1e-9; v += step) out.push(+v.toFixed(10));
  return out;
}

const WIDTH = 760;

function frame({ W = WIDTH, x, y, xTicks, yTicks, xFmt, yFmt, h, pad, xLabel, yLabel }) {
  let s = "";
  for (const t of yTicks) {
    s += `<line x1="${pad.l}" x2="${W - pad.r}" y1="${y(t)}" y2="${y(t)}" stroke="var(--grid)" stroke-width="1"/>`;
    s += `<text x="${pad.l - 8}" y="${y(t) + 4}" text-anchor="end" class="num">${esc(yFmt(t))}</text>`;
  }
  for (const t of xTicks) {
    s += `<text x="${x(t)}" y="${h - pad.b + 18}" text-anchor="middle" class="num">${esc(xFmt(t))}</text>`;
  }
  s += `<line x1="${pad.l}" x2="${W - pad.r}" y1="${h - pad.b}" y2="${h - pad.b}" stroke="var(--axis)" stroke-width="1"/>`;
  if (xLabel) s += `<text x="${(pad.l + W - pad.r) / 2}" y="${h - 4}" text-anchor="middle">${esc(xLabel)}</text>`;
  if (yLabel) s += `<text x="${pad.l}" y="${pad.t - 10}" text-anchor="start">${esc(yLabel)}</text>`;
  return s;
}

export function legend(items) {
  return `<div class="legend">${items.map((it) =>
    `<span><i class="${it.kind || ""}" style="background:${it.color}"></i>${esc(it.name)}</span>`).join("")}</div>`;
}

/** Line chart with optional bands, a crosshair and a multi-series tooltip. */
export function lineChart(o) {
  const W = o.w || WIDTH;
  const id = "c" + (++uid);
  const h = o.height || 300;
  const pad = { l: o.padL || 62, r: 20, t: 26, b: 40 };
  const xs = o.x;
  const all = [];
  o.series.forEach((s) => s.values.forEach((v) => v != null && all.push(v)));
  (o.bands || []).forEach((b) => { b.lo.forEach((v) => all.push(v)); b.hi.forEach((v) => all.push(v)); });
  (o.refLines || []).forEach((r) => all.push(r.y));
  let yMin = o.yMin != null ? o.yMin : Math.min(...all);
  let yMax = o.yMax != null ? o.yMax : Math.max(...all);
  if (o.yMin == null) { const span = yMax - yMin; yMin -= span * 0.05; }
  const yTicks = coverTicks(yMin, yMax, 5);
  yMin = Math.min(yMin, yTicks[0]); yMax = Math.max(yMax, yTicks[yTicks.length - 1]);
  const x = o.logX ? logScale(xs[0], xs[xs.length - 1], pad.l, W - pad.r) : lin(xs[0], xs[xs.length - 1], pad.l, W - pad.r);
  const y = lin(yMin, yMax, h - pad.b, pad.t);
  const xTicks = o.xTicks || niceTicks(xs[0], xs[xs.length - 1], 8).filter((t) => t >= xs[0] && t <= xs[xs.length - 1]);
  let s = frame({ W, x, y, xTicks, yTicks, xFmt: o.xFmt || String, yFmt: o.yFmt || String, h, pad, xLabel: o.xLabel, yLabel: o.yLabel });
  for (const b of o.bands || []) {
    const top = xs.map((xv, i) => `${x(xv)},${y(b.hi[i])}`).join(" ");
    const bot = xs.map((xv, i) => `${x(xv)},${y(b.lo[i])}`).reverse().join(" ");
    s += `<polygon points="${top} ${bot}" fill="${b.color}" opacity="${b.opacity || 0.14}"/>`;
  }
  for (const r of o.refLines || []) {
    s += `<line x1="${pad.l}" x2="${W - pad.r}" y1="${y(r.y)}" y2="${y(r.y)}" stroke="var(--ink-3)" stroke-width="1"/>`;
    if (r.label) s += `<text x="${W - pad.r}" y="${y(r.y) - 6}" text-anchor="end">${esc(r.label)}</text>`;
  }
  for (const m of o.markers || []) {
    s += `<line x1="${x(m.x)}" x2="${x(m.x)}" y1="${pad.t}" y2="${h - pad.b}" stroke="var(--axis)" stroke-width="1"/>`;
    s += `<text x="${x(m.x) + 6}" y="${pad.t + 12}" class="ink2">${esc(m.label)}</text>`;
  }
  for (const se of o.series) {
    const pts = xs.map((xv, i) => se.values[i] == null ? null : `${x(xv)},${y(se.values[i])}`).filter(Boolean).join(" ");
    s += `<polyline points="${pts}" fill="none" stroke="${se.color}" stroke-width="${se.width || 2}" stroke-linejoin="round" stroke-linecap="round"/>`;
    if (se.dots) xs.forEach((xv, i) => { if (se.values[i] != null) s += `<circle cx="${x(xv)}" cy="${y(se.values[i])}" r="4" fill="${se.color}" stroke="var(--surface)" stroke-width="2"/>`; });
    if (se.endLabel) {
      const i = se.values.length - 1;
      s += `<text x="${x(xs[i]) - 4}" y="${y(se.values[i]) - 8}" text-anchor="end" class="ink">${esc(se.endLabel)}</text>`;
    }
  }
  s += `<line id="${id}-x" x1="0" x2="0" y1="${pad.t}" y2="${h - pad.b}" stroke="var(--ink-3)" stroke-width="1" visibility="hidden"/>`;
  s += `<rect x="${pad.l}" y="${pad.t}" width="${W - pad.l - pad.r}" height="${h - pad.t - pad.b}" fill="transparent" data-chart="${id}"/>`;
  registry.set(id, { type: "line", o, x, xs, pad, h });
  const lg = o.legend === false ? "" : legend([...o.series.filter((s2) => !s2.hideLegend).map((s2) => ({ name: s2.name, color: s2.color })),
    ...(o.bands || []).filter((b) => b.name).map((b) => ({ name: b.name, color: b.color, kind: "box" }))]);
  return `${lg}<div class="chart"><svg viewBox="0 0 ${W} ${h}" role="img" aria-label="${esc(o.title || "chart")}">${s}</svg></div>`;
}

/** Scatter for the efficient frontier: a line plus labelled points. */
export function frontierChart(o) {
  const W = o.w || WIDTH;
  const id = "c" + (++uid);
  const h = 340;
  const pad = { l: 56, r: 24, t: 26, b: 44 };
  const xsAll = [...o.frontier.map((p) => p.volatility), ...o.points.map((p) => p.x), ...o.assets.map((a) => a.x)];
  const ysAll = [...o.frontier.map((p) => p.expected_return), ...o.points.map((p) => p.y), ...o.assets.map((a) => a.y)];
  const xTicks = coverTicks(0, Math.max(...xsAll) * 1.03, 6);
  const yTicks = coverTicks(Math.min(...ysAll) * 0.95, Math.max(...ysAll) * 1.03, 5);
  const x = lin(xTicks[0], xTicks[xTicks.length - 1], pad.l, W - pad.r);
  const y = lin(yTicks[0], yTicks[yTicks.length - 1], h - pad.b, pad.t);
  const pct = (v) => (v * 100).toFixed(0) + "%";
  let s = frame({ W, x, y, xTicks, yTicks, xFmt: pct, yFmt: (v) => (v * 100).toFixed(1) + "%", h, pad, xLabel: "Volatility (annual)", yLabel: "Expected return (annual)" });
  s += `<polyline points="${o.frontier.map((p) => `${x(p.volatility)},${y(p.expected_return)}`).join(" ")}" fill="none" stroke="var(--s1)" stroke-width="2"/>`;
  for (const a of o.assets) {
    s += `<circle cx="${x(a.x)}" cy="${y(a.y)}" r="4" fill="var(--ink-3)" stroke="var(--surface)" stroke-width="2" data-tip="${esc(a.tip)}"/>`;
    s += `<text x="${x(a.x) + (a.dx ?? 7)}" y="${y(a.y) + (a.dy ?? 4)}" text-anchor="${a.anchor || "start"}">${esc(a.label)}</text>`;
  }
  for (const p of o.points) {
    s += `<circle cx="${x(p.x)}" cy="${y(p.y)}" r="${p.r || 6}" fill="${p.color}" stroke="var(--surface)" stroke-width="2" data-tip="${esc(p.tip)}"/>`;
    if (p.label) s += `<text x="${x(p.x) + (p.dx || -10)}" y="${y(p.y) + (p.dy || -10)}" text-anchor="${p.anchor || "end"}" class="ink">${esc(p.label)}</text>`;
  }
  registry.set(id, { type: "static" });
  return `${legend([{ name: "Efficient frontier", color: "var(--s1)" }, { name: "Model portfolios", color: "var(--s1)", kind: "dot" },
    { name: "Risk parity (risky assets)", color: "var(--s2)", kind: "dot" }, { name: "Single asset classes", color: "var(--ink-3)", kind: "dot" }])}
    <div class="chart"><svg viewBox="0 0 ${W} ${h}" role="img" aria-label="Efficient frontier">${s}</svg></div>`;
}

/** Horizontal stacked bars, one per row; parts carry their own colours. */
export function stackedBars(o) {
  const W = o.w || WIDTH;
  const rowH = 34, barH = 18, padL = o.padL || 170, padR = 16;
  const h = o.rows.length * rowH + 30;
  const x = lin(0, 1, padL, W - padR);
  let s = "";
  for (const t of [0, 0.25, 0.5, 0.75, 1]) {
    s += `<line x1="${x(t)}" x2="${x(t)}" y1="0" y2="${h - 26}" stroke="var(--grid)"/>`;
    s += `<text x="${x(t)}" y="${h - 8}" text-anchor="middle" class="num">${Math.round(t * 100)}%</text>`;
  }
  o.rows.forEach((r, i) => {
    const yy = i * rowH + (rowH - barH) / 2;
    s += `<text x="${padL - 10}" y="${yy + barH / 2 + 4}" text-anchor="end" class="ink">${esc(r.label)}</text>`;
    let acc = 0;
    r.parts.forEach((p) => {
      if (p.value <= 0) return;
      const x0 = x(acc), x1 = x(acc + p.value);
      const wpx = Math.max(x1 - x0 - 2, 0.5);
      s += `<rect x="${x0}" y="${yy}" width="${wpx}" height="${barH}" rx="2" fill="${p.color}" data-tip="${esc(`<b>${r.label}</b><br>${p.name}: ${(p.value * 100).toFixed(1)}%`)}"/>`;
      if (wpx > 44) s += `<text x="${x0 + 6}" y="${yy + barH / 2 + 4}" style="fill:${p.textColor || "#fff"};font-size:11px;font-weight:500">${(p.value * 100).toFixed(0)}%</text>`;
      acc += p.value;
    });
  });
  return `${legend(o.legend)}<div class="chart"><svg viewBox="0 0 ${W} ${h}" role="img" aria-label="${esc(o.title || "stacked bars")}">${s}</svg></div>`;
}

/** Diverging bars around zero with tolerance-band ticks (drift chart). */
export function driftChart(o) {
  const W = o.w || WIDTH;
  const rowH = 30, barH = 14, padL = 150, padR = 20;
  const h = o.rows.length * rowH + 34;
  const lim = Math.max(0.06, ...o.rows.map((r) => Math.abs(r.pre)), ...o.rows.map((r) => r.band)) * 1.1;
  const x = lin(-lim, lim, padL, W - padR);
  let s = "";
  for (const t of niceTicks(-lim, lim, 6)) {
    s += `<line x1="${x(t)}" x2="${x(t)}" y1="0" y2="${h - 28}" stroke="${t === 0 ? "var(--axis)" : "var(--grid)"}"/>`;
    s += `<text x="${x(t)}" y="${h - 10}" text-anchor="middle" class="num">${t > 0 ? "+" : ""}${(t * 100).toFixed(0)}</text>`;
  }
  o.rows.forEach((r, i) => {
    const yy = i * rowH + (rowH - barH) / 2;
    s += `<text x="${padL - 10}" y="${yy + barH / 2 + 4}" text-anchor="end" class="ink">${esc(r.label)}</text>`;
    s += `<rect x="${x(-r.band)}" y="${yy - 3}" width="${x(r.band) - x(-r.band)}" height="${barH + 6}" fill="var(--seq-1)" opacity="0.7"/>`;
    const x0 = x(Math.min(0, r.pre)), x1 = x(Math.max(0, r.pre));
    const breach = Math.abs(r.pre) > r.band;
    s += `<rect x="${x0}" y="${yy}" width="${Math.max(x1 - x0, 1)}" height="${barH}" rx="2" fill="${breach ? "var(--s2)" : "var(--s1)"}"
      data-tip="${esc(`<b>${r.label}</b><br>Drift before: ${(r.pre * 100).toFixed(2)} pts<br>Band: ±${(r.band * 100).toFixed(2)} pts<br>Drift after: ${(r.post * 100).toFixed(2)} pts`)}"/>`;
    s += `<line x1="${x(r.post)}" x2="${x(r.post)}" y1="${yy - 4}" y2="${yy + barH + 4}" stroke="var(--ink)" stroke-width="2"/>`;
  });
  return `${legend([{ name: "Drift inside band", color: "var(--s1)", kind: "box" }, { name: "Drift outside band", color: "var(--s2)", kind: "box" },
    { name: "Tolerance band (5/25)", color: "var(--seq-1)", kind: "box" }, { name: "After orders", color: "var(--ink)" }])}
    <div class="chart"><svg viewBox="0 0 ${W} ${h}" role="img" aria-label="Drift by asset class, percentage points">${s}</svg></div>
    <p class="note">Percentage points away from target weight.</p>`;
}

/** Dot-and-range rows: p5..p95 range, base dot, mean tick. */
export function rangeChart(o) {
  const W = o.w || WIDTH;
  const rowH = 28, padL = 190, padR = 20;
  const h = o.rows.length * rowH + 34;
  const hi = Math.max(...o.rows.map((r) => r.hi), ...o.rows.map((r) => r.base)) * 1.08;
  const x = lin(0, hi, padL, W - padR);
  let s = "";
  for (const t of niceTicks(0, hi, 6)) {
    s += `<line x1="${x(t)}" x2="${x(t)}" y1="0" y2="${h - 28}" stroke="var(--grid)"/>`;
    s += `<text x="${x(t)}" y="${h - 10}" text-anchor="middle" class="num">${(t * 100).toFixed(0)}%</text>`;
  }
  o.rows.forEach((r, i) => {
    const yy = i * rowH + rowH / 2;
    s += `<text x="${padL - 10}" y="${yy + 4}" text-anchor="end" class="ink">${esc(r.label)}</text>`;
    s += `<line x1="${x(r.lo)}" x2="${x(r.hi)}" y1="${yy}" y2="${yy}" stroke="var(--seq-3)" stroke-width="6" stroke-linecap="round" opacity="0.55"/>`;
    s += `<line x1="${x(r.mean)}" x2="${x(r.mean)}" y1="${yy - 7}" y2="${yy + 7}" stroke="var(--ink)" stroke-width="2"/>`;
    s += `<circle cx="${x(r.base)}" cy="${yy}" r="5" fill="var(--s1)" stroke="var(--surface)" stroke-width="2"
      data-tip="${esc(`<b>${r.label}</b><br>Model weight: ${(r.base * 100).toFixed(1)}%<br>Resampled mean: ${(r.mean * 100).toFixed(1)}%<br>5th to 95th percentile: ${(r.lo * 100).toFixed(1)}% to ${(r.hi * 100).toFixed(1)}%`)}"/>`;
  });
  return `${legend([{ name: "Model weight", color: "var(--s1)", kind: "dot" }, { name: "Resampled mean", color: "var(--ink)" },
    { name: "5th to 95th percentile", color: "var(--seq-3)" }])}
    <div class="chart"><svg viewBox="0 0 ${W} ${h}" role="img" aria-label="Resampled weight ranges">${s}</svg></div>`;
}

/** Horizontal bars, one hue. */
export function barChart(o) {
  const W = o.w || WIDTH;
  const rowH = 30, barH = 16, padL = o.padL || 230, padR = 70;
  const h = o.rows.length * rowH + 30;
  const max = o.max || Math.max(...o.rows.map((r) => r.value)) * 1.05;
  const x = lin(0, max, padL, W - padR);
  let s = "";
  for (const t of niceTicks(0, max, 5)) {
    s += `<line x1="${x(t)}" x2="${x(t)}" y1="0" y2="${h - 26}" stroke="var(--grid)"/>`;
    s += `<text x="${x(t)}" y="${h - 8}" text-anchor="middle" class="num">${esc(o.fmt(t))}</text>`;
  }
  o.rows.forEach((r, i) => {
    const yy = i * rowH + (rowH - barH) / 2;
    s += `<text x="${padL - 10}" y="${yy + barH / 2 + 4}" text-anchor="end" class="ink">${esc(r.label)}</text>`;
    const wpx = Math.max(x(r.value) - x(0), 1);
    s += `<path d="M${x(0)},${yy} h${Math.max(wpx - 4, 0)} a4,4 0 0 1 4,4 v${barH - 8} a4,4 0 0 1 -4,4 h${-Math.max(wpx - 4, 0)} z" fill="${r.color || "var(--s1)"}" data-tip="${esc(`<b>${r.label}</b><br>${o.fmt(r.value)}`)}"/>`;
    s += `<text x="${x(r.value) + 8}" y="${yy + barH / 2 + 4}" class="ink num">${esc(o.fmt(r.value))}</text>`;
  });
  return `<div class="chart"><svg viewBox="0 0 ${W} ${h}" role="img" aria-label="${esc(o.title || "bar chart")}">${s}</svg></div>`;
}

/** Reliability diagram: predicted vs realized, with the diagonal. */
export function reliabilityChart(o) {
  const W = o.w || WIDTH;
  const h = 360, pad = { l: 56, r: 20, t: 26, b: 44 };
  const x = lin(0, 1, pad.l, W - pad.r), y = lin(0, 1, h - pad.b, pad.t);
  const t = [0, 0.2, 0.4, 0.6, 0.8, 1];
  let s = frame({ W, x, y, xTicks: t, yTicks: t, xFmt: (v) => Math.round(v * 100) + "%", yFmt: (v) => Math.round(v * 100) + "%", h, pad,
    xLabel: "Predicted probability of success", yLabel: "Share of plans that actually succeeded" });
  s += `<line x1="${x(0)}" y1="${y(0)}" x2="${x(1)}" y2="${y(1)}" stroke="var(--ink-3)" stroke-width="1"/>`;
  for (const se of o.series) {
    s += `<polyline points="${se.points.map((p) => `${x(p.predicted)},${y(p.realized)}`).join(" ")}" fill="none" stroke="${se.color}" stroke-width="2"/>`;
    for (const p of se.points) {
      s += `<circle cx="${x(p.predicted)}" cy="${y(p.realized)}" r="4.5" fill="${se.color}" stroke="var(--surface)" stroke-width="2"
        data-tip="${esc(`<b>${se.name}</b><br>Bin ${p.bin} (${p.n} plans)<br>Predicted ${(p.predicted * 100).toFixed(0)}%, realized ${(p.realized * 100).toFixed(0)}%`)}"/>`;
    }
  }
  return `${legend([...o.series.map((se) => ({ name: se.name, color: se.color })), { name: "Perfect calibration", color: "var(--ink-3)" }])}
    <div class="chart"><svg viewBox="0 0 ${W} ${h}" role="img" aria-label="Calibration reliability diagram">${s}</svg></div>`;
}

// ---------- tooltips ----------
// ---------- distributions ----------
function erf(x) {
  const s = Math.sign(x); x = Math.abs(x);
  const t = 1 / (1 + 0.3275911 * x);
  const y = 1 - ((((1.061405429 * t - 1.453152027) * t + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-x * x);
  return s * y;
}
export const normCdf = (x, m, s) => 0.5 * (1 + erf((x - m) / (s * Math.SQRT2)));
const normPdf = (x, m, s) => Math.exp(-0.5 * ((x - m) / s) ** 2) / (s * Math.sqrt(2 * Math.PI));

/** Histogram as a density, with an optional normal curve and a comparison outline.
 *  o.primary / o.compare: {name, edges, counts, n, mean, sd, color}. */
export function histogramChart(o) {
  const W = o.w || WIDTH, h = o.height || 340, pad = { l: 24, r: 16, t: 40, b: 46 };
  const P = o.primary, C = o.compare;
  const dens = (S) => S.counts.map((c, i) => c / (S.n * (S.edges[i + 1] - S.edges[i])));
  const pd = dens(P), cd = C ? dens(C) : [];
  const xs = [...P.edges, ...(C ? C.edges : [])];
  let x0 = Math.min(...xs), x1 = Math.max(...xs);
  if (o.clip) { x0 = Math.max(x0, o.clip[0]); x1 = Math.min(x1, o.clip[1]); }
  const curve = [];
  if (o.normal) for (let i = 0; i <= 220; i++) { const xv = x0 + (x1 - x0) * i / 220; curve.push([xv, normPdf(xv, P.mean, P.sd)]); }
  let yMax = Math.max(...pd, ...cd, ...curve.map((c) => c[1])) * 1.06;
  const floor = yMax * 2e-4;
  const ty = o.logY ? (v) => Math.log10(Math.max(v, floor)) : (v) => v;
  const y0v = ty(o.logY ? floor : 0), y1v = ty(yMax);
  const x = lin(x0, x1, pad.l, W - pad.r), y = lin(y0v, y1v, h - pad.b, pad.t);
  let s = "";
  const ticks = niceTicks(x0, x1, 7).filter((t) => t >= x0 && t <= x1);
  for (const t of ticks) {
    s += `<line x1="${x(t)}" x2="${x(t)}" y1="${pad.t}" y2="${h - pad.b}" stroke="var(--grid)"/>`;
    s += `<text x="${x(t)}" y="${h - pad.b + 18}" text-anchor="middle" class="num">${esc(o.fmtX(t))}</text>`;
  }
  s += `<line x1="${pad.l}" x2="${W - pad.r}" y1="${h - pad.b}" y2="${h - pad.b}" stroke="var(--axis)"/>`;
  s += `<text x="${(pad.l + W - pad.r) / 2}" y="${h - 6}" text-anchor="middle">${esc(o.xLabel || "")}</text>`;
  s += `<text x="${pad.l}" y="14">${o.logY ? "Relative frequency (log scale)" : "Relative frequency"}</text>`;
  P.counts.forEach((c, i) => {
    const a = P.edges[i], b = P.edges[i + 1];
    if (b < x0 || a > x1) return;
    const xa = x(Math.max(a, x0)), xb = x(Math.min(b, x1));
    const top = y(ty(pd[i])), base = h - pad.b;
    const share = c / P.n;
    const expShare = normCdf(b, P.mean, P.sd) - normCdf(a, P.mean, P.sd);
    const tip = `<b>${esc(o.fmtTip(a))} to ${esc(o.fmtTip(b))}</b><br>${c.toLocaleString("en-CA")} ${esc(o.unitWord || "observations")} (${(share * 100).toFixed(share < 0.001 ? 3 : 2)}%)<br>A normal curve would put ${(expShare * 100).toFixed(expShare < 0.001 ? 3 : 2)}% here`;
    if (c > 0) s += `<rect x="${xa + 0.5}" y="${top}" width="${Math.max(xb - xa - 1, 0.6)}" height="${Math.max(base - top, 0)}" fill="${P.color}" opacity="0.8" data-tip="${esc(tip)}"/>`;
    else s += `<rect x="${xa}" y="${pad.t}" width="${Math.max(xb - xa, 0.6)}" height="${base - pad.t}" fill="transparent" data-tip="${esc(tip)}"/>`;
  });
  if (C) {
    let pts = [];
    C.counts.forEach((c, i) => {
      const a = Math.max(C.edges[i], x0), b = Math.min(C.edges[i + 1], x1);
      if (b <= a) return;
      const yy = y(ty(cd[i]));
      pts.push(`${x(a)},${yy}`, `${x(b)},${yy}`);
    });
    s += `<polyline points="${pts.join(" ")}" fill="none" stroke="${C.color}" stroke-width="2" stroke-linejoin="round"/>`;
  }
  if (o.normal) s += `<polyline points="${curve.map(([xv, d]) => `${x(xv)},${y(ty(d))}`).join(" ")}" fill="none" stroke="var(--ink)" stroke-width="1.5" stroke-dasharray="5 4"/>`;
  const mark = (v, label, right) => {
    if (v < x0 || v > x1) return;
    s += `<line x1="${x(v)}" x2="${x(v)}" y1="${pad.t - 14}" y2="${h - pad.b}" stroke="var(--ink-2)" stroke-width="1"/>`;
    s += `<text x="${x(v) + (right ? 5 : -5)}" y="${pad.t - 6}" text-anchor="${right ? "start" : "end"}" class="ink2">${esc(label)}</text>`;
  };
  // put the larger of mean and median on the right so the two labels never collide
  mark(P.mean, "mean", P.mean >= P.median);
  mark(P.median, "median", P.median > P.mean);
  const items = [{ name: P.name, color: P.color, kind: "box" }];
  if (C) items.push({ name: C.name, color: C.color });
  if (o.normal) items.push({ name: "Normal curve with the same mean and stdev", color: "var(--ink)" });
  return `${legend(items)}<div class="chart"><svg viewBox="0 0 ${W} ${h}" role="img" aria-label="Distribution histogram">${s}</svg></div>`;
}

/** Normal Q-Q plot: sample quantiles against the quantiles of a fitted normal. */
export function qqChart(o) {
  const W = o.w || WIDTH, h = o.height || 300, pad = { l: 64, r: 16, t: 18, b: 46 };
  const all = o.series.flatMap((s) => [...s.normal, ...s.empirical]);
  const ticks = coverTicks(Math.min(...all), Math.max(...all), 5);
  const lo = ticks[0], hi = ticks[ticks.length - 1];
  const x = lin(lo, hi, pad.l, W - pad.r), y = lin(lo, hi, h - pad.b, pad.t);
  let s = frame({ W, x, y, xTicks: ticks, yTicks: ticks, xFmt: o.fmt, yFmt: o.fmt, h, pad, xLabel: "What a normal distribution predicts", yLabel: "What the data show" });
  s += `<line x1="${x(lo)}" y1="${y(lo)}" x2="${x(hi)}" y2="${y(hi)}" stroke="var(--ink-3)" stroke-width="1"/>`;
  for (const se of o.series) {
    se.p.forEach((p, i) => {
      s += `<circle cx="${x(se.normal[i])}" cy="${y(se.empirical[i])}" r="3.2" fill="${se.color}" stroke="var(--surface)" stroke-width="1.5"
        data-tip="${esc(`<b>${se.name}</b><br>${(p * 100).toFixed(1)}th percentile<br>Data: ${o.fmt(se.empirical[i])}<br>Normal: ${o.fmt(se.normal[i])}`)}"/>`;
    });
  }
  return `${legend([...o.series.map((se) => ({ name: se.name, color: se.color, kind: "dot" })), { name: "On this line = normal", color: "var(--ink-3)" }])}
    <div class="chart"><svg viewBox="0 0 ${W} ${h}" role="img" aria-label="Normal Q-Q plot">${s}</svg></div>`;
}

/** Small fan chart with no axes, for previews: outer band, inner band, median line. */
export function miniFan(o) {
  const w = 320, h = o.height || 120, pad = 6;
  const xs = o.x;
  const hiMax = Math.max(...o.hi);
  const x = lin(xs[0], xs[xs.length - 1], pad, w - pad);
  const y = lin(0, hiMax * 1.02, h - pad, pad);
  const poly = (lo, hi) => `${xs.map((xv, i) => `${x(xv)},${y(hi[i])}`).join(" ")} ${xs.map((xv, i) => `${x(xv)},${y(lo[i])}`).reverse().join(" ")}`;
  let s = `<line x1="${pad}" x2="${w - pad}" y1="${h - pad}" y2="${h - pad}" stroke="var(--axis)" stroke-width="1"/>`;
  s += `<polygon points="${poly(o.lo, o.hi)}" fill="var(--seq-3)" opacity="0.16"/>`;
  s += `<polygon points="${poly(o.lo2, o.hi2)}" fill="var(--seq-4)" opacity="0.26"/>`;
  s += `<polyline points="${xs.map((xv, i) => `${x(xv)},${y(o.mid[i])}`).join(" ")}" fill="none" stroke="var(--s1)" stroke-width="2" stroke-linejoin="round"/>`;
  if (o.marker != null) s += `<line x1="${x(o.marker)}" x2="${x(o.marker)}" y1="${pad}" y2="${h - pad}" stroke="var(--axis)" stroke-width="1"/>`;
  return `<div class="chart"><svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(o.title || "projection preview")}">${s}</svg></div>`;
}

export function bindTooltips() {
  const tip = document.getElementById("tip");
  const place = (e) => {
    const pad = 14;
    let left = e.clientX + pad, top = e.clientY + pad;
    const r = tip.getBoundingClientRect();
    if (left + r.width > window.innerWidth - 8) left = e.clientX - r.width - pad;
    if (top + r.height > window.innerHeight - 8) top = e.clientY - r.height - pad;
    tip.style.left = left + "px"; tip.style.top = top + "px";
  };
  document.addEventListener("pointermove", (e) => {
    const el = e.target.closest ? e.target.closest("[data-tip],[data-chart]") : null;
    document.querySelectorAll("line[id$='-x']").forEach((l) => { if (!el || l.id !== el.dataset.chart + "-x") l.setAttribute("visibility", "hidden"); });
    if (!el) { tip.style.display = "none"; return; }
    if (el.dataset.tip) {
      tip.innerHTML = el.dataset.tip; tip.style.display = "block"; place(e); return;
    }
    const spec = registry.get(el.dataset.chart);
    if (!spec || spec.type !== "line") return;
    const svg = el.ownerSVGElement;
    const pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
    const loc = pt.matrixTransform(svg.getScreenCTM().inverse());
    let best = 0, bd = Infinity;
    spec.xs.forEach((xv, i) => { const d = Math.abs(spec.x(xv) - loc.x); if (d < bd) { bd = d; best = i; } });
    const xl = document.getElementById(el.dataset.chart + "-x");
    if (xl) { xl.setAttribute("x1", spec.x(spec.xs[best])); xl.setAttribute("x2", spec.x(spec.xs[best])); xl.setAttribute("visibility", "visible"); }
    const o = spec.o;
    const rows = [];
    for (const b of o.bands || []) if (b.name) rows.push(`<span class="k" style="background:${b.color};opacity:.5"></span>${esc(b.name)}: ${esc(o.tipFmt(b.lo[best]))} to ${esc(o.tipFmt(b.hi[best]))}`);
    for (const se of o.series) if (se.values[best] != null) rows.push(`<span class="k" style="background:${se.color}"></span>${esc(se.name)}: <b>${esc(o.tipFmt(se.values[best]))}</b>`);
    tip.innerHTML = `<b>${esc((o.xTipFmt || o.xFmt || String)(spec.xs[best]))}</b><br>${rows.join("<br>")}`;
    tip.style.display = "block"; place(e);
  });
  document.addEventListener("pointerleave", () => { tip.style.display = "none"; });
  window.addEventListener("scroll", () => { tip.style.display = "none"; }, { passive: true });
}
