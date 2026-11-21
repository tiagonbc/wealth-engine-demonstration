"""Rebalancing and order generation with pre-trade checks.

Policy (illustrative):
- Tolerance bands: an asset class breaches when its drift exceeds 5 percentage
  points or 25% of its target weight, whichever is smaller (the "5/25" rule).
- Cash flows always trigger a trade: deposits buy the most underweight
  holdings; withdrawals sell the most overweight ones.
- Whole units only, sells before buys, a 0.5% cash buffer, $100 minimum order.
- Client restrictions block new purchases of an asset class; its target is
  redistributed pro rata to the other equity classes. Existing units may still
  be sold.

Every order then passes through the pre-trade checks below; a failed check
blocks that order, and the account-level summary reports the drift that
remains.
"""
from __future__ import annotations

import math
from datetime import date, timedelta

from . import data

BAND_ABS = 0.05
BAND_REL = 0.25
CASH_BUFFER = 0.005
MIN_ORDER = 100.0
MIN_TRADE_WEIGHT = 0.005  # on a band rebalance, skip gaps under 0.5% of the account
MAX_ORDER_SHARE = 0.35  # orders above this share of the account go to review


def band_for(target: float) -> float:
    return min(BAND_ABS, BAND_REL * target) if target > 0 else 0.005


def business_days_between(d0: date, d1: date) -> int:
    days, d = 0, d0
    while d < d1:
        d += timedelta(days=1)
        if d.weekday() < 5:
            days += 1
    return days


def effective_targets(target: dict, restrictions: list[str]) -> dict:
    t = dict(target)
    for code in restrictions:
        freed = t.get(code, 0.0)
        t[code] = 0.0
        peers = [c for c in t if data.GROUPS[c] == data.GROUPS[code] and c not in restrictions and t[c] > 0]
        base = sum(t[c] for c in peers)
        for c in peers:
            t[c] += freed * t[c] / base
    return t


def _weights(holdings: dict, prices: dict, total: float) -> dict:
    return {c: holdings.get(c, 0) * prices[c]["price"] / total for c in data.CODES}


