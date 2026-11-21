"""Mock data for the demonstration.

Every number in this module is illustrative. The capital market assumptions
are round numbers chosen to look plausible for a Canadian investor; they are
not forecasts and they are not RBC's. The households, accounts and prices are
fictional.
"""
from __future__ import annotations

import copy
from datetime import date

import numpy as np

AS_OF = date(2026, 11, 19)
INFLATION = 0.021          # long-run inflation used to express plans in today's dollars
PLATFORM_FEE = 0.0035      # annual all-in fee deducted from returns in projections
RISK_FREE = 0.025          # cash yield used for Sharpe ratios

# code, name, group, expected arithmetic return, volatility (annual, nominal, CAD)
ASSET_CLASSES = [
    ("CASH", "Cash (money market)", "Cash", 0.025, 0.006),
    ("CSTB", "Canadian short-term bonds", "Fixed income", 0.032, 0.025),
    ("CUB", "Canadian universe bonds", "Fixed income", 0.038, 0.055),
    ("GAGG", "Global bonds (CAD-hedged)", "Fixed income", 0.036, 0.045),
    ("CEQ", "Canadian equity", "Equity", 0.066, 0.140),
    ("USEQ", "US equity", "Equity", 0.070, 0.155),
    ("INTL", "International developed equity", "Equity", 0.068, 0.150),
    ("EMEQ", "Emerging markets equity", "Equity", 0.076, 0.190),
    ("REIT", "Global real estate", "Real assets", 0.064, 0.170),
]

CODES = [a[0] for a in ASSET_CLASSES]
NAMES = {a[0]: a[1] for a in ASSET_CLASSES}
GROUPS = {a[0]: a[2] for a in ASSET_CLASSES}
MU = np.array([a[3] for a in ASSET_CLASSES])
SIGMA = np.array([a[4] for a in ASSET_CLASSES])

CORR = np.array([
    # CASH  CSTB  CUB   GAGG  CEQ   USEQ  INTL  EMEQ  REIT
    [1.00, 0.20, 0.10, 0.10, 0.00, 0.00, 0.00, 0.00, 0.00],  # CASH
    [0.20, 1.00, 0.85, 0.70, 0.10, 0.05, 0.05, 0.05, 0.15],  # CSTB
    [0.10, 0.85, 1.00, 0.80, 0.15, 0.10, 0.10, 0.10, 0.25],  # CUB
    [0.10, 0.70, 0.80, 1.00, 0.05, 0.05, 0.05, 0.00, 0.20],  # GAGG
    [0.00, 0.10, 0.15, 0.05, 1.00, 0.75, 0.75, 0.70, 0.65],  # CEQ
    [0.00, 0.05, 0.10, 0.05, 0.75, 1.00, 0.80, 0.70, 0.65],  # USEQ
    [0.00, 0.05, 0.10, 0.05, 0.75, 0.80, 1.00, 0.78, 0.65],  # INTL
    [0.00, 0.05, 0.10, 0.00, 0.70, 0.70, 0.78, 1.00, 0.60],  # EMEQ
    [0.00, 0.15, 0.25, 0.20, 0.65, 0.65, 0.65, 0.60, 1.00],  # REIT
])

COV = np.outer(SIGMA, SIGMA) * CORR

# Policy constraints for every model portfolio (min, max weight).
BOUNDS = {
    "CASH": (0.01, 0.30),
    "CSTB": (0.00, 0.40),
    "CUB": (0.00, 0.40),
    "GAGG": (0.00, 0.25),
    "CEQ": (0.00, 0.35),
    "USEQ": (0.00, 0.35),
    "INTL": (0.00, 0.25),
    "EMEQ": (0.00, 0.10),
    "REIT": (0.00, 0.10),
}
GROUP_CAPS = [
    {"name": "Total equity", "codes": ["CEQ", "USEQ", "INTL", "EMEQ"], "max": 0.90},
]

RISK_PROFILES = [
    {"id": "conservative", "name": "Conservative", "target_vol": 0.040},
    {"id": "moderately_conservative", "name": "Moderately conservative", "target_vol": 0.060},
    {"id": "balanced", "name": "Balanced", "target_vol": 0.085},
    {"id": "growth", "name": "Growth", "target_vol": 0.110},
    {"id": "aggressive_growth", "name": "Aggressive growth", "target_vol": 0.130},
]
PROFILE_BY_ID = {p["id"]: p for p in RISK_PROFILES}

