import numpy as np
import pytest

from wealth_engine import data, simulate, validation
from wealth_engine.simulate import Plan, project

BALANCED = None


def balanced():
    from wealth_engine import optimize
    global BALANCED
    if BALANCED is None:
        mp = {p["id"]: p for p in optimize.model_portfolios()}["balanced"]
        BALANCED = np.array([mp["weights"][c] for c in data.CODES])
    return BALANCED


def plan(**kw):
    base = dict(age=55, retirement_age=62, plan_to_age=95, investable=600000, monthly_contribution=2000,
                retirement_spending=64000, retirement_other_income=28000)
    base.update(kw)
    return Plan(**base)


def test_lognormal_parameters_reproduce_mean_and_volatility():
    m, s = simulate.lognormal_params(np.array([0.07]), np.array([0.16]))
    rng = np.random.default_rng(0)
    r = np.expm1(m + s * rng.standard_normal(400000))
    assert r.mean() == pytest.approx(0.07, abs=0.002)
    assert r.std() == pytest.approx(0.16, abs=0.002)


def test_zero_volatility_matches_closed_form():
    p = plan(age=60, retirement_age=60, plan_to_age=70, investable=100000, monthly_contribution=0,
             retirement_spending=15000, retirement_other_income=5000)
    real = np.full((1, p.years), 0.03)
    wealth, dep = project(p, real)
    w = 100000.0
    for _ in range(10):
        w = (w - 10000) * 1.03
    assert wealth[0, -1] == pytest.approx(w)
    assert np.isnan(dep[0])


def test_depletion_age_is_recorded():
    p = plan(age=70, retirement_age=70, plan_to_age=95, investable=50000, monthly_contribution=0,
             retirement_spending=30000, retirement_other_income=10000)
    real = np.zeros((1, p.years))
    _, dep = project(p, real)
    assert dep[0] == 72  # 50k - 20k - 20k leaves 10k; the third draw empties it at 72


def test_same_seed_same_answer():
    a, _ = simulate.simulate_plan(plan(), balanced(), n_paths=2000, seed=5, with_spending_solve=False)
    b, _ = simulate.simulate_plan(plan(), balanced(), n_paths=2000, seed=5, with_spending_solve=False)
    assert a["probability_of_success"] == b["probability_of_success"]


def test_more_spending_never_raises_success():
    p = plan()
    rng = np.random.default_rng(1)
    real = simulate.real_portfolio_returns(simulate.draw_asset_returns(rng, 3000, p.years), balanced(),
                                           p.inflation, p.fee)
    probs = [np.isnan(project(p, real, spending=s)[1]).mean() for s in (50000, 60000, 70000, 80000)]
    assert all(b <= a for a, b in zip(probs, probs[1:]))


def test_percentiles_are_ordered():
    r, _ = simulate.simulate_plan(plan(), balanced(), n_paths=3000, with_spending_solve=False)
    rows = np.array([r["percentiles"][str(q)] for q in simulate.PERCENTILES])
    assert (np.diff(rows, axis=0) >= -1e-6).all()


def test_spending_at_90_hits_the_target():
    p = plan()
    r, real = simulate.simulate_plan(p, balanced(), n_paths=4000)
    _, dep = project(p, real, spending=r["spending_at_90"])
    assert np.isnan(dep).mean() >= 0.90
    _, dep2 = project(p, real, spending=r["spending_at_90"] + 1000)
    assert np.isnan(dep2).mean() < 0.905


def test_student_t_keeps_volatility_but_fattens_tails():
    rng = np.random.default_rng(3)
    n = simulate.draw_asset_returns(rng, 60000, 1)[:, 0, 4]
    t = simulate.draw_asset_returns(rng, 60000, 1, tails="t")[:, 0, 4]
    assert t.std() == pytest.approx(n.std(), rel=0.08)
    kurt = lambda x: ((x - x.mean()) ** 4).mean() / x.var() ** 2
    assert kurt(t) > kurt(n) + 0.5


def test_what_if_grid_moves_the_right_way():
    p = plan()
    _, real = simulate.simulate_plan(p, balanced(), n_paths=3000, with_spending_solve=False)
    grid = simulate.what_if_grid(p, real, retired=False)
    cells = np.array(grid["cells"])
    assert (np.diff(cells, axis=0) >= -1e-9).all()  # more saving helps
    assert (np.diff(cells, axis=1) >= -1e-9).all()  # retiring later helps


def test_convergence_error_shrinks_with_paths():
    rows = validation.convergence(plan(), balanced(), path_counts=(250, 4000), n_seeds=6)
    assert rows[1]["sd_across_seeds"] < rows[0]["sd_across_seeds"]


def test_calibrated_world_scores_near_the_ideal_brier():
    from wealth_engine import optimize
    w = {p["id"]: p["weights"] for p in optimize.model_portfolios()}
    res = validation.calibration(w, n_plans=300, n_paths=300, seed=8)
    model = next(x for x in res["worlds"] if x["id"] == "model")
    assert abs(model["brier"] - model["brier_if_calibrated"]) < 0.05
    worse = next(x for x in res["worlds"] if x["id"] == "optimistic")
    assert worse["mean_realized"] < model["mean_realized"] + 0.02
