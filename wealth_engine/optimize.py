"""Portfolio construction: efficient frontier, model portfolios, risk parity and
a resampling test of how stable the optimized weights are."""
from __future__ import annotations

import numpy as np
from scipy.optimize import minimize

from . import data
from .metrics import portfolio_stats, risk_contributions


def _bounds_list(codes=None, bounds=None):
    codes = codes or data.CODES
    bounds = bounds or data.BOUNDS
    return [bounds[c] for c in codes]


def _group_constraints(codes=None, group_caps=None):
    codes = codes or data.CODES
    group_caps = data.GROUP_CAPS if group_caps is None else group_caps
    cons = []
    for g in group_caps:
        idx = np.array([codes.index(c) for c in g["codes"] if c in codes])
        cons.append({"type": "ineq", "fun": (lambda w, idx=idx, cap=g["max"]: cap - w[idx].sum())})
    return cons


def _start(bounds):
    lo = np.array([b[0] for b in bounds])
    hi = np.array([b[1] for b in bounds])
    x = lo + (hi - lo) * (1 - lo.sum()) / (hi - lo).sum()
    return x


def _feasible(w, bounds, constraints, tol=1e-6):
    lo = np.array([b[0] for b in bounds])
    hi = np.array([b[1] for b in bounds])
    if (w < lo - tol).any() or (w > hi + tol).any():
        return False
    for c in constraints:
        v = c["fun"](w)
        if c["type"] == "eq" and abs(v) > tol * 100:
            return False
        if c["type"] == "ineq" and v < -tol * 100:
            return False
    return True


def _solve(objective, bounds, constraints, x0=None):
    """SLSQP with a feasibility check. SLSQP sometimes stops with a line-search
    warning at a point that is already optimal and feasible; accept that point
    only if every constraint holds, otherwise retry from a neutral start."""
    starts = [_start(bounds) if x0 is None else x0, _start(bounds)]
    last = None
    for s in starts:
        res = minimize(objective, s, method="SLSQP", bounds=bounds,
                       constraints=constraints, options={"ftol": 1e-10, "maxiter": 1000})
        last = res
        if res.success or _feasible(res.x, bounds, constraints):
            w = np.clip(res.x, 0, None)
            return w / w.sum()
    raise RuntimeError("optimizer did not converge: %s" % last.message)


def min_variance(mu=None, cov=None, bounds=None, group_caps=None):
    cov = data.COV if cov is None else cov
    b = _bounds_list(bounds=bounds)
    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1}] + _group_constraints(group_caps=group_caps)
    return _solve(lambda w: w @ cov @ w * 1e4, b, cons)


def max_return(mu=None, bounds=None, group_caps=None):
    mu = data.MU if mu is None else mu
    b = _bounds_list(bounds=bounds)
    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1}] + _group_constraints(group_caps=group_caps)
    return _solve(lambda w: -(w @ mu) * 100, b, cons)


def max_return_for_vol(target_vol: float, mu=None, cov=None, bounds=None, group_caps=None):
    """Highest expected return whose volatility stays within the budget."""
    mu = data.MU if mu is None else mu
    cov = data.COV if cov is None else cov
    b = _bounds_list(bounds=bounds)
    cons = [
        {"type": "eq", "fun": lambda w: w.sum() - 1},
        {"type": "ineq", "fun": lambda w: (target_vol ** 2 - w @ cov @ w) * 1e4},
    ] + _group_constraints(group_caps=group_caps)
    w_min = min_variance(mu, cov, bounds, group_caps)
    if np.sqrt(w_min @ cov @ w_min) > target_vol + 1e-9:
        return w_min  # budget below the least-risky feasible portfolio
    return _solve(lambda w: -(w @ mu) * 100, b, cons, x0=w_min)


def min_variance_for_return(target_ret: float, mu=None, cov=None, bounds=None, group_caps=None):
    mu = data.MU if mu is None else mu
    cov = data.COV if cov is None else cov
    b = _bounds_list(bounds=bounds)
    cons = [
        {"type": "eq", "fun": lambda w: w.sum() - 1},
        {"type": "eq", "fun": lambda w: (w @ mu - target_ret) * 100},
    ] + _group_constraints(group_caps=group_caps)
    return _solve(lambda w: w @ cov @ w * 1e4, b, cons)


