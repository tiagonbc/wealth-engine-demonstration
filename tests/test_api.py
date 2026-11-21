import pytest

from api.app import create_app
from wealth_engine import data, optimize


@pytest.fixture(scope="module")
def client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_status(client):
    r = client.get("/api/v1/status")
    assert r.status_code == 200
    body = r.get_json()
    assert body["status"] == "ok" and body["data_checks"]["fail"] == 0
    assert r.headers["X-Request-ID"] and float(r.headers["X-Elapsed-Ms"]) >= 0


def test_request_id_is_echoed(client):
    r = client.get("/api/v1/status", headers={"X-Request-ID": "abc123"})
    assert r.headers["X-Request-ID"] == "abc123"


def test_model_portfolios(client):
    body = client.get("/api/v1/model-portfolios").get_json()
    assert [p["id"] for p in body["portfolios"]] == [p["id"] for p in data.RISK_PROFILES]


def test_optimize_by_profile_and_by_budget(client):
    a = client.post("/api/v1/portfolios/optimize", json={"risk_profile": "growth"}).get_json()
    b = client.post("/api/v1/portfolios/optimize", json={"target_vol": 0.11}).get_json()
    assert abs(sum(a["weights"].values()) - 1) < 1e-6
    assert a["weights"] == b["weights"]


def test_optimize_rejects_both_or_neither(client):
    r = client.post("/api/v1/portfolios/optimize", json={"risk_profile": "growth", "target_vol": 0.1})
    assert r.status_code == 400
    assert r.mimetype == "application/problem+json"
    assert client.post("/api/v1/portfolios/optimize", json={}).status_code == 400


def test_simulate_happy_path(client):
    body = {"age": 40, "retirement_age": 65, "investable": 150000, "monthly_contribution": 1200,
            "retirement_spending": 60000, "retirement_other_income": 20000, "risk_profile": "growth",
            "paths": 2000, "seed": 1}
    r = client.post("/api/v1/plans/simulate", json=body)
    assert r.status_code == 200
    res = r.get_json()
    assert 0 <= res["probability_of_success"] <= 1
    assert res["n_paths"] == 2000 and len(res["ages"]) == 56


def test_simulate_caps_paths_to_protect_the_service(client):
    body = {"age": 40, "retirement_age": 65, "investable": 1, "retirement_spending": 1, "paths": 10 ** 6}
    r = client.post("/api/v1/plans/simulate", json=body)
    assert r.status_code == 400
    assert any(e["field"] == "paths" for e in r.get_json()["errors"])


def test_simulate_rejects_unknown_fields(client):
    body = {"age": 40, "retirement_age": 65, "investable": 1, "retirement_spending": 1, "colour": "blue"}
    assert client.post("/api/v1/plans/simulate", json=body).status_code == 400


def test_simulate_rejects_retired_with_contributions(client):
    body = {"age": 70, "retirement_age": 65, "investable": 1000, "retirement_spending": 1, "monthly_contribution": 100}
    assert client.post("/api/v1/plans/simulate", json=body).status_code == 422


def test_non_json_body_is_415(client):
    r = client.post("/api/v1/plans/simulate", data="age=40", content_type="text/plain")
    assert r.status_code == 415


def test_health_score_endpoint(client):
    h = {k: v for k, v in data.HOUSEHOLD_BY_ID["H2"].items() if k not in ("id", "name")}
    h["retirement_probability"] = 0.7
    r = client.post("/api/v1/health-score", json=h)
    assert r.status_code == 200
    assert 0 <= r.get_json()["score"] <= 100


def test_rebalance_endpoint_matches_the_engine(client):
    w = {p["id"]: p["weights"] for p in optimize.model_portfolios()}
    acct = next(a for a in data.build_accounts(w) if a["id"] == "A2")
    payload = {k: acct[k] for k in ("id", "type", "cash", "cash_flow", "holdings", "acb", "restrictions", "risk_profile")}
    r = client.post("/api/v1/accounts/rebalance", json=payload)
    assert r.status_code == 200
    assert r.get_json()["trigger"] == "bands"


def test_rebalance_rejects_unknown_fund(client):
    payload = {"id": "X", "type": "TFSA", "cash": 0, "holdings": {"ZZZ": 1}, "risk_profile": "balanced"}
    assert client.post("/api/v1/accounts/rebalance", json=payload).status_code == 400


def test_unknown_household_is_404_problem_json(client):
    r = client.get("/api/v1/households/H99")
    assert r.status_code == 404 and r.mimetype == "application/problem+json"


def test_wrong_method_is_405(client):
    assert client.get("/api/v1/plans/simulate").status_code == 405


def test_openapi_lists_every_route(client):
    app = create_app()
    routes = {str(r.rule).replace("<hid>", "{hid}") for r in app.url_map.iter_rules() if str(r.rule).startswith("/api/")}
    spec = client.get("/api/v1/openapi.json").get_json()
    assert routes == set(spec["paths"])
