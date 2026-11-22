"""Build the demonstration site's data from the engine.

    python build_site.py            # full build (about a minute)
    python build_site.py --fast     # fewer paths and histories, for quick checks

Writes docs/data/engine.json, which the static site in docs/ reads. Every
number on the site comes from this file, and every number in this file comes
from the engine running on mock data.
"""
from __future__ import annotations

import json
import platform
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from api.app import create_app
from wealth_engine import __version__, backtest, data, health, market, optimize, rebalance, risk, simulate, stats, validation
from wealth_engine.metrics import portfolio_stats, risk_contributions

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs" / "data" / "engine.json"


def _round(x, nd=6):
    if isinstance(x, float):
        return float(f"{x:.{nd}g}") if np.isfinite(x) else None
    if isinstance(x, (np.floating,)):
        return _round(float(x), nd)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, dict):
        return {k: _round(v, nd) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_round(v, nd) for v in x]
    if isinstance(x, np.ndarray):
        return _round(x.tolist(), nd)
    return x


def run_tests():
    t = time.perf_counter()
    proc = subprocess.run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider"],
                          cwd=ROOT, capture_output=True, text=True)
    out = proc.stdout + proc.stderr
    m = re.search(r"(\d+) passed", out)
    f = re.search(r"(\d+) failed", out)
    col = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-p", "no:cacheprovider"],
                         cwd=ROOT, capture_output=True, text=True).stdout
    per_file = {}
    for line in col.splitlines():
        if "::" in line:
            fname = line.split("::")[0].replace("tests/", "").replace("tests\\", "")
            per_file[fname] = per_file.get(fname, 0) + 1
    return {"passed": int(m.group(1)) if m else 0, "failed": int(f.group(1)) if f else 0,
            "seconds": round(time.perf_counter() - t, 1), "per_file": per_file}