# One mock fund per asset class. REIT's quote is deliberately stale so the
# pre-trade staleness check has something to catch.
FUNDS = {
    "CASH": {"fund": "Demo Money Market Fund", "price": 10.00, "price_date": "2026-11-19"},
    "CSTB": {"fund": "Demo Short-Term Bond ETF", "price": 19.85, "price_date": "2026-11-19"},
    "CUB": {"fund": "Demo Universe Bond ETF", "price": 21.40, "price_date": "2026-11-19"},
    "GAGG": {"fund": "Demo Global Bond ETF (hedged)", "price": 18.70, "price_date": "2026-11-19"},
    "CEQ": {"fund": "Demo Canadian Equity ETF", "price": 34.10, "price_date": "2026-11-19"},
    "USEQ": {"fund": "Demo US Equity ETF", "price": 52.75, "price_date": "2026-11-19"},
    "INTL": {"fund": "Demo International Equity ETF", "price": 27.30, "price_date": "2026-11-19"},
    "EMEQ": {"fund": "Demo Emerging Markets ETF", "price": 24.15, "price_date": "2026-11-19"},
    "REIT": {"fund": "Demo Global REIT ETF", "price": 22.60, "price_date": "2026-11-14"},
}

# Fictional households. Money amounts in CAD; spending needs in today's dollars.
HOUSEHOLDS = [
    {
        "id": "H1", "name": "Maya", "summary": "28, early-career saver, renting in Toronto",
        "age": 28, "retired": False, "retirement_age": 65, "plan_to_age": 95,
        "gross_income": 72000, "essential_monthly": 2600, "monthly_spending": 4300,
        "liquid_savings": 9000, "investable": {"TFSA": 24000},
        "monthly_contribution": 750,
        "mortgage_payment": 0, "other_debt_payment": 350,
        "card_balance": 1800, "card_limit": 6000,
        "dependents": 0, "life_insurance": False, "disability_insurance": False,
        "retirement_spending": 48000, "retirement_other_income": 18000,
        "risk_profile": "growth",
    },
    {
        "id": "H2", "name": "The Okafor family", "summary": "38 and 36, two children, mortgage",
        "age": 38, "retired": False, "retirement_age": 63, "plan_to_age": 95,
        "gross_income": 165000, "essential_monthly": 7800, "monthly_spending": 10900,
        "liquid_savings": 14000, "investable": {"RRSP": 80000, "TFSA": 40000},
        "monthly_contribution": 2000,
        "mortgage_payment": 3100, "other_debt_payment": 600,
        "card_balance": 4500, "card_limit": 20000,
        "dependents": 2, "life_insurance": True, "disability_insurance": False,
        "retirement_spending": 78000, "retirement_other_income": 38000,
        "risk_profile": "balanced",
    },
    {
        "id": "H3", "name": "Daniel", "summary": "55, pre-retiree planning to stop at 62",
        "age": 55, "retired": False, "retirement_age": 62, "plan_to_age": 95,
        "gross_income": 128000, "essential_monthly": 4800, "monthly_spending": 6900,
        "liquid_savings": 40000, "investable": {"RRSP": 450000, "TFSA": 95000, "Non-registered": 95000},
        "monthly_contribution": 2000,
        "mortgage_payment": 1200, "other_debt_payment": 0,
        "card_balance": 900, "card_limit": 15000,
        "dependents": 0, "life_insurance": True, "disability_insurance": True,
        "retirement_spending": 60000, "retirement_other_income": 28000,
        "risk_profile": "balanced",
    },
    {
        "id": "H4", "name": "Rosa and Luis", "summary": "67 and 66, retired, drawing from savings",
        "age": 67, "retired": True, "retirement_age": 65, "plan_to_age": 95,
        "gross_income": 58000, "essential_monthly": 3900, "monthly_spending": 5000,
        "liquid_savings": 30000, "investable": {"RRIF": 500000, "TFSA": 140000, "Non-registered": 140000},
        "monthly_contribution": 0,
        "mortgage_payment": 0, "other_debt_payment": 0,
        "card_balance": 500, "card_limit": 10000,
        "dependents": 0, "life_insurance": True, "disability_insurance": False,
        "retirement_spending": 68000, "retirement_other_income": 36000,
        "risk_profile": "moderately_conservative",
    },
    {
        "id": "H5", "name": "Priya", "summary": "33, high income, high spending, carrying card debt",
        "age": 33, "retired": False, "retirement_age": 62, "plan_to_age": 95,
        "gross_income": 140000, "essential_monthly": 5200, "monthly_spending": 9800,
        "liquid_savings": 3000, "investable": {"TFSA": 35000},
        "monthly_contribution": 300,
        "mortgage_payment": 2900, "other_debt_payment": 1100,
        "card_balance": 14000, "card_limit": 18000,
        "dependents": 0, "life_insurance": False, "disability_insurance": False,
        "retirement_spending": 75000, "retirement_other_income": 22000,
        "risk_profile": "aggressive_growth",
    },
    {
        "id": "H6", "name": "Sam", "summary": "45, self-employed, one child",
        "age": 45, "retired": False, "retirement_age": 65, "plan_to_age": 95,
        "gross_income": 96000, "essential_monthly": 4100, "monthly_spending": 6800,
        "liquid_savings": 25000, "investable": {"RRSP": 150000, "TFSA": 60000},
        "monthly_contribution": 1000,
        "mortgage_payment": 1900, "other_debt_payment": 0,
        "card_balance": 2000, "card_limit": 10000,
        "dependents": 1, "life_insurance": True, "disability_insurance": False,
        "retirement_spending": 56000, "retirement_other_income": 20000,
        "risk_profile": "growth",
    },
]
HOUSEHOLD_BY_ID = {h["id"]: h for h in HOUSEHOLDS}

