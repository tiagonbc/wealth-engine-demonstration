import pytest

from wealth_engine import optimize, risk


@pytest.fixture(scope="module")
def report():
    w = {p["id"]: p["weights"] for p in optimize.model_portfolios()}
    return risk.risk_report(w, n_hist=120, years=15, n_annual=20000)


def test_one_row_per_model_portfolio(report):
    assert [r["id"] for r in report] == ["conservative", "moderately_conservative", "balanced", "growth",
                                         "aggressive_growth"]


def test_cvar_is_at_least_var(report):
    for r in report:
        assert r["cvar95_1y"] >= r["var95_1y"]


def test_riskier_profiles_carry_more_tail_risk(report):
    var = [r["var95_1y"] for r in report]
    vol = [r["volatility"] for r in report]
    assert var == sorted(var)
    assert vol == sorted(vol)


def test_drawdowns_are_negative_and_bounded(report):
    for r in report:
        assert -1 < r["worst_drawdown_p5"] <= r["max_drawdown"] < 0


def test_losing_year_probability_is_a_probability(report):
    for r in report:
        assert 0 < r["prob_losing_year"] < 0.5
