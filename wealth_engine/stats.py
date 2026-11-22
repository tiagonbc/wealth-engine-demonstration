"""Descriptive statistics and distribution shape for any sample.

`describe()` returns what a reviewer needs to judge a distribution: centre
(mean, median), spread (standard deviation, interquartile range, annualized
volatility), shape (skewness, excess kurtosis, share of points beyond three
standard deviations against the normal 0.27%), tails (percentiles, value at
risk, conditional value at risk), tests (Jarque-Bera normality test, lag-1
autocorrelation) plus a histogram and normal Q-Q quantiles for charts.
"""
from __future__ import annotations

import numpy as np
from scipy import stats as st

NORMAL_BEYOND_3SD = float(2 * st.norm.sf(3))  # 0.27%
QQ_PROBS = np.linspace(0.005, 0.995, 100)


def describe(x, kind: str = "return", periods_per_year: int | None = None, bins: int = 40,
             time_series: bool = True, hist_upper_pct: float | None = None) -> dict:
    """kind='return' for returns (fractions), 'money' for wealth amounts."""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    n = int(x.size)
    if n < 8:
        raise ValueError("need at least 8 observations")
    mean = float(x.mean())
    sd = float(x.std(ddof=1))
    pct = np.percentile(x, [1, 5, 25, 50, 75, 95, 99])
    jb = st.jarque_bera(x)
    z = (x - mean) / sd if sd > 0 else np.zeros_like(x)
    out = {
        "kind": kind, "n": n,
        "mean": mean, "median": float(pct[3]), "stdev": sd,
        "min": float(x.min()), "max": float(x.max()),
        "p1": float(pct[0]), "p5": float(pct[1]), "p25": float(pct[2]),
        "p75": float(pct[4]), "p95": float(pct[5]), "p99": float(pct[6]),
        "iqr": float(pct[4] - pct[2]),
        "skewness": float(st.skew(x, bias=False)),
        "excess_kurtosis": float(st.kurtosis(x, fisher=True, bias=False)),
        "beyond_3sd": float((np.abs(z) > 3).mean()),
        "beyond_3sd_normal": NORMAL_BEYOND_3SD,
        "jarque_bera": float(jb.statistic), "jarque_bera_p": float(jb.pvalue),
        "autocorr1": float(np.corrcoef(x[:-1], x[1:])[0, 1]) if time_series and sd > 0 else None,
    }
    if kind == "return":
        tail = x[x <= pct[1]]
        out.update(var95=float(-pct[1]), cvar95=float(-tail.mean()), share_positive=float((x > 0).mean()))
        if periods_per_year:
            out.update(periods_per_year=periods_per_year, ann_mean=mean * periods_per_year,
                       ann_vol=sd * np.sqrt(periods_per_year))
    else:
        out.update(share_positive=float((x > 0).mean()))
    if hist_upper_pct is not None:
        # long right tails (wealth outcomes): bin up to a percentile and count the rest
        hi = float(np.percentile(x, hist_upper_pct))
        counts, edges = np.histogram(x[x <= hi], bins=bins, range=(float(x.min()), hi))
        out["hist"] = {"edges": edges.tolist(), "counts": counts.tolist(), "above": int((x > hi).sum()), "upper_pct": hist_upper_pct}
    else:
        counts, edges = np.histogram(x, bins=bins)
        out["hist"] = {"edges": edges.tolist(), "counts": counts.tolist()}
    out["qq"] = {"p": QQ_PROBS.tolist(), "empirical": np.quantile(x, QQ_PROBS).tolist(),
                 "normal": (mean + sd * st.norm.ppf(QQ_PROBS)).tolist()}
    return out
