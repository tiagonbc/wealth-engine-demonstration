"""Financial health score (0-100).

Six transparent components, each scored on a straight line between a
"no points" and a "full points" threshold. The thresholds are illustrative
rules of thumb for the demonstration, not RBC's methodology. Every component
returns the action that would raise it, and actions are ranked by the points
they would add.
"""
from __future__ import annotations


def _linear(x: float, zero_at: float, full_at: float) -> float:
    """0 at `zero_at`, 1 at `full_at`, clipped; works in either direction."""
    if full_at == zero_at:
        return 1.0 if x >= full_at else 0.0
    t = (x - zero_at) / (full_at - zero_at)
    return max(0.0, min(1.0, t))


BANDS = [(80, "Strong"), (60, "Steady"), (40, "Stretched"), (0, "Vulnerable")]


def band(score: float) -> str:
    for cut, name in BANDS:
        if score >= cut:
            return name
    return BANDS[-1][1]


def score_household(h: dict, retirement_probability: float) -> dict:
    income = h["gross_income"]
    comps = []

    # 1. Saving (working) or drawdown sustainability (retired)
    if h["retired"]:
        investable = sum(h["investable"].values())
        draw = max(h["retirement_spending"] - h["retirement_other_income"], 0)
        rate = draw / investable if investable else 1.0
        f = _linear(rate, 0.07, 0.04)
        comps.append({
            "id": "saving", "name": "Withdrawal rate", "max": 20, "value": rate, "display": "%.1f%% a year" % (rate * 100),
            "rule": "Full points at 4% or less of savings drawn per year; none at 7%.", "points": 20 * f,
            "action": "Trim planned withdrawals toward %s a year (4%% of savings)" % _money(0.04 * investable),
        })
    else:
        rate = 12 * h["monthly_contribution"] / income
        f = _linear(rate, 0.0, 0.15)
        target = 0.15 * income / 12
        comps.append({
            "id": "saving", "name": "Savings rate", "max": 20, "value": rate, "display": "%.1f%% of gross income" % (rate * 100),
            "rule": "Full points at 15% of gross income saved; none at 0%.", "points": 20 * f,
            "action": "Raise automatic saving from %s to %s a month" % (_money(h["monthly_contribution"]), _money(target)),
        })

    # 2. Emergency fund
    months = h["liquid_savings"] / h["essential_monthly"]
    need = 6 if (h["dependents"] or "self-employed" in h.get("summary", "")) else 3
    f = _linear(months, 0, need)
    comps.append({
        "id": "emergency", "name": "Emergency fund", "max": 15, "value": months,
        "display": "%.1f months of essential costs" % months,
        "rule": "Full points at %d months of essential costs in cash (6 with dependents or variable income)." % need,
        "points": 15 * f,
        "action": "Build cash reserves to %s (%d months)" % (_money(need * h["essential_monthly"]), need),
    })

    # 3. Total debt service ratio
    card_payment = 0.03 * h["card_balance"]
    tds = 12 * (h["mortgage_payment"] + h["other_debt_payment"] + card_payment) / income
    f = _linear(tds, 0.50, 0.30)
    comps.append({
        "id": "debt", "name": "Debt service", "max": 20, "value": tds,
        "display": "%.0f%% of gross income" % (tds * 100),
        "rule": "Full points at 30% or less of gross income going to debt payments; none at 50%.",
        "points": 20 * f,
        "action": "Pay down non-mortgage debt first, highest interest rate first",
    })

    # 4. Retirement readiness (from the Monte Carlo planner)
    f = _linear(retirement_probability, 0.40, 0.85)
    comps.append({
        "id": "retirement", "name": "Retirement readiness", "max": 25, "value": retirement_probability,
        "display": "%.0f%% chance the plan lasts to %d" % (retirement_probability * 100, h["plan_to_age"]),
        "rule": "Full points at an 85% Monte Carlo success rate; none at 40%.", "points": 25 * f,
        "action": ("Lower planned spending or review the portfolio mix (see what-if grid)" if h["retired"]
                   else "Save more, retire later or plan to spend less (see what-if grid)"),
    })

    # 5. Credit utilization
    util = h["card_balance"] / h["card_limit"] if h["card_limit"] else 0.0
    f = _linear(util, 0.90, 0.30)
    comps.append({
        "id": "credit", "name": "Credit card use", "max": 10, "value": util,
        "display": "%.0f%% of limit" % (util * 100),
        "rule": "Full points at 30% or less of the card limit in use; none at 90%.", "points": 10 * f,
        "action": "Bring the card balance under %s (30%% of limit)" % _money(0.3 * h["card_limit"]),
    })

    # 6. Protection
    if h["retired"]:
        pts, display, action = 10.0, "No earned income to protect", "No action"
    elif h["dependents"]:
        pts = 5.0 * h["life_insurance"] + 5.0 * h["disability_insurance"]
        have = [n for n, ok in (("life", h["life_insurance"]), ("disability", h["disability_insurance"])) if ok]
        display = ("Has " + " and ".join(have) + " cover") if have else "No life or disability cover"
        missing = [n for n, ok in (("life", h["life_insurance"]), ("disability", h["disability_insurance"])) if not ok]
        action = "Review %s cover with an advisor" % " and ".join(missing) if missing else "No action"
    else:
        pts = 10.0 * h["disability_insurance"]
        display = "Has disability cover" if h["disability_insurance"] else "No disability cover"
        action = "Look into disability cover for income protection" if not h["disability_insurance"] else "No action"
    comps.append({
        "id": "protection", "name": "Protection", "max": 10, "value": pts / 10, "display": display,
        "rule": "Income protection for workers; life and disability cover when someone depends on that income.",
        "points": pts, "action": action,
    })

    for c in comps:
        c["points"] = round(c["points"], 1)
        c["gain"] = round(c["max"] - c["points"], 1)
    score = round(sum(c["points"] for c in comps), 1)
    actions = sorted(
        [{"component": c["name"], "action": c["action"], "points": c["gain"]} for c in comps if c["gain"] >= 0.5],
        key=lambda a: -a["points"],
    )
    return {"score": score, "band": band(score), "components": comps, "next_best_actions": actions[:3]}


def _money(x: float) -> str:
    return "${:,.0f}".format(round(x, -1))