def api_samples_and_latency(accounts):
    app = create_app()
    app.config.update(TESTING=True)
    c = app.test_client()
    h2 = {k: v for k, v in data.HOUSEHOLD_BY_ID["H2"].items() if k not in ("id", "name")}
    h2["retirement_probability"] = 0.73
    a2 = next(a for a in accounts if a["id"] == "A2")
    a2_payload = {k: a2[k] for k in ("id", "type", "cash", "cash_flow", "holdings", "acb", "restrictions", "risk_profile")}
    plan_body = {"age": 40, "retirement_age": 65, "investable": 150000, "monthly_contribution": 1200,
                 "retirement_spending": 60000, "retirement_other_income": 20000, "risk_profile": "growth",
                 "paths": 5000, "seed": 7}
    calls = [
        ("GET", "/api/v1/status", None, "Service status and data checks"),
        ("GET", "/api/v1/model-portfolios", None, "The five model portfolios"),
        ("POST", "/api/v1/portfolios/optimize", {"risk_profile": "balanced"}, "Optimize for a risk profile"),
        ("POST", "/api/v1/plans/simulate", plan_body, "Monte Carlo plan, 5,000 paths"),
        ("POST", "/api/v1/health-score", h2, "Financial health score"),
        ("POST", "/api/v1/accounts/rebalance", a2_payload, "Rebalance with pre-trade checks"),
        ("POST", "/api/v1/plans/simulate", dict(plan_body, paths=1000000), "Rejected: too many paths"),
    ]
    samples, latency = [], []
    for method, path, body, label in calls:
        times = []
        n = 25 if "simulate" in path or "health" in path else 40
        resp = None
        for _ in range(n):
            t = time.perf_counter()
            resp = c.open(path, method=method, json=body)
            times.append((time.perf_counter() - t) * 1000)
        js = resp.get_json()
        if path.endswith("simulate") and resp.status_code == 200:
            js = {k: v for k, v in js.items() if k not in ("percentiles", "ages")}
            js["percentiles"] = "(by age: 5th to 95th; trimmed here)"
        if path.endswith("model-portfolios"):
            js = {"portfolios": [{k: p[k] for k in ("id", "name", "target_vol", "expected_return", "volatility", "sharpe")}
                                 for p in js["portfolios"]], "note": "(weights and risk contributions trimmed here)"}
        if path.endswith("rebalance"):
            js = {k: js[k] for k in ("account", "trigger", "breaches", "status", "turnover", "max_post_drift")} | {
                "orders": [{k: o[k] for k in ("side", "code", "units", "price", "value", "status")} for o in js["orders"]]}
        if path.endswith("health-score"):
            js = {k: js[k] for k in ("score", "band", "next_best_actions")}
        samples.append({"method": method, "path": path, "label": label, "request": body if path.endswith(("optimize", "simulate")) else (
            "(household H2 profile)" if path.endswith("health-score") else ("(account A2 holdings)" if path.endswith("rebalance") else None)),
            "status": resp.status_code, "response": js})
        times.sort()
        latency.append({"endpoint": "%s %s" % (method, path), "label": label, "calls": n,
                        "p50_ms": times[len(times) // 2], "p95_ms": times[int(len(times) * 0.95) - 1]})
    return samples, latency


def distributions(Wn: dict, terminal_wealth: dict, n_hist: int = 500, years: int = 25) -> dict:
    """Every series the Statistics page can show, each with stats per frequency."""
    series = []
    spy = market.spy_returns()
    if spy is not None:
        series.append({
            "id": "spy", "name": "SPY (S&P 500 ETF), total return", "group": "Market data (real)", "unit": "return",
            "source": "Norgate Data, dividends reinvested, %s to %s" % (spy["start"], spy["end"]),
            "freqs": {
                "daily": {**stats.describe(spy["daily"], periods_per_year=252, bins=80), "span": "%s to %s" % (spy["start"], spy["end"])},
                "monthly": {**stats.describe(spy["monthly"], periods_per_year=12, bins=40), "span": spy["monthly_span"]},
                "annual": {**stats.describe(spy["annual"], periods_per_year=1, bins=12), "span": spy["annual_span"]},
            },
        })
    rets = backtest.simulate_monthly(n_hist, years * 12, seed=777)
    fee_m = (1 + data.PLATFORM_FEE) ** (1 / 12) - 1
    for p in data.RISK_PROFILES:
        m = rets @ Wn[p["id"]] - fee_m                       # (hist, months)
        a = np.prod(1 + m.reshape(n_hist, years, 12), axis=2) - 1
        series.append({
            "id": "mp_" + p["id"], "name": p["name"] + " model portfolio", "group": "Model portfolios (simulated)",
            "unit": "return", "source": "%d simulated %d-year histories from the mock assumptions, after fees" % (n_hist, years),
            "freqs": {
                "monthly": {**stats.describe(m.ravel(), periods_per_year=12, bins=40, time_series=False), "span": "pooled simulated months"},
                "annual": {**stats.describe(a.ravel(), periods_per_year=1, bins=30, time_series=False), "span": "pooled simulated years"},
            },
        })
    for i, (code, name, *_rest) in enumerate(data.ASSET_CLASSES):
        series.append({
            "id": "ac_" + code, "name": name, "group": "Asset classes (simulated)", "unit": "return",
            "source": "%d simulated %d-year histories from the mock assumptions" % (n_hist, years),
            "freqs": {"monthly": {**stats.describe(rets[:, :, i].ravel(), periods_per_year=12, bins=40, time_series=False),
                                  "span": "pooled simulated months"}},
        })
    for h in data.HOUSEHOLDS:
        series.append({
            "id": "tw_" + h["id"], "name": "%s: wealth at %d" % (h["name"], h["plan_to_age"]), "group": "Client outcomes (Monte Carlo)",
            "unit": "money", "source": "Monte Carlo paths in today's dollars; 0 means the money ran out",
            "freqs": {"outcome": {**stats.describe(terminal_wealth[h["id"]], kind="money", bins=40, time_series=False, hist_upper_pct=99),
                                  "span": "%s simulated paths" % format(len(terminal_wealth[h["id"]]), ",")}},
        })
    return {"normal_beyond_3sd": stats.NORMAL_BEYOND_3SD, "series": series}


def main(fast: bool = False):
    t0 = time.perf_counter()
    paths = 4000 if fast else 10000
    mps = optimize.model_portfolios()
    W = {p["id"]: p["weights"] for p in mps}
    Wn = {k: np.array([v[c] for c in data.CODES]) for k, v in W.items()}

    # --- portfolios
    frontier = optimize.efficient_frontier(30)
    rp_risky = optimize.risk_parity()
    rp = np.concatenate([[0.0], rp_risky])
    rp_stats = portfolio_stats(rp, data.MU, data.COV, data.RISK_FREE)
    ws = optimize.resampled_weights(0.085, n_resamples=60 if fast else 200)
    resampling = [{"asset": c, "base": W["balanced"][c], "mean": float(ws[:, i].mean()),
                   "p5": float(np.percentile(ws[:, i], 5)), "p95": float(np.percentile(ws[:, i], 95))}
                  for i, c in enumerate(data.CODES)]
    sensitivity = optimize.input_sensitivity("balanced")
    below_start = {p["id"]: simulate.probability_below_start(Wn[p["id"]]) for p in mps}
    risk_rows = risk.risk_report(W, n_hist=150 if fast else 500)

    # --- households
    households = []
    terminal_wealth = {}
    grid_profiles = {k: Wn[k] for k in ("conservative", "moderately_conservative", "balanced", "growth")}
    for h in data.HOUSEHOLDS:
        plan = simulate.Plan.from_household(h)
        res, real = simulate.simulate_plan(plan, Wn[h["risk_profile"]], n_paths=paths)
        grid = simulate.what_if_grid(plan, real, h["retired"], weights_by_profile=grid_profiles)
        hs = health.score_household(h, res["probability_of_success"])
        households.append({"profile": h, "investable_total": data.total_investable(h), "plan": res,
                           "what_if": grid, "health": hs})
        terminal_wealth[h["id"]] = simulate.project(plan, real)[0][:, -1]

    # --- accounts
    accounts = data.build_accounts(W)
    rebalances = [{"account": a, "result": rebalance.plan_rebalance(a, W[a["risk_profile"]])} for a in accounts]

    # --- backtest and validation
    bt = backtest.compare_policies("balanced", W["balanced"], n_hist=150 if fast else 500, years=25)
    h3 = simulate.Plan.from_household(data.HOUSEHOLD_BY_ID["H3"])
    conv = validation.convergence(h3, Wn["balanced"], n_seeds=6 if fast else 12)
    calib = validation.calibration(W, n_plans=400 if fast else 1500, n_paths=400 if fast else 1000)
    stress = validation.stress_tests(h3, Wn["balanced"], n_paths=paths)

    dists = distributions(Wn, terminal_wealth, n_hist=150 if fast else 500)

    samples, latency = api_samples_and_latency(accounts)
    tests = run_tests()

    payload = {
        "meta": {
            "title": "Wealth Engine Demonstration", "version": __version__,
            "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "as_of": data.AS_OF.isoformat(), "python": platform.python_version(),
            "numpy": np.__version__, "paths_per_plan": paths, "fast_build": fast,
            "build_seconds": None,
        },
        "assumptions": {
            "asset_classes": [{"code": c, "name": n, "group": g, "expected_return": mu, "volatility": s,
                               "fund": data.FUNDS[c]["fund"], "price": data.FUNDS[c]["price"],
                               "price_date": data.FUNDS[c]["price_date"], "bounds": data.BOUNDS[c]}
                              for c, n, g, mu, s in data.ASSET_CLASSES],
            "correlation": data.CORR.tolist(), "inflation": data.INFLATION, "fee": data.PLATFORM_FEE,
            "risk_free": data.RISK_FREE, "group_caps": data.GROUP_CAPS,
        },
        "data_checks": data.validate_assumptions(),
        "model_portfolios": mps,
        "frontier": [{k: p[k] for k in ("expected_return", "volatility")} for p in frontier],
        "risk_parity": {"weights": dict(zip(data.CODES, rp.tolist())), **rp_stats,
                        "risk_contributions": dict(zip(data.CODES[1:], risk_contributions(rp_risky, data.COV[1:, 1:]).tolist()))},
        "resampling": {"profile": "balanced", "n": int(len(ws)), "rows": resampling},
        "sensitivity": sensitivity,
        "probability_below_start": below_start,
        "risk_metrics": risk_rows,
        "distributions": dists,
        "households": households,
        "rebalances": rebalances,
        "rebalance_policy": {"band_abs": rebalance.BAND_ABS, "band_rel": rebalance.BAND_REL,
                             "cash_buffer": rebalance.CASH_BUFFER, "min_order": rebalance.MIN_ORDER,
                             "min_trade_weight": rebalance.MIN_TRADE_WEIGHT,
                             "max_order_share": rebalance.MAX_ORDER_SHARE},
        "backtest": bt,
        "validation": {"convergence": conv, "calibration": calib, "stress": stress, "stress_household": "H3"},
        "model_inventory": data.MODEL_INVENTORY,
        "api": {"samples": samples, "latency": latency},
        "tests": tests,
    }
    payload["meta"]["build_seconds"] = round(time.perf_counter() - t0, 1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(_round(payload), separators=(",", ":")), encoding="utf-8")
    print("wrote %s (%.0f KB) in %.1fs; tests %d passed, %d failed" % (
        OUT.relative_to(ROOT), OUT.stat().st_size / 1024, payload["meta"]["build_seconds"], tests["passed"], tests["failed"]))


if __name__ == "__main__":
    main(fast="--fast" in sys.argv)
