"""Flask REST API over the wealth engine.

Run locally:   python -m flask --app api.app run   (or: docker compose up)
All endpoints live under /api/v1 and return JSON. Errors follow RFC 9457
(application/problem+json). Every response carries an X-Request-ID and the
server time in X-Elapsed-Ms.
"""
from __future__ import annotations

import time
import uuid
from functools import lru_cache

import numpy as np
from flask import Flask, g, jsonify, request
from jsonschema import Draft202012Validator

from wealth_engine import __version__, data, health, optimize, rebalance, simulate

MAX_PATHS = 50000


class ApiError(Exception):
    def __init__(self, status: int, title: str, detail: str = "", errors=None):
        super().__init__(detail)
        self.status, self.title, self.detail, self.errors = status, title, detail, errors or []


# ---------- request schemas ----------
PLAN_SCHEMA = {
    "type": "object",
    "required": ["age", "retirement_age", "investable", "retirement_spending"],
    "properties": {
        "age": {"type": "integer", "minimum": 18, "maximum": 100},
        "retirement_age": {"type": "integer", "minimum": 18, "maximum": 100},
        "plan_to_age": {"type": "integer", "minimum": 50, "maximum": 110},
        "investable": {"type": "number", "minimum": 0},
        "monthly_contribution": {"type": "number", "minimum": 0},
        "retirement_spending": {"type": "number", "minimum": 0},
        "retirement_other_income": {"type": "number", "minimum": 0},
        "risk_profile": {"enum": [p["id"] for p in data.RISK_PROFILES]},
        "paths": {"type": "integer", "minimum": 100, "maximum": MAX_PATHS},
        "seed": {"type": "integer", "minimum": 0},
        "tails": {"enum": ["normal", "t"]},
    },
    "additionalProperties": False,
}

OPTIMIZE_SCHEMA = {
    "type": "object",
    "properties": {
        "risk_profile": {"enum": [p["id"] for p in data.RISK_PROFILES]},
        "target_vol": {"type": "number", "minimum": 0.02, "maximum": 0.16},
    },
    "oneOf": [{"required": ["risk_profile"]}, {"required": ["target_vol"]}],
    "additionalProperties": False,
}

HEALTH_SCHEMA = {
    "type": "object",
    "required": ["age", "retired", "gross_income", "essential_monthly", "liquid_savings", "investable",
                 "monthly_contribution", "mortgage_payment", "other_debt_payment", "card_balance",
                 "card_limit", "dependents", "life_insurance", "disability_insurance",
                 "retirement_age", "retirement_spending", "retirement_other_income"],
    "properties": {
        "age": {"type": "integer", "minimum": 18, "maximum": 100},
        "retired": {"type": "boolean"},
        "gross_income": {"type": "number", "exclusiveMinimum": 0},
        "essential_monthly": {"type": "number", "exclusiveMinimum": 0},
        "liquid_savings": {"type": "number", "minimum": 0},
        "investable": {"type": "object", "additionalProperties": {"type": "number", "minimum": 0}},
        "monthly_contribution": {"type": "number", "minimum": 0},
        "mortgage_payment": {"type": "number", "minimum": 0},
        "other_debt_payment": {"type": "number", "minimum": 0},
        "card_balance": {"type": "number", "minimum": 0},
        "card_limit": {"type": "number", "minimum": 0},
        "dependents": {"type": "integer", "minimum": 0},
        "life_insurance": {"type": "boolean"},
        "disability_insurance": {"type": "boolean"},
        "retirement_age": {"type": "integer"},
        "plan_to_age": {"type": "integer"},
        "retirement_spending": {"type": "number", "minimum": 0},
        "retirement_other_income": {"type": "number", "minimum": 0},
        "risk_profile": {"enum": [p["id"] for p in data.RISK_PROFILES]},
        "retirement_probability": {"type": "number", "minimum": 0, "maximum": 1},
        "summary": {"type": "string"},
    },
}

REBALANCE_SCHEMA = {
    "type": "object",
    "required": ["id", "type", "cash", "holdings", "risk_profile"],
    "properties": {
        "id": {"type": "string"},
        "type": {"enum": ["TFSA", "RRSP", "RRIF", "FHSA", "Non-registered"]},
        "cash": {"type": "number"},
        "cash_flow": {"type": "number"},
        "holdings": {"type": "object", "propertyNames": {"enum": data.CODES},
                     "additionalProperties": {"type": "integer", "minimum": 0}},
        "acb": {"type": "object", "propertyNames": {"enum": data.CODES},
                "additionalProperties": {"type": "number", "minimum": 0}},
        "restrictions": {"type": "array", "items": {"enum": data.CODES}},
        "risk_profile": {"enum": [p["id"] for p in data.RISK_PROFILES]},
    },
}


