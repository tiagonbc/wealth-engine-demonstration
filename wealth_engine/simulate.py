"""Monte Carlo goal planning.

Plans are projected in today's dollars, one year at a time. Each path draws
correlated lognormal returns for every asset class, the portfolio is
rebalanced to its model weights once a year, the platform fee is deducted and
inflation is removed. Contributions go in at the start of each working year;
retirement withdrawals (spending need minus other income) come out at the
start of each retired year. A plan succeeds if the money lasts to the
planning age.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import data


@dataclass
class Plan:
    age: int
    retirement_age: int
    plan_to_age: int
    investable: float
    monthly_contribution: float
    retirement_spending: float
    retirement_other_income: float
    inflation: float = data.INFLATION
    fee: float = data.PLATFORM_FEE

    @property
    def years(self) -> int:
        return self.plan_to_age - self.age

    @classmethod
    def from_household(cls, h: dict, **overrides) -> "Plan":
        fields = dict(
            age=h["age"], retirement_age=h["retirement_age"], plan_to_age=h["plan_to_age"],
            investable=data.total_investable(h), monthly_contribution=h["monthly_contribution"],
            retirement_spending=h["retirement_spending"],
            retirement_other_income=h["retirement_other_income"],
        )
        fields.update(overrides)
        return cls(**fields)


def lognormal_params(mu, sigma):
    """Log-space mean and sd that reproduce an arithmetic mean and volatility."""
    mu = np.asarray(mu, float)
    sigma = np.asarray(sigma, float)
    s2 = np.log1p((sigma / (1 + mu)) ** 2)
    return np.log1p(mu) - 0.5 * s2, np.sqrt(s2)


def draw_asset_returns(rng, n_paths, n_years, mu=None, sigma=None, corr=None,
                       tails: str = "normal", df: int = 5, equity_shift: float = 0.0):
    """Correlated annual asset returns, shape (paths, years, assets)."""
    mu = (data.MU if mu is None else np.asarray(mu, float)).copy()
    sigma = data.SIGMA if sigma is None else np.asarray(sigma, float)
    corr = data.CORR if corr is None else corr
    if equity_shift:
        eq = np.array([data.GROUPS[c] in ("Equity", "Real assets") for c in data.CODES])
        mu[eq] += equity_shift
    m, s = lognormal_params(mu, sigma)
    z = rng.standard_normal((n_paths, n_years, len(mu)))
    if tails == "t":
        # multivariate Student t with unit variance: fatter tails, same volatility
        g = rng.chisquare(df, size=(n_paths, n_years, 1)) / df
        z = z / np.sqrt(g) * np.sqrt((df - 2) / df)
    z = z @ np.linalg.cholesky(corr).T
    return np.expm1(m + s * z)


def real_portfolio_returns(asset_returns, weights, inflation, fee):
    nominal = asset_returns @ weights
    return (1 + nominal - fee) / (1 + inflation) - 1


def project(plan: Plan, real_returns: np.ndarray, spending=None, contribution=None,
            retirement_age=None, shock_first_retired_year: float = 0.0):
    """Run every path. Returns (wealth by year incl. start, depletion age or nan)."""
    spending = plan.retirement_spending if spending is None else spending
    contribution = plan.monthly_contribution if contribution is None else contribution
    retirement_age = plan.retirement_age if retirement_age is None else retirement_age
    n_paths, n_years = real_returns.shape
    w = np.full(n_paths, float(plan.investable))
    out = np.empty((n_paths, n_years + 1))
    out[:, 0] = w
    depleted_at = np.full(n_paths, np.nan)
    draw = max(spending - plan.retirement_other_income, 0.0)
    for t in range(n_years):
        age = plan.age + t
        r = real_returns[:, t]
        if age < retirement_age:
            w = (w + 12 * contribution) * (1 + r)
        else:
            if shock_first_retired_year and age == max(retirement_age, plan.age):
                r = np.minimum(r, shock_first_retired_year)
            w = w - draw
            newly = (w <= 0) & np.isnan(depleted_at)
            depleted_at[newly] = age
            w = np.where(w > 0, w * (1 + r), 0.0)
        out[:, t + 1] = w
    return out, depleted_at


PERCENTILES = [5, 10, 25, 50, 75, 90, 95]


def simulate_plan(plan: Plan, weights: np.ndarray, n_paths: int = 10000, seed: int = 2026,
                  tails: str = "normal", equity_shift: float = 0.0, inflation=None,
                  shock_first_retired_year: float = 0.0, with_spending_solve: bool = True):
    rng = np.random.default_rng(seed)
    assets = draw_asset_returns(rng, n_paths, plan.years, tails=tails, equity_shift=equity_shift)
    infl = plan.inflation if inflation is None else inflation
    real = real_portfolio_returns(assets, weights, infl, plan.fee)
    wealth, depleted = project(plan, real, shock_first_retired_year=shock_first_retired_year)
    success = np.isnan(depleted)
    p = float(success.mean())
    ages = list(range(plan.age, plan.plan_to_age + 1))
    pct = np.percentile(wealth, PERCENTILES, axis=0)
    ret_idx = max(plan.retirement_age - plan.age, 0)
    result = {
        "probability_of_success": p,
        "standard_error": float(np.sqrt(p * (1 - p) / n_paths)),
        "n_paths": n_paths, "seed": seed,
        "ages": ages,
        "percentiles": {str(q): pct[i].round(0).tolist() for i, q in enumerate(PERCENTILES)},
        "median_at_retirement": float(np.median(wealth[:, ret_idx])),
        "median_at_end": float(np.median(wealth[:, -1])),
        "p10_at_end": float(np.percentile(wealth[:, -1], 10)),
        "median_depletion_age": float(np.nanmedian(depleted)) if (~success).any() else None,
        "probability_one_year_loss": float((real[:, 0] < 0).mean()),
        "annual_draw": max(plan.retirement_spending - plan.retirement_other_income, 0.0),
    }
    if with_spending_solve:
        result["spending_at_90"] = solve_spending(plan, real, 0.90)
    return result, real


def solve_spending(plan: Plan, real_returns: np.ndarray, target: float = 0.90) -> float:
    """Highest real retirement spending that keeps the success rate at `target`
    (same random paths for every trial, so the answer is monotone and stable)."""
    lo = plan.retirement_other_income
    hi = max(plan.retirement_spending * 3, lo + 1000)
    for _ in range(40):
        mid = (lo + hi) / 2
        _, dep = project(plan, real_returns, spending=mid)
        if np.isnan(dep).mean() >= target:
            lo = mid
        else:
            hi = mid
    return round(lo, -2)


def what_if_grid(plan: Plan, real_returns: np.ndarray, retired: bool, weights_by_profile=None,
                 seed: int = 2026):
    """Probability of success across two levers, on common random numbers."""
    if not retired:
        rows = [0, 250, 500, 1000]
        cols = [plan.retirement_age - 2, plan.retirement_age, plan.retirement_age + 2, plan.retirement_age + 4]
        cells = []
        for extra in rows:
            row = []
            for ra in cols:
                _, dep = project(plan, real_returns, contribution=plan.monthly_contribution + extra, retirement_age=ra)
                row.append(float(np.isnan(dep).mean()))
            cells.append(row)
        return {"row_label": "Extra monthly saving", "rows": ["+$%d" % r for r in rows],
                "col_label": "Retirement age", "cols": [str(c) for c in cols], "cells": cells}
    # retired: spending change x risk profile
    rows = [-0.10, -0.05, 0.0, 0.05]
    rng = np.random.default_rng(seed)
    assets = draw_asset_returns(rng, real_returns.shape[0], plan.years)
    cells = []
    profiles = list(weights_by_profile.items())
    for chg in rows:
        row = []
        for _, w in profiles:
            real = real_portfolio_returns(assets, w, plan.inflation, plan.fee)
            _, dep = project(plan, real, spending=plan.retirement_spending * (1 + chg))
            row.append(float(np.isnan(dep).mean()))
        cells.append(row)
    return {"row_label": "Change in spending", "rows": ["%+d%%" % round(r * 100) for r in rows],
            "col_label": "Model portfolio", "cols": [data.PROFILE_BY_ID[k]["name"] for k, _ in profiles],
            "cells": cells}


def probability_below_start(weights: np.ndarray, horizons=(1, 3, 5, 10), n_paths: int = 20000, seed: int = 11):
    """Chance a lump sum is worth less (in nominal dollars, after fees) than it
    started after each horizon: the number advisors use to explain risk."""
    rng = np.random.default_rng(seed)
    assets = draw_asset_returns(rng, n_paths, max(horizons))
    r = assets @ weights - data.PLATFORM_FEE
    growth = np.cumprod(1 + r, axis=1)
    return {str(h): float((growth[:, h - 1] < 1).mean()) for h in horizons}