# One managed account per household. Each starts on its model portfolio and is
# then moved by a mock market move ("drift"), so every account tells a
# different story: cash-flow-only investing, a band breach, realized gains,
# a withdrawal, a client restriction and a stale price, and no action needed.
ACCOUNT_SCENARIOS = [
    {"id": "A1", "household": "H1", "type": "TFSA", "value": 24000, "cash_flow": 600,
     "move": {"equity": 1.02, "other": 1.00}, "gain": 0.06, "restrictions": [],
     "story": "Monthly deposit, small drift: invest the deposit into underweights, no sells."},
    {"id": "A2", "household": "H2", "type": "RRSP", "value": 80000, "cash_flow": 0,
     "move": {"equity": 1.15, "other": 0.97, "CEQ": 1.45}, "gain": 0.12, "restrictions": [],
     "story": "Equity rally breached the 5/25 bands: trim equity, top up bonds."},
    {"id": "A3", "household": "H3", "type": "Non-registered", "value": 95000, "cash_flow": 0,
     "move": {"equity": 1.12, "other": 0.98, "USEQ": 1.55, "INTL": 1.25}, "gain": 0.25, "restrictions": [],
     "story": "Taxable account: same breach, so the plan reports the capital gain it would realize (ACB method)."},
    {"id": "A4", "household": "H4", "type": "RRIF", "value": 500000, "cash_flow": -3000,
     "move": {"equity": 1.03, "other": 1.00}, "gain": 0.10, "restrictions": [],
     "story": "Monthly withdrawal: raise cash from the most overweight holdings first."},
    {"id": "A5", "household": "H5", "type": "TFSA", "value": 35000, "cash_flow": 300,
     "move": {"equity": 0.90, "other": 1.01, "REIT": 1.60}, "gain": 0.04, "restrictions": ["EMEQ"],
     "story": "Client asked for no new emerging-markets purchases; REIT quote is stale."},
    {"id": "A6", "household": "H6", "type": "RRSP", "value": 150000, "cash_flow": 0,
     "move": {"equity": 1.01, "other": 1.00}, "gain": 0.08, "restrictions": [],
     "story": "Within bands and no cash flow: the engine should do nothing."},
]

MODEL_INVENTORY = [
    {
        "id": "M1", "name": "Portfolio optimizer", "tier": "High",
        "purpose": "Builds the five model portfolios: highest expected return for each risk profile's volatility budget.",
        "inputs": "Capital market assumptions (returns, volatilities, correlations); weight bounds; equity cap.",
        "outputs": "Target weights and expected risk and return per profile.",
        "assumptions": "Returns are summarized by means and covariances; assumptions are long-run and stable.",
        "limitations": "Mean-variance weights are sensitive to expected-return inputs; tails and liquidity are not modelled.",
        "tests": "Constraint checks, frontier monotonicity, resampling stability, input-shock sensitivity.",
        "monitoring": "Weight change between reviews; realized vs expected volatility per profile.",
    },
    {
        "id": "M2", "name": "Monte Carlo goal planner", "tier": "High",
        "purpose": "Estimates the probability that a household's plan lasts to the planning age.",
        "inputs": "Household balances, contributions, retirement age and spending; model portfolio; inflation; fees.",
        "outputs": "Probability of success, wealth percentiles by age, sustainable spending at 90% success.",
        "assumptions": "Lognormal annual asset returns, annual rebalancing, constant real spending, deterministic inflation.",
        "limitations": "No taxes or benefit timing; inflation is fixed; return model can be too optimistic in its tails.",
        "tests": "Closed-form check at zero volatility, convergence vs path count, calibration (Brier score), stress tests.",
        "monitoring": "Calibration of predicted vs realized outcomes as client histories accumulate.",
    },
    {
        "id": "M3", "name": "Financial health score", "tier": "Medium",
        "purpose": "Summarizes a household's financial position in a 0-100 score with ranked next steps.",
        "inputs": "Income, spending, savings, debt payments, card use, insurance, retirement probability (M2).",
        "outputs": "Score, band, component points, next best actions with point gains.",
        "assumptions": "Component thresholds are illustrative rules of thumb, not RBC's methodology.",
        "limitations": "Rule-based weights; no behavioural data; self-reported inputs.",
        "tests": "Bounds per component, ideal and worst-case households, monotonicity, action ranking.",
        "monitoring": "Score distribution drift; share of households moving bands after actions.",
    },
    {
        "id": "M4", "name": "Rebalancing and order engine", "tier": "High",
        "purpose": "Turns drift and cash flows into whole-unit orders that pass pre-trade checks.",
        "inputs": "Holdings, cash, prices and price dates, model weights, client restrictions, cash flows.",
        "outputs": "Orders with check results, post-trade drift, turnover, realized gain (taxable accounts).",
        "assumptions": "5/25 tolerance bands; sells before buys; 0.5% cash buffer; $100 minimum order.",
        "limitations": "Average-cost ACB only; no tax-loss harvesting or superficial-loss handling yet.",
        "tests": "No-trade inside bands, no shorts, restricted buys blocked, stale prices blocked, cash never negative.",
        "monitoring": "Blocked-order rate by check; post-trade drift; turnover vs policy budget.",
    },
]


