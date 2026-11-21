"""Backtest of rebalancing policies on synthetic monthly histories.

Every policy sees the same simulated histories, so differences come from the
policy alone. Results are medians across histories; the reference portfolio
is rebalanced every month at no cost, so tracking error measures how far each
policy lets the account wander from its model.
"""
from __future__ import annotations

import numpy as np

from . import data
from .rebalance import BAND_ABS, BAND_REL

POLICIES = [
    {"id": "none", "name": "Never rebalance"},
    {"id": "annual", "name": "Calendar, yearly"},
    {"id": "quarterly", "name": "Calendar, quarterly"},
    {"id": "bands", "name": "5/25 tolerance bands, checked monthly"},
]


def simulate_monthly(n_hist: int, months: int, seed: int = 99):
    rng = np.random.default_rng(seed)
    mu_m = (1 + data.MU) ** (1 / 12) - 1
    sig_m = data.SIGMA / np.sqrt(12)
    s2 = np.log1p((sig_m / (1 + mu_m)) ** 2)
    m = np.log1p(mu_m) - 0.5 * s2
    z = rng.standard_normal((n_hist, months, len(mu_m))) @ np.linalg.cholesky(data.CORR).T
    return np.expm1(m + np.sqrt(s2) * z)


def run_policy(returns: np.ndarray, target: np.ndarray, policy: str, cost_bps: float = 10.0):
    """Vectorized across histories. returns: (hist, months, assets)."""
    n_hist, months, _ = returns.shape
    bands = np.minimum(BAND_ABS, BAND_REL * target)
    h = np.tile(target, (n_hist, 1))
    values = np.ones((n_hist, months + 1))
    port_ret = np.empty((n_hist, months))
    turnover = np.zeros(n_hist)
    n_reb = np.zeros(n_hist)
    max_drift = np.zeros((n_hist, months))
    for t in range(months):
        start = h.sum(axis=1)
        h = h * (1 + returns[:, t, :])
        v = h.sum(axis=1)
        w = h / v[:, None]
        port_ret[:, t] = v / start - 1
        drift = np.abs(w - target)
        max_drift[:, t] = drift.max(axis=1)
        if policy == "none":
            do = np.zeros(n_hist, bool)
        elif policy == "annual":
            do = np.full(n_hist, t % 12 == 11)
        elif policy == "quarterly":
            do = np.full(n_hist, t % 3 == 2)
        elif policy == "bands":
            do = (drift > bands).any(axis=1)
        elif policy == "monthly":
            do = np.ones(n_hist, bool)
        else:
            raise ValueError(policy)
        if do.any():
            one_way = 0.5 * drift.sum(axis=1)
            cost = 2 * one_way * cost_bps / 1e4
            v_new = np.where(do, v * (1 - cost), v)
            h = np.where(do[:, None], target[None, :] * v_new[:, None], h)
            turnover += np.where(do, one_way, 0)
            n_reb += do
            port_ret[:, t] = np.where(do, v_new / start - 1, port_ret[:, t])
            v = v_new
        values[:, t + 1] = h.sum(axis=1)
    return {"values": values, "returns": port_ret, "turnover": turnover, "rebalances": n_reb, "max_drift": max_drift}


def compare_policies(profile_id: str = "balanced", weights=None, n_hist: int = 500, years: int = 25,
                     seed: int = 99, cost_bps: float = 10.0):
    months = years * 12
    target = np.array([weights[c] for c in data.CODES])
    rets = simulate_monthly(n_hist, months, seed)
    ref = run_policy(rets, target, "monthly", cost_bps=0.0)
    out = []
    sample = {}
    for p in POLICIES:
        r = run_policy(rets, target, p["id"], cost_bps)
        yrs = months / 12
        cagr = (r["values"][:, -1]) ** (1 / yrs) - 1
        vol = r["returns"].std(axis=1, ddof=1) * np.sqrt(12)
        peaks = np.maximum.accumulate(r["values"], axis=1)
        mdd = (r["values"] / peaks - 1).min(axis=1)
        te = (r["returns"] - ref["returns"]).std(axis=1, ddof=1) * np.sqrt(12)
        out.append({
            **p,
            "cagr": float(np.median(cagr)), "volatility": float(np.median(vol)),
            "max_drawdown": float(np.median(mdd)), "tracking_error": float(np.median(te)),
            "turnover_per_year": float(np.median(r["turnover"] / yrs)),
            "rebalances_per_year": float(np.median(r["rebalances"] / yrs)),
            "avg_max_drift": float(np.median(r["max_drift"].mean(axis=1))),
            "worst_drift": float(np.median(r["max_drift"].max(axis=1))),
            "p95_tracking_error": float(np.percentile(te, 95)),
        })
        # equity share path for the first history, for the drift chart
        eq_idx = [data.CODES.index(c) for c in data.CODES if data.GROUPS[c] == "Equity"]
        sample[p["id"]] = _equity_path(rets[0], target, p["id"], eq_idx)
    return {"profile": profile_id, "n_histories": n_hist, "years": years, "cost_bps": cost_bps,
            "policies": out, "sample_equity_share": sample,
            "target_equity_share": float(target[[data.CODES.index(c) for c in data.CODES if data.GROUPS[c] == "Equity"]].sum())}


def _equity_path(returns_one: np.ndarray, target: np.ndarray, policy: str, eq_idx):
    bands = np.minimum(BAND_ABS, BAND_REL * target)
    h = target.copy()
    path = []
    for t in range(returns_one.shape[0]):
        h = h * (1 + returns_one[t])
        w = h / h.sum()
        path.append(round(float(w[eq_idx].sum()), 5))
        drift = np.abs(w - target)
        do = (policy == "annual" and t % 12 == 11) or (policy == "quarterly" and t % 3 == 2) or \
             (policy == "bands" and (drift > bands).any())
        if do:
            h = target * h.sum()
    return path