def _validate(schema: dict, body):
    if body is None:
        raise ApiError(415, "Unsupported Media Type", "Send a JSON body with Content-Type: application/json.")
    errors = sorted(Draft202012Validator(schema).iter_errors(body), key=lambda e: list(e.path))
    if errors:
        raise ApiError(400, "Invalid request", "%d field(s) failed validation." % len(errors),
                       [{"field": "/".join(str(p) for p in e.path) or "(body)", "message": e.message} for e in errors])
    return body


@lru_cache(maxsize=1)
def _model_portfolios():
    return optimize.model_portfolios()


def _weights(profile_id: str) -> np.ndarray:
    mp = {p["id"]: p for p in _model_portfolios()}[profile_id]
    return np.array([mp["weights"][c] for c in data.CODES])


def create_app() -> Flask:
    app = Flask(__name__)
    app.json.sort_keys = False

    @app.before_request
    def _start():
        g.t0 = time.perf_counter()
        g.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]

    @app.after_request
    def _finish(resp):
        resp.headers["X-Request-ID"] = g.get("request_id", "")
        resp.headers["X-Elapsed-Ms"] = "%.1f" % ((time.perf_counter() - g.get("t0", time.perf_counter())) * 1000)
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.errorhandler(ApiError)
    def _api_error(e: ApiError):
        body = {"type": "about:blank", "title": e.title, "status": e.status, "detail": e.detail,
                "instance": request.path, "request_id": g.get("request_id")}
        if e.errors:
            body["errors"] = e.errors
        resp = jsonify(body)
        resp.status_code = e.status
        resp.mimetype = "application/problem+json"
        return resp

    @app.errorhandler(404)
    def _not_found(_):
        return _api_error(ApiError(404, "Not Found", "No route %s %s." % (request.method, request.path)))

    @app.errorhandler(405)
    def _method(_):
        return _api_error(ApiError(405, "Method Not Allowed", "%s is not allowed on %s." % (request.method, request.path)))

    @app.errorhandler(500)
    def _server(_):
        return _api_error(ApiError(500, "Internal Server Error", "The engine failed; the request ID identifies the log entry."))

    # ---------- routes ----------
    @app.get("/api/v1/status")
    def status():
        checks = data.validate_assumptions()
        return jsonify({"status": "ok" if all(c["status"] != "FAIL" for c in checks) else "degraded",
                        "version": __version__, "as_of": data.AS_OF.isoformat(),
                        "data_checks": {"pass": sum(c["status"] == "PASS" for c in checks),
                                        "warn": sum(c["status"] == "WARN" for c in checks),
                                        "fail": sum(c["status"] == "FAIL" for c in checks)}})

    @app.get("/api/v1/assumptions")
    def assumptions():
        return jsonify({
            "as_of": data.AS_OF.isoformat(), "note": "Illustrative mock assumptions, not forecasts.",
            "inflation": data.INFLATION, "platform_fee": data.PLATFORM_FEE, "risk_free": data.RISK_FREE,
            "asset_classes": [{"code": c, "name": n, "group": gname, "expected_return": mu, "volatility": s}
                              for c, n, gname, mu, s in data.ASSET_CLASSES],
            "correlation": data.CORR.round(4).tolist(),
            "bounds": {c: list(b) for c, b in data.BOUNDS.items()}, "group_caps": data.GROUP_CAPS,
        })

    @app.get("/api/v1/model-portfolios")
    def model_portfolios():
        return jsonify({"portfolios": _model_portfolios()})

    @app.post("/api/v1/portfolios/optimize")
    def optimize_portfolio():
        body = _validate(OPTIMIZE_SCHEMA, request.get_json(silent=True))
        target = body.get("target_vol") or data.PROFILE_BY_ID[body["risk_profile"]]["target_vol"]
        w = optimize.max_return_for_vol(float(target))
        from wealth_engine.metrics import portfolio_stats
        return jsonify({"target_vol": target, **portfolio_stats(w, data.MU, data.COV, data.RISK_FREE),
                        "weights": dict(zip(data.CODES, w.round(6).tolist()))})

    @app.post("/api/v1/plans/simulate")
    def simulate_plan():
        body = _validate(PLAN_SCHEMA, request.get_json(silent=True))
        if body["retirement_age"] < body["age"] and body.get("monthly_contribution", 0) > 0:
            raise ApiError(422, "Inconsistent plan", "A retired household cannot have monthly contributions.")
        plan = simulate.Plan(
            age=body["age"], retirement_age=body["retirement_age"], plan_to_age=body.get("plan_to_age", 95),
            investable=body["investable"], monthly_contribution=body.get("monthly_contribution", 0),
            retirement_spending=body["retirement_spending"],
            retirement_other_income=body.get("retirement_other_income", 0))
        if plan.years < 1:
            raise ApiError(422, "Inconsistent plan", "plan_to_age must be greater than age.")
        res, _ = simulate.simulate_plan(plan, _weights(body.get("risk_profile", "balanced")),
                                        n_paths=body.get("paths", 5000), seed=body.get("seed", 2026),
                                        tails=body.get("tails", "normal"))
        return jsonify(res)

    @app.post("/api/v1/health-score")
    def health_score():
        body = _validate(HEALTH_SCHEMA, request.get_json(silent=True))
        h = {"plan_to_age": 95, "summary": "", **body}
        p = body.get("retirement_probability")
        if p is None:
            plan = simulate.Plan.from_household(h)
            res, _ = simulate.simulate_plan(plan, _weights(h.get("risk_profile", "balanced")),
                                            n_paths=4000, with_spending_solve=False)
            p = res["probability_of_success"]
        return jsonify({"retirement_probability": p, **health.score_household(h, p)})

    @app.post("/api/v1/accounts/rebalance")
    def rebalance_account():
        body = _validate(REBALANCE_SCHEMA, request.get_json(silent=True))
        acct = {"cash_flow": 0, "acb": {}, "restrictions": [], **body}
        mp = {p["id"]: p for p in _model_portfolios()}[acct["risk_profile"]]
        return jsonify(rebalance.plan_rebalance(acct, mp["weights"]))

    @app.get("/api/v1/households")
    def households():
        return jsonify({"households": [{"id": h["id"], "name": h["name"], "summary": h["summary"],
                                        "risk_profile": h["risk_profile"]} for h in data.HOUSEHOLDS]})

    @app.get("/api/v1/households/<hid>")
    def household(hid):
        if hid not in data.HOUSEHOLD_BY_ID:
            raise ApiError(404, "Not Found", "No household with id %s." % hid)
        return jsonify(data.household(hid))

    @app.get("/api/v1/openapi.json")
    def openapi():
        return jsonify(openapi_spec())

    return app


