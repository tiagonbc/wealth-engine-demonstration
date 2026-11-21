"""Standard risk metrics for the model portfolios.

Two sources, both simulated from the mock capital market assumptions:
- 500 synthetic 25-year monthly histories, rebalanced monthly, after fees:
  return, volatility, Sharpe, Sortino, maximum drawdown, Calmar (medians).
- 50,000 one-year outcomes: 95% value at risk, 95% conditional value at risk
  (expected shortfall) and the chance of a losing year.
"""
from __future__ import annotations

import numpy as np

from . import data
from .backtest import simulate_monthly
from .simulate import draw_asset_returns


def risk_report(weights_by_profile: dict, n_hist: int = 500, years: int = 25,
                n_annual: int = 50000, seed: int = 314) -> list[dict]:
    months = years * 12
    rets = simulate_monthly(n_hist, months, seed)
    annual = draw_asset_returns(np.random.default_rng(seed + 1), n_annual, 1)[:, 0, :]
    fee_m = (1 + data.PLATFORM_FEE) ** (1 / 12) - 1
    rf_m = (1 + data.RISK_FREE) ** (1 / 12) - 1
    rows = []
    for pid, weights in weights_by_profile.items():
        w = np.array([weights[c] for c in data.CODES])
        pm = rets @ w - fee_m                                    # (hist, months)
        values = np.cumprod(1 + pm, axis=1)
        cagr = values[:, -1] ** (1 / years) - 1
        sd = pm.std(axis=1, ddof=1)
        excess = pm - rf_m
        sharpe = excess.mean(axis=1) / sd * np.sqrt(12)
        downside = np.sqrt(np.mean(np.minimum(excess, 0.0) ** 2, axis=1))
        sortino = excess.mean(axis=1) / downside * np.sqrt(12)
        curve = np.concatenate([np.ones((n_hist, 1)), values], axis=1)
        mdd = (curve / np.maximum.accumulate(curve, axis=1) - 1).min(axis=1)
        calmar = cagr / np.abs(mdd)
        ra = annual @ w - data.PLATFORM_FEE
        p5 = np.percentile(ra, 5)
        rows.append({
            "id": pid,
            "cagr": float(np.median(cagr)),
            "volatility": float(np.median(sd) * np.sqrt(12)),
            "sharpe": float(np.median(sharpe)),
            "sortino": float(np.median(sortino)),
            "max_drawdown": float(np.median(mdd)),
            "worst_drawdown_p5": float(np.percentile(mdd, 5)),
            "calmar": float(np.median(calmar)),
            "var95_1y": float(-p5),
            "cvar95_1y": float(-ra[ra <= p5].mean()),
            "prob_losing_year": float((ra < 0).mean()),
        })
    return rows
