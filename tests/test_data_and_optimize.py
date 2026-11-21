import numpy as np
import pytest

from wealth_engine import data, optimize
from wealth_engine.metrics import risk_contributions


@pytest.fixture(scope="module")
def portfolios():
    return optimize.model_portfolios()


def test_assumption_checks_have_no_failures():
    checks = data.validate_assumptions()
    assert all(c["status"] in ("PASS", "WARN") for c in checks)
    # the stale REIT quote is planted on purpose and must be caught
    assert any(c["status"] == "WARN" and "REIT" in c["detail"] for c in checks)


def test_covariance_is_positive_definite():
    assert np.linalg.eigvalsh(data.COV).min() > 0


@pytest.mark.parametrize("idx", range(5))
def test_model_portfolio_respects_every_constraint(portfolios, idx):
    p = portfolios[idx]
    w = np.array([p["weights"][c] for c in data.CODES])
    assert w.sum() == pytest.approx(1.0, abs=1e-6)
    for c, (lo, hi) in data.BOUNDS.items():
        assert lo - 1e-6 <= p["weights"][c] <= hi + 1e-6, c
    for gcap in data.GROUP_CAPS:
        assert sum(p["weights"][c] for c in gcap["codes"]) <= gcap["max"] + 1e-6
    assert p["volatility"] <= p["target_vol"] + 1e-5


def test_more_risk_budget_never_lowers_expected_return(portfolios):
    rets = [p["expected_return"] for p in portfolios]
    assert all(b >= a - 1e-9 for a, b in zip(rets, rets[1:]))


def test_efficient_frontier_is_monotone():
    pts = optimize.efficient_frontier(n_points=12)
    vols = [p["volatility"] for p in pts]
    rets = [p["expected_return"] for p in pts]
    assert all(b >= a - 1e-9 for a, b in zip(rets, rets[1:]))
    assert all(b >= a - 1e-6 for a, b in zip(vols, vols[1:]))


def test_model_portfolios_sit_on_or_below_the_frontier(portfolios):
    pts = optimize.efficient_frontier(n_points=40)
    for p in portfolios:
        # best frontier return at no more than this volatility
        best = max(q["expected_return"] for q in pts if q["volatility"] <= p["volatility"] + 1e-4)
        assert p["expected_return"] >= best - 2e-4


def test_risk_parity_equalizes_risk_contributions():
    w = optimize.risk_parity()
    rc = risk_contributions(w, data.COV[1:, 1:])
    assert w.min() > 0
    assert rc.max() - rc.min() < 1e-6


def test_tiny_budget_falls_back_to_minimum_variance():
    w = optimize.max_return_for_vol(0.001)
    wmin = optimize.min_variance()
    assert np.allclose(w, wmin, atol=1e-6)


def test_resampling_returns_valid_weights():
    ws = optimize.resampled_weights(0.085, n_resamples=20)
    assert len(ws) >= 18
    assert np.allclose(ws.sum(axis=1), 1.0, atol=1e-6)
    assert (ws >= -1e-9).all()


def test_input_sensitivity_reports_every_risky_asset():
    rows = optimize.input_sensitivity("balanced")
    assert {r["asset"] for r in rows} == set(data.CODES) - {"CASH"}
    assert all(r["turnover"] >= 0 for r in rows)
