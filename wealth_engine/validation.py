"""Model validation procedures for the Monte Carlo planner and the optimizer.

1. Convergence: how the success probability settles as paths increase.
2. Calibration: do plans the model calls "70% likely" succeed about 70% of
   the time? Tested three ways: when the world behaves like the model, when
   returns have fatter tails, and when expected returns turn out 1.5 points
   lower than assumed. Scored with the Brier score and a reliability table.
3. Stress tests on a household plan.
"""
from __future__ import annotations

import numpy as np

from . import data
from .simulate import Plan, draw_asset_returns, project, real_portfolio_returns


def convergence(plan: Plan, weights: np.ndarray, path_counts=(250, 500, 1000, 2500, 5000, 10000, 20000),
                n_seeds: int = 12):
    rows = []
    for n in path_counts:
        ps = []
        for s in range(n_seeds):
            rng = np.random.default_rng(1000 + s)
            assets = draw_asset_returns(rng, n, plan.years)
            real = real_portfolio_returns(assets, weights, plan.inflation, plan.fee)
            _, dep = project(plan, real)
            ps.append(np.isnan(dep).mean())
        ps = np.array(ps)
        p = ps.mean()
        rows.append({"paths": n, "mean": float(p), "sd_across_seeds": float(ps.std(ddof=1)),
                     "theoretical_se": float(np.sqrt(p * (1 - p) / n)),
                     "min": float(ps.min()), "max": float(ps.max())})
    return rows


def _portfolio_moments(weights):
    mu = float(weights @ data.MU)
    vol = float(np.sqrt(weights @ data.COV @ weights))
    return mu, vol


def _paths(rng, n, years, mu, vol, tails="normal", df=4):
    s2 = np.log1p((vol / (1 + mu)) ** 2)
    m = np.log1p(mu) - 0.5 * s2
    z = rng.standard_normal((n, years))
    if tails == "t":
        g = rng.chisquare(df, size=(n, years)) / df
        z = z / np.sqrt(g) * np.sqrt((df - 2) / df)
    nominal = np.expm1(m + np.sqrt(s2) * z)
    return (1 + nominal - data.PLATFORM_FEE) / (1 + data.INFLATION) - 1


def _random_plans(rng, n):
    plans = []
    profiles = [p["id"] for p in data.RISK_PROFILES]
    for _ in range(n):
        age = int(rng.integers(30, 70))
        retired = age >= 65 or rng.random() < 0.15
        ret_age = age if retired else int(rng.integers(max(age + 3, 58), 68))
        spend = float(rng.uniform(40000, 110000))
        other = float(rng.uniform(12000, 40000))
        draw = max(spend - other, 5000)
        # size savings so plans span the whole probability range
        coverage = float(rng.uniform(8, 32))
        investable = draw * coverage * (0.35 if not retired else 1.0)
        contrib = 0.0 if retired else float(rng.uniform(200, 3000))
        plans.append((Plan(age=age, retirement_age=ret_age, plan_to_age=95, investable=investable,
                           monthly_contribution=contrib, retirement_spending=spend,
                           retirement_other_income=other), profiles[int(rng.integers(0, len(profiles)))]))
    return plans


def calibration(model_weights: dict, n_plans: int = 1500, n_paths: int = 1000, seed: int = 404):
    """Predicted success probability vs realized outcome on one 'true' future per plan."""
    rng = np.random.default_rng(seed)
    plans = _random_plans(rng, n_plans)
    worlds = {
        "model": {"name": "World behaves like the model", "tails": "normal", "shift": 0.0},
        "fat_tails": {"name": "Fatter tails (Student t, 4 df)", "tails": "t", "shift": 0.0},
        "optimistic": {"name": "Returns 1.5 pts lower than assumed", "tails": "normal", "shift": -0.015},
    }
    preds = np.empty(n_plans)
    outcomes = {k: np.empty(n_plans) for k in worlds}
    for i, (plan, prof) in enumerate(plans):
        w = np.array([model_weights[prof][c] for c in data.CODES])
        mu, vol = _portfolio_moments(w)
        real = _paths(rng, n_paths, plan.years, mu, vol)
        _, dep = project(plan, real)
        preds[i] = np.isnan(dep).mean()
        for k, wd in worlds.items():
            eq_share = sum(w[data.CODES.index(c)] for c in data.CODES if data.GROUPS[c] in ("Equity", "Real assets"))
            truth = _paths(rng, 1, plan.years, mu + wd["shift"] * eq_share, vol, tails=wd["tails"])
            _, d1 = project(plan, truth)
            outcomes[k][i] = float(np.isnan(d1[0]))
    bins = np.linspace(0, 1, 11)
    result = {"n_plans": n_plans, "n_paths": n_paths, "worlds": []}
    for k, wd in worlds.items():
        y = outcomes[k]
        brier = float(np.mean((preds - y) ** 2))
        # Brier score a perfectly calibrated model would get on these predictions
        expected = float(np.mean(preds * (1 - preds)))
        table = []
        for lo, hi in zip(bins[:-1], bins[1:]):
            m = (preds >= lo) & ((preds < hi) | (hi == 1.0))
            if m.sum() >= 15:
                table.append({"bin": "%d-%d%%" % (lo * 100, hi * 100), "n": int(m.sum()),
                              "predicted": float(preds[m].mean()), "realized": float(y[m].mean())})
        result["worlds"].append({"id": k, "name": wd["name"], "brier": brier, "brier_if_calibrated": expected,
                                 "mean_predicted": float(preds.mean()), "mean_realized": float(y.mean()),
                                 "reliability": table})
    return result


def stress_tests(plan: Plan, weights: np.ndarray, n_paths: int = 10000, seed: int = 2026):
    from .simulate import simulate_plan
    cases = [
        ("Base case", {}),
        ("Fatter tails (Student t)", {"tails": "t"}),
        ("Equity returns 1.5 pts lower", {"equity_shift": -0.015}),
        ("Inflation at 3.5%", {"inflation": 0.035}),
        ("Bad first retirement year (-25%)", {"shock_first_retired_year": -0.25}),
    ]
    rows = []
    for name, kw in cases:
        r, _ = simulate_plan(plan, weights, n_paths=n_paths, seed=seed, with_spending_solve=False, **kw)
        rows.append({"case": name, "probability_of_success": r["probability_of_success"],
                     "median_at_end": r["median_at_end"]})
    return rows