def household(household_id: str) -> dict:
    return copy.deepcopy(HOUSEHOLD_BY_ID[household_id])


def total_investable(h: dict) -> float:
    return float(sum(h["investable"].values()))


def build_accounts(model_weights: dict[str, dict[str, float]]) -> list[dict]:
    """Materialize the mock accounts from their scenarios and the model weights."""
    accounts = []
    for sc in ACCOUNT_SCENARIOS:
        h = HOUSEHOLD_BY_ID[sc["household"]]
        target = model_weights[h["risk_profile"]]
        raw = {}
        for code, w in target.items():
            default = sc["move"]["equity"] if GROUPS[code] == "Equity" else sc["move"]["other"]
            raw[code] = w * sc["move"].get(code, default)
        scale = sc["value"] * 0.995 / sum(raw.values())
        holdings, acb = {}, {}
        for code, v in raw.items():
            price = FUNDS[code]["price"]
            units = int(v * scale // price)
            if units > 0:
                holdings[code] = units
                acb[code] = round(price / (1 + sc["gain"]), 4)
        invested = sum(u * FUNDS[c]["price"] for c, u in holdings.items())
        accounts.append({
            "id": sc["id"], "household": sc["household"], "owner": h["name"],
            "type": sc["type"], "risk_profile": h["risk_profile"],
            "cash": round(sc["value"] - invested, 2), "holdings": holdings, "acb": acb,
            "cash_flow": sc["cash_flow"], "restrictions": list(sc["restrictions"]),
            "story": sc["story"],
        })
    return accounts


def validate_assumptions() -> list[dict]:
    """Data-quality checks run before any model uses the assumptions."""
    checks = []

    def add(name, ok, detail, fail_status="FAIL"):
        checks.append({"check": name, "status": "PASS" if ok else fail_status, "detail": detail})

    eig = float(np.linalg.eigvalsh(CORR).min())
    add("Correlation matrix is symmetric", bool(np.allclose(CORR, CORR.T)), "max |C - C'| = %.1e" % np.abs(CORR - CORR.T).max())
    add("Correlation diagonal is 1", bool(np.allclose(np.diag(CORR), 1.0)), "all nine diagonal entries equal 1")
    add("Correlation matrix is positive definite", eig > 0, "smallest eigenvalue %.4f" % eig)
    add("Volatilities are positive", bool((SIGMA > 0).all()), "min %.1f%%" % (SIGMA.min() * 100))
    add("Expected returns in a plausible range", bool(((MU > 0) & (MU < 0.15)).all()), "%.1f%% to %.1f%%" % (MU.min() * 100, MU.max() * 100))
    lo = sum(b[0] for b in BOUNDS.values())
    hi = sum(b[1] for b in BOUNDS.values())
    add("Weight bounds admit a fully invested portfolio", lo <= 1 <= hi, "sum of minimums %.2f, of maximums %.2f" % (lo, hi))
    stale = [c for c, f in FUNDS.items() if f["price_date"] != AS_OF.isoformat()]
    add("Prices are dated today", not stale,
        ("stale: %s; orders in it are blocked at the pre-trade check" % ", ".join(stale)) if stale
        else "all quotes dated %s" % AS_OF.isoformat(), fail_status="WARN")
    for h in HOUSEHOLDS:
        ok = (h["age"] < h["plan_to_age"]) and all(v >= 0 for v in h["investable"].values()) and h["gross_income"] > 0
        ok = ok and (h["retired"] or h["retirement_age"] > h["age"]) and h["risk_profile"] in PROFILE_BY_ID
        add("Household %s inputs are consistent" % h["id"], ok, h["summary"])
    return checks
