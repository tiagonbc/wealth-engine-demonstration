"""Real market data used for the distribution statistics.

SPY total-return closes (dividends reinvested) from Norgate Data are read from
a local, git-ignored file, data/spy_tr_daily.csv. The repository and the site
publish only statistics, histograms and quantiles derived from it, never the
price series itself. If the file is missing, the SPY section is skipped.
"""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import numpy as np

SPY_FILE = Path(__file__).resolve().parent.parent / "data" / "spy_tr_daily.csv"


def load_spy(path: Path = SPY_FILE):
    if not path.exists():
        return None
    dates, closes = [], []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            dates.append(date.fromisoformat(row["date"][:10]))
            closes.append(float(row["close_tr"]))
    return dates, np.array(closes)


def spy_returns(path: Path = SPY_FILE):
    """Daily, monthly (complete months) and calendar-year returns, plus the span."""
    loaded = load_spy(path)
    if loaded is None:
        return None
    dates, px = loaded
    daily = px[1:] / px[:-1] - 1
    # last close of each month
    month_end = {}
    for d, p in zip(dates, px):
        month_end[(d.year, d.month)] = (d, p)
    keys = sorted(month_end)
    last_date = dates[-1]
    if keys and (keys[-1] == (last_date.year, last_date.month)):
        keys = keys[:-1]  # drop the month still in progress
    m_px = np.array([month_end[k][1] for k in keys])
    monthly = m_px[1:] / m_px[:-1] - 1
    year_end = {}
    for d, p in zip(dates, px):
        year_end[d.year] = p
    years = sorted(year_end)
    full_years = [y for y in years if y > years[0] and y < last_date.year]
    annual = np.array([year_end[y] / year_end[y - 1] - 1 for y in full_years])
    return {
        "daily": daily, "monthly": monthly, "annual": annual,
        "start": dates[0].isoformat(), "end": last_date.isoformat(),
        "monthly_span": "%d-%02d to %d-%02d" % (keys[1][0], keys[1][1], keys[-1][0], keys[-1][1]),
        "annual_span": "%d to %d" % (full_years[0], full_years[-1]),
    }
