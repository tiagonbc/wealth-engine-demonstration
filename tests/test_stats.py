import numpy as np
import pytest

from wealth_engine.stats import NORMAL_BEYOND_3SD, describe


def test_normal_sample_looks_normal():
    x = np.random.default_rng(1).normal(0.01, 0.04, 20000)
    d = describe(x, periods_per_year=12)
    assert abs(d["skewness"]) < 0.06
    assert abs(d["excess_kurtosis"]) < 0.12
    assert d["jarque_bera_p"] > 0.01
    assert d["mean"] == pytest.approx(0.01, abs=0.001)
    assert d["ann_vol"] == pytest.approx(0.04 * np.sqrt(12), rel=0.03)
    assert d["beyond_3sd"] == pytest.approx(NORMAL_BEYOND_3SD, abs=0.0015)


def test_fat_tails_are_detected():
    x = np.random.default_rng(2).standard_t(3, 20000) * 0.02
    d = describe(x)
    assert d["excess_kurtosis"] > 2
    assert d["beyond_3sd"] > 2 * NORMAL_BEYOND_3SD
    assert d["jarque_bera_p"] < 1e-6


def test_skew_sign_follows_the_tail():
    rng = np.random.default_rng(3)
    right = np.expm1(rng.normal(0, 0.5, 20000))
    assert describe(right)["skewness"] > 1
    assert describe(-right)["skewness"] < -1


def test_tail_metrics_and_histogram_are_consistent():
    x = np.random.default_rng(4).normal(0, 0.05, 5000)
    d = describe(x, bins=30)
    assert d["cvar95"] >= d["var95"] > 0
    assert sum(d["hist"]["counts"]) == d["n"]
    assert len(d["hist"]["edges"]) == 31
    assert d["p1"] <= d["p5"] <= d["p25"] <= d["median"] <= d["p75"] <= d["p95"] <= d["p99"]
    assert np.all(np.diff(d["qq"]["empirical"]) >= 0)


def test_known_small_sample():
    d = describe([1, 2, 3, 4, 5, 6, 7, 100], kind="money", time_series=False)
    assert d["median"] == 4.5
    assert d["mean"] == 16
    assert d["skewness"] > 2
    assert d["autocorr1"] is None


def test_long_tail_histogram_counts_everything():
    x = np.concatenate([np.zeros(300), np.random.default_rng(5).lognormal(12, 1.2, 9700)])
    d = describe(x, kind="money", time_series=False, hist_upper_pct=99)
    assert sum(d["hist"]["counts"]) + d["hist"]["above"] == d["n"]
    assert d["hist"]["edges"][-1] == pytest.approx(d["p99"])
    assert d["skewness"] > 2


def test_too_few_points_is_an_error():
    with pytest.raises(ValueError):
        describe([0.1, 0.2, 0.3])
