"""Performance and risk metrics shared by the backtests and the API."""
from __future__ import annotations

import numpy as np


def cagr(values: np.ndarray, periods_per_year: int = 12) -> float:
    values = np.asarray(values, float)
    years = (len(values) - 1) / periods_per_year
    return float((values[-1] / values[0]) ** (1 / years) - 1) if years > 0 else 0.0


def annual_vol(returns: np.ndarray, periods_per_year: int = 12) -> float:
    return float(np.std(returns, ddof=1) * np.sqrt(periods_per_year))


def sharpe(returns: np.ndarray, rf_annual: float, periods_per_year: int = 12) -> float:
    excess = np.asarray(returns) - ((1 + rf_annual) ** (1 / periods_per_year) - 1)
    sd = np.std(excess, ddof=1)
    return float(np.mean(excess) / sd * np.sqrt(periods_per_year)) if sd > 0 else 0.0


def max_drawdown(values: np.ndarray) -> float:
    values = np.asarray(values, float)
    peaks = np.maximum.accumulate(values)
    return float((values / peaks - 1).min())


def tracking_error(returns: np.ndarray, benchmark: np.ndarray, periods_per_year: int = 12) -> float:
    diff = np.asarray(returns) - np.asarray(benchmark)
    return float(np.std(diff, ddof=1) * np.sqrt(periods_per_year))


def portfolio_stats(w: np.ndarray, mu: np.ndarray, cov: np.ndarray, rf: float) -> dict:
    ret = float(w @ mu)
    vol = float(np.sqrt(w @ cov @ w))
    return {"expected_return": ret, "volatility": vol, "sharpe": (ret - rf) / vol if vol > 0 else 0.0}


def risk_contributions(w: np.ndarray, cov: np.ndarray) -> np.ndarray:
    """Share of portfolio variance contributed by each asset (sums to 1)."""
    var = float(w @ cov @ w)
    return w * (cov @ w) / var