def efficient_frontier(n_points: int = 24, mu=None, cov=None):
    mu = data.MU if mu is None else mu
    cov = data.COV if cov is None else cov
    w_lo = min_variance(mu, cov)
    w_hi = max_return(mu)
    r_lo, r_hi = float(w_lo @ mu), float(w_hi @ mu)
    points = []
    for r in np.linspace(r_lo, r_hi, n_points):
        w = min_variance_for_return(r, mu, cov) if r_lo < r < r_hi else (w_lo if r <= r_lo else w_hi)
        s = portfolio_stats(w, mu, cov, data.RISK_FREE)
        points.append({"expected_return": s["expected_return"], "volatility": s["volatility"],
                       "weights": dict(zip(data.CODES, w.round(6).tolist()))})
    return points


def model_portfolios(mu=None, cov=None):
    mu = data.MU if mu is None else mu
    cov = data.COV if cov is None else cov
    out = []
    for p in data.RISK_PROFILES:
        w = max_return_for_vol(p["target_vol"], mu, cov)
        s = portfolio_stats(w, mu, cov, data.RISK_FREE)
        rc = risk_contributions(w, cov)
        eq = sum(w[data.CODES.index(c)] for c in data.CODES if data.GROUPS[c] == "Equity")
        out.append({
            **p, **s,
            "weights": dict(zip(data.CODES, w.round(6).tolist())),
            "risk_contributions": dict(zip(data.CODES, rc.round(6).tolist())),
            "equity_share": float(eq),
        })
    return out


def risk_parity(cov=None, tol: float = 1e-10, max_iter: int = 10000):
    """Long-only equal-risk-contribution weights (cyclical coordinate method).
    Pass the covariance of the risky assets only; cash would absorb the budget."""
    cov = data.COV[1:, 1:] if cov is None else cov
    n = cov.shape[0]
    budget = 1.0 / n
    w = np.ones(n) / np.sqrt(np.diag(cov))
    for _ in range(max_iter):
        w_old = w.copy()
        for i in range(n):
            # minimize 0.5 w'Cw - sum(b ln w) one coordinate at a time:
            # w_i solves C_ii w_i^2 + (sum_{j!=i} C_ij w_j) w_i - b = 0 (positive root)
            a = cov[i, i]
            bcoef = cov[i] @ w - cov[i, i] * w[i]
            w[i] = (-bcoef + np.sqrt(bcoef ** 2 + 4 * a * budget)) / (2 * a)
        if np.abs(w - w_old).max() < tol:
            break
    return w / w.sum()


def resampled_weights(target_vol: float, n_resamples: int = 200, n_months: int = 120, seed: int = 7):
    """Re-optimize on parameters re-estimated from simulated 10-year histories.

    The spread of the resulting weights shows how much of a model portfolio is
    signal and how much is estimation noise (Michaud-style resampling)."""
    rng = np.random.default_rng(seed)
    mu_m = data.MU / 12
    cov_m = data.COV / 12
    L = np.linalg.cholesky(cov_m)
    ws = []
    for _ in range(n_resamples):
        sample = mu_m + rng.standard_normal((n_months, len(mu_m))) @ L.T
        mu_hat = sample.mean(axis=0) * 12
        cov_hat = np.cov(sample, rowvar=False) * 12
        try:
            ws.append(max_return_for_vol(target_vol, mu_hat, cov_hat))
        except RuntimeError:
            continue
    return np.array(ws)


def input_sensitivity(profile_id: str = "balanced", bump: float = 0.005):
    """Weight changes when one expected return moves by `bump` (default +0.5 pp)."""
    p = data.PROFILE_BY_ID[profile_id]
    base = max_return_for_vol(p["target_vol"])
    rows = []
    for i, code in enumerate(data.CODES):
        if code == "CASH":
            continue
        mu = data.MU.copy()
        mu[i] += bump
        w = max_return_for_vol(p["target_vol"], mu)
        rows.append({"asset": code, "max_weight_change": float(np.abs(w - base).max()),
                     "turnover": float(0.5 * np.abs(w - base).sum())})
    return rows
