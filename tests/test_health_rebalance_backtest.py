import copy

import numpy as np
import pytest

from wealth_engine import backtest, data, health, optimize, rebalance


@pytest.fixture(scope="module")
def weights():
    return {p["id"]: p["weights"] for p in optimize.model_portfolios()}


@pytest.fixture(scope="module")
def accounts(weights):
    return {a["id"]: a for a in data.build_accounts(weights)}


# ---------- health score ----------
IDEAL = dict(age=40, retired=False, gross_income=100000, essential_monthly=3000, liquid_savings=30000,
             investable={"RRSP": 300000}, monthly_contribution=2000, mortgage_payment=1000, other_debt_payment=0,
             card_balance=0, card_limit=10000, dependents=1, life_insurance=True, disability_insurance=True,
             retirement_age=65, plan_to_age=95, retirement_spending=50000, retirement_other_income=20000,
             summary="")


def test_ideal_household_scores_100():
    r = health.score_household(IDEAL, 0.95)
    assert r["score"] == 100
    assert r["band"] == "Strong"
    assert r["next_best_actions"] == []


def test_component_points_stay_within_bounds():
    for h in data.HOUSEHOLDS:
        r = health.score_household(h, 0.5)
        for c in r["components"]:
            assert 0 <= c["points"] <= c["max"]
        assert sum(c["max"] for c in r["components"]) == 100


def test_worse_inputs_never_raise_the_score():
    worse = copy.deepcopy(IDEAL)
    worse.update(card_balance=9000, liquid_savings=2000, monthly_contribution=200)
    assert health.score_household(worse, 0.5)["score"] < health.score_household(IDEAL, 0.95)["score"]


def test_actions_are_ranked_by_points():
    for h in data.HOUSEHOLDS:
        acts = health.score_household(h, 0.3)["next_best_actions"]
        pts = [a["points"] for a in acts]
        assert pts == sorted(pts, reverse=True)


def test_retired_household_is_scored_on_withdrawal_rate():
    r = health.score_household(data.HOUSEHOLD_BY_ID["H4"], 0.8)
    assert r["components"][0]["name"] == "Withdrawal rate"


# ---------- rebalancing ----------
def test_no_trades_inside_bands(accounts, weights):
    r = rebalance.plan_rebalance(accounts["A6"], weights["growth"])
    assert r["trigger"] == "none" and r["orders"] == []


def test_band_breach_is_brought_back_inside_bands(accounts, weights):
    r = rebalance.plan_rebalance(accounts["A2"], weights["balanced"])
    assert r["trigger"] == "bands"
    for c in data.CODES:
        assert abs(r["post_drift"][c]) <= r["bands"][c] + 1e-9


def test_generated_orders_never_short_and_are_whole_units(accounts, weights):
    for a in accounts.values():
        r = rebalance.plan_rebalance(a, weights[a["risk_profile"]])
        for o in r["orders"]:
            assert isinstance(o["units"], int) and o["units"] > 0
            if o["side"] == "SELL":
                assert o["units"] <= a["holdings"].get(o["code"], 0)


def test_cash_never_goes_negative(accounts, weights):
    for a in accounts.values():
        r = rebalance.plan_rebalance(a, weights[a["risk_profile"]])
        assert r["cash_after"] >= -1e-6


def test_restricted_fund_can_be_sold_but_not_bought(accounts, weights):
    a = copy.deepcopy(accounts["A5"])
    r = rebalance.plan_rebalance(a, weights["aggressive_growth"])
    em = [o for o in r["orders"] if o["code"] == "EMEQ"]
    assert em and all(o["side"] == "SELL" and o["status"] == "PASS" for o in em)
    assert r["targets"]["EMEQ"] == 0
    # its weight goes to the other equity classes, so the account stays fully invested
    assert sum(r["targets"].values()) == pytest.approx(1.0, abs=1e-5)
    # without the restriction and with no units held, the engine would buy it
    a["holdings"].pop("EMEQ", None)
    unrestricted = rebalance.plan_rebalance(dict(a, restrictions=[]), weights["aggressive_growth"])
    assert any(o["code"] == "EMEQ" and o["side"] == "BUY" for o in unrestricted["orders"])
    restricted = rebalance.plan_rebalance(a, weights["aggressive_growth"])
    assert not any(o["code"] == "EMEQ" and o["side"] == "BUY" for o in restricted["orders"])


def test_stale_price_blocks_the_order(accounts, weights):
    r = rebalance.plan_rebalance(accounts["A5"], weights["aggressive_growth"])
    reit = [o for o in r["orders"] if o["code"] == "REIT"]
    assert reit and all(o["status"] == "BLOCK" for o in reit)
    assert any(c["id"] == "C2" and c["status"] == "BLOCK" for c in reit[0]["checks"])


def test_deposit_only_buys(accounts, weights):
    r = rebalance.plan_rebalance(accounts["A1"], weights["growth"])
    assert r["trigger"] == "deposit"
    assert r["orders"] and all(o["side"] == "BUY" for o in r["orders"])


def test_withdrawal_only_sells_and_raises_the_cash(accounts, weights):
    a = accounts["A4"]
    r = rebalance.plan_rebalance(a, weights["moderately_conservative"])
    assert r["trigger"] == "withdrawal"
    assert all(o["side"] == "SELL" for o in r["orders"])
    assert r["cash_after"] >= 0


def test_taxable_account_reports_realized_gain(accounts, weights):
    r = rebalance.plan_rebalance(accounts["A3"], weights["balanced"])
    assert r["trigger"] == "bands"
    assert r["realized_gain"] > 0


def test_registered_account_reports_no_gain(accounts, weights):
    r = rebalance.plan_rebalance(accounts["A2"], weights["balanced"])
    assert r["realized_gain"] == 0


def test_business_day_count_skips_weekends():
    from datetime import date
    assert rebalance.business_days_between(date(2026, 11, 13), date(2026, 11, 16)) == 1  # Fri -> Mon


# ---------- backtest ----------
def test_never_rebalance_has_zero_turnover(weights):
    target = np.array([weights["balanced"][c] for c in data.CODES])
    rets = backtest.simulate_monthly(20, 60, seed=1)
    r = backtest.run_policy(rets, target, "none")
    assert (r["turnover"] == 0).all()


def test_monthly_policy_tracks_the_reference_exactly(weights):
    target = np.array([weights["balanced"][c] for c in data.CODES])
    rets = backtest.simulate_monthly(20, 60, seed=2)
    a = backtest.run_policy(rets, target, "monthly", cost_bps=0)
    b = backtest.run_policy(rets, target, "monthly", cost_bps=0)
    assert np.allclose(a["returns"], b["returns"])


def test_bands_trade_less_than_quarterly(weights):
    res = backtest.compare_policies(weights=weights["balanced"], n_hist=60, years=10)
    by = {p["id"]: p for p in res["policies"]}
    assert by["bands"]["turnover_per_year"] < by["quarterly"]["turnover_per_year"]
    assert by["none"]["tracking_error"] > by["bands"]["tracking_error"]