def plan_rebalance(account: dict, target: dict, prices: dict | None = None, as_of: date = data.AS_OF) -> dict:
    prices = prices or data.FUNDS
    holdings = dict(account["holdings"])
    cash = float(account["cash"]) + float(account.get("cash_flow", 0))
    invested = sum(u * prices[c]["price"] for c, u in holdings.items())
    total = invested + cash
    tgt = effective_targets(target, account.get("restrictions", []))
    pre_w = _weights(holdings, prices, total)
    drift = {c: pre_w[c] - tgt[c] for c in data.CODES}
    breaches = [c for c in data.CODES if abs(drift[c]) > band_for(tgt[c])]
    has_flow = abs(account.get("cash_flow", 0)) >= MIN_ORDER

    result = {
        "account": account["id"], "total_value": round(total, 2),
        "targets": {c: round(v, 6) for c, v in tgt.items()},
        "pre_weights": {c: round(v, 6) for c, v in pre_w.items()},
        "drift": {c: round(v, 6) for c, v in drift.items()},
        "bands": {c: round(band_for(tgt[c]), 6) for c in data.CODES},
        "breaches": breaches, "trigger": None, "orders": [], "skipped": [],
    }
    if not breaches and not has_flow:
        result.update(trigger="none", post_weights=result["pre_weights"], max_post_drift=max(abs(v) for v in drift.values()),
                      turnover=0.0, realized_gain=0.0, cash_after=round(cash, 2), status="No action")
        return result

    result["trigger"] = "bands" if breaches else ("deposit" if account["cash_flow"] > 0 else "withdrawal")
    investable_total = total * (1 - CASH_BUFFER)
    desired = {c: tgt[c] * investable_total for c in data.CODES}
    current = {c: holdings.get(c, 0) * prices[c]["price"] for c in data.CODES}
    gap = {c: desired[c] - current[c] for c in data.CODES}

    if not breaches:
        # cash-flow-only: move only in the direction of the flow
        if account["cash_flow"] > 0:
            gap = {c: max(g, 0.0) for c, g in gap.items()}
            budget = max(cash - total * CASH_BUFFER, 0.0)
            pos = sum(gap.values())
            gap = {c: g * min(1.0, budget / pos) if pos else 0.0 for c, g in gap.items()}
        else:
            need = max(total * CASH_BUFFER - cash, 0.0)
            neg = {c: max(-g, 0.0) for c, g in gap.items()}
            s = sum(neg.values())
            if s >= need and s > 0:
                gap = {c: -neg[c] * need / s for c in data.CODES}
            else:  # not enough overweight: sell pro rata to holdings
                inv = sum(current.values())
                gap = {c: -need * current[c] / inv for c in data.CODES}

    orders = []
    for c in data.CODES:
        g = gap[c]
        price = prices[c]["price"]
        if abs(g) < MIN_ORDER:
            if abs(g) >= 1:
                result["skipped"].append({"code": c, "value": round(g, 2), "reason": "below $%d minimum" % MIN_ORDER})
            continue
        if breaches and abs(g) / total < MIN_TRADE_WEIGHT:
            result["skipped"].append({"code": c, "value": round(g, 2),
                                      "reason": "gap under %.1f%% of the account" % (MIN_TRADE_WEIGHT * 100)})
            continue
        if g < 0:
            raw = -g / price
            # withdrawals round up so the cash is really raised; rebalances round down
            units = math.ceil(raw) if result["trigger"] == "withdrawal" else int(raw)
            units = min(units, holdings.get(c, 0))  # never generate a short; C3 re-checks
            side = "SELL"
        else:
            units = int(g // price)
            side = "BUY"
        if units <= 0:
            continue
        orders.append({"code": c, "fund": prices[c]["fund"], "side": side, "units": units,
                       "price": price, "value": round(units * price, 2)})

    # sells first, then buys funded by available cash
    orders.sort(key=lambda o: (o["side"] != "SELL", -o["value"]))
    checks_run = []
    cash_avail = cash
    post_holdings = dict(holdings)
    realized = 0.0
    for o in orders:
        c = o["code"]
        checks = []

        def chk(cid, name, ok, detail, fail="BLOCK"):
            checks.append({"id": cid, "name": name, "status": "PASS" if ok else fail, "detail": detail})

        restricted = c in account.get("restrictions", [])
        chk("C1", "Client restriction", not (restricted and o["side"] == "BUY"),
            "no new purchases allowed in %s" % c if restricted else "no restriction on %s" % c)
        age = business_days_between(date.fromisoformat(prices[c]["price_date"]), as_of)
        chk("C2", "Price freshness", age <= 1, "quote is %d business day(s) old" % age)
        held = holdings.get(c, 0)
        chk("C3", "No short sale", o["side"] == "BUY" or o["units"] <= held,
            "sell %d of %d units held" % (o["units"], held) if o["side"] == "SELL" else "buy order")
        share = o["value"] / total
        chk("C4", "Order size", share <= MAX_ORDER_SHARE, "%.1f%% of account value" % (share * 100), fail="REVIEW")
        before = abs(drift[c])
        after_w = (held + (o["units"] if o["side"] == "BUY" else -o["units"])) * o["price"] / total
        after = abs(after_w - tgt[c])
        toward = after <= before + 1e-9
        chk("C5", "Moves toward target", toward, "drift %.2f%% -> %.2f%%" % (before * 100, after * 100))
        if o["side"] == "BUY":
            ok_cash = o["value"] <= cash_avail - total * CASH_BUFFER + 1e-6
            if not ok_cash:
                affordable = int(max(cash_avail - total * CASH_BUFFER, 0) // o["price"])
                if affordable > 0 and all(x["status"] == "PASS" for x in checks):
                    o["units"] = affordable
                    o["value"] = round(affordable * o["price"], 2)
                    ok_cash = True
            chk("C6", "Cash available", ok_cash, "buffer kept at %.1f%%" % (CASH_BUFFER * 100))
        else:
            chk("C6", "Cash available", True, "sell order raises cash")
        status = "BLOCK" if any(x["status"] == "BLOCK" for x in checks) else (
            "REVIEW" if any(x["status"] == "REVIEW" for x in checks) else "PASS")
        o["checks"] = checks
        o["status"] = status
        if status == "PASS":
            if o["side"] == "SELL":
                cash_avail += o["value"]
                post_holdings[c] = held - o["units"]
                if account["type"] == "Non-registered":
                    acb = account["acb"].get(c, o["price"])
                    realized += (o["price"] - acb) * o["units"]
            else:
                cash_avail -= o["value"]
                post_holdings[c] = held + o["units"]
        checks_run.append(o)

    post_w = _weights(post_holdings, prices, total)
    post_drift = {c: post_w[c] - tgt[c] for c in data.CODES}
    traded = sum(o["value"] for o in orders if o["status"] == "PASS")
    result.update(
        orders=checks_run,
        post_weights={c: round(v, 6) for c, v in post_w.items()},
        post_drift={c: round(v, 6) for c, v in post_drift.items()},
        max_post_drift=max(abs(v) for v in post_drift.values()),
        turnover=round(traded / total, 6) if total else 0.0,
        realized_gain=round(realized, 2),
        cash_after=round(cash_avail, 2),
        status=("Orders ready" if all(o["status"] == "PASS" for o in checks_run)
                else "Orders ready, some held by checks"),
    )
    return result