def openapi_spec() -> dict:
    def op(summary, schema=None, ok="OK"):
        o = {"summary": summary, "responses": {"200": {"description": ok},
                                              "400": {"description": "Invalid request (problem+json)"}}}
        if schema:
            o["requestBody"] = {"required": True, "content": {"application/json": {"schema": schema}}}
        return o

    return {
        "openapi": "3.1.0",
        "info": {"title": "Wealth Engine API (demonstration)", "version": __version__,
                 "description": "Mock data only. Independent work by Tiago Costa; not affiliated with RBC."},
        "paths": {
            "/api/v1/status": {"get": op("Service status and data-quality checks")},
            "/api/v1/assumptions": {"get": op("Capital market assumptions and constraints")},
            "/api/v1/model-portfolios": {"get": op("The five optimized model portfolios")},
            "/api/v1/portfolios/optimize": {"post": op("Optimize for a risk profile or volatility budget", OPTIMIZE_SCHEMA)},
            "/api/v1/plans/simulate": {"post": op("Monte Carlo goal projection", PLAN_SCHEMA)},
            "/api/v1/health-score": {"post": op("Financial health score with next best actions", HEALTH_SCHEMA)},
            "/api/v1/accounts/rebalance": {"post": op("Rebalance an account and run pre-trade checks", REBALANCE_SCHEMA)},
            "/api/v1/households": {"get": op("List mock households")},
            "/api/v1/households/{hid}": {"get": op("One mock household")},
            "/api/v1/openapi.json": {"get": op("This specification")},
        },
    }


app = create_app()
