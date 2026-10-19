"""Choose a small, material sample of merchandise, with reproducible reasons."""
from math import isfinite

from .sales_actions import _eligible, _trend, _fmt

FOCUS_VERSION = "sales-focus-v2"
# Require a material share of merchandise sales (or of the leading product).
STORE_FLOOR = .002
LEADER_FLOOR = .05
NON_MERCHANDISE_IDS = {"POSTAGE", "BANK CHARGES", "AMAZONFEE", "AMAZON FEE", "MANUAL"}


def number(value):
    return isinstance(value, (int, float)) and isfinite(value) and value >= 0


def merchandise(product):
    # Exact matches only: e.g. a real "POSTAGE STAMP SET" is still merchandise.
    return _eligible(product) and str(product["id"]).strip().upper() not in NON_MERCHANDISE_IDS


def select_focus(products, summary, parameters):
    eligible = [p for p in products if merchandise(p)]
    monetary = bool(eligible) and all(number(p.get("amount")) for p in eligible) and sum(p["amount"] for p in eligible) > 0
    unit = summary.get("unit", "")
    comparable_quantity = bool(unit and unit not in {"原始商品单位", "未提供", "未知", "未指定"})
    metric = "amount" if monetary else "quantity" if comparable_quantity else "active_days"

    def raw_value(p):
        if metric == "active_days":
            return sum(number(d.get("quantity")) and d["quantity"] > 0 for d in p.get("daily", []))
        return p.get(metric) or 0

    values = {p["id"]: raw_value(p) for p in eligible}
    def value(p):
        return values[p["id"]]

    total = sum(value(p) for p in eligible)
    leaders = sorted((p for p in eligible if value(p) > 0), key=lambda p: (-value(p), p["id"]))
    if not leaders or total <= 0:
        return [], {}
    largest = value(leaders[0])
    floor = max(total * STORE_FLOOR, largest * LEADER_FLOOR)
    ranks, previous_value, rank = {}, None, 0
    for index, p in enumerate(leaders, 1):
        if value(p) != previous_value:
            rank = index
        ranks[p["id"]], previous_value = rank, value(p)
    candidates = []

    def add(p, category, label, reason, score, evidence):
        candidates.append({"id": p["id"], "category": category, "label": label,
                           "reason": reason, "score": score, "evidence": evidence})

    for p in eligible:
        v, rank = value(p), ranks.get(p["id"])
        if v >= floor and (metric != "active_days" or v >= 14):
            if metric == "amount":
                share = v / total * 100
                reason = f"本月商品销售额排名第{rank}，占商品销售额 {share:.1f}%。"
            elif metric == "quantity":
                reason = f"本月售出 {_fmt(v)} {unit}，商品销量排名第{rank}。"
            else:
                reason = f"本月有 {int(v)} 天卖出，销售天数在商品中排名第{rank}。"
            add(p, "leader", "主要销售商品", reason, v * .15,
                {"metric": metric, "value": v, "total": total, "rank": rank})

        # Unknown units cannot be summed across products to estimate impact.
        if metric == "active_days":
            continue
        contribution = p.get("contribution") or {}
        q = p.get("quantity", 0)
        old_q = contribution.get("previous_quantity") or 0
        old_amount = contribution.get("previous_amount")
        price = 1
        if monetary:
            price = p["amount"] / q if q > 0 else 0
            if number(old_amount) and old_q > 0:
                price = (p["amount"] + old_amount) / (q + old_q)
        if monetary and price <= 0:
            continue

        trend = None
        if summary.get("complete_month") and parameters.get("complete_coverage"):
            trend = _trend(p, parameters) if p.get("daily") else None
        if trend:
            impact = trend["quantity_impact"] * price * 4
            if impact >= floor:
                direction = "增长" if trend["signal"] == "growth" else "下降"
                add(p, trend["signal"], f"连续四周{direction}", trend["reason"], impact,
                    {"period": trend["period"], "quantities": trend["quantities"]})
        elif not p.get("daily"):
            c = p.get("comparison") or {}
            previous, current = c.get("previous_quantity"), c.get("current_quantity")
            if c.get("status") == "available" and number(previous) and previous > 0 and number(current):
                delta = current - previous
                impact = abs(delta) * price
                if abs(delta) >= 3 and abs(delta / previous) >= .25 and impact >= floor:
                    category = "growth" if delta > 0 else "decline"
                    reason = f"本月售出 {_fmt(current)}，上月 {_fmt(previous)}，{'多' if delta > 0 else '少'}卖 {_fmt(abs(delta))}。"
                    add(p, category, "本月销量增长" if delta > 0 else "本月销量下降", reason, impact,
                        {"period": [c["previous_start"], c["current_end"]], "quantities": [previous, current]})

        events = [a for a in p.get("anomalies", []) if number(a.get("actual")) and number(a.get("reference"))]
        if events:
            event = max(events, key=lambda a: (abs(a["actual"] - a["reference"]), a["date"]))
            delta = abs(event["actual"] - event["reference"])
            impact = delta * price
            if delta >= 3 and impact >= floor / 4:
                reason = f"{event['date'][5:]} 售出 {_fmt(event['actual'])}。"
                if q > 0:
                    reason = f"{event['date'][5:]} 售出 {_fmt(event['actual'])}，占本月销量 {event['actual'] / q:.1%}。"
                add(p, "anomaly", "单日销量明显变化", reason, impact, dict(event))

    if not candidates:
        return [], {}
    # Keep the main sales product visible; diversify subsequent choices only
    # among candidates that already meet the materiality and evidence gates.
    first = next((c for c in candidates if c["category"] == "leader" and c["id"] == leaders[0]["id"]), None)
    chosen = [first] if first else []
    counts = {"leader": 1} if first else {}
    used = {first["id"]} if first else set()
    while len(chosen) < 5:
        remaining = [c for c in candidates if c["id"] not in used]
        if not remaining:
            break
        best = min(remaining, key=lambda c: (-c["score"] * (.45 ** counts.get(c["category"], 0)), c["id"], c["category"]))
        chosen.append(best)
        used.add(best["id"])
        counts[best["category"]] = counts.get(best["category"], 0) + 1
    return [c["id"] for c in chosen], {c["id"]: c for c in chosen}


def focus_view(report, output=None):
    result = _focus_view(report)
    if output is None:
        return result
    from .sales_order_focus import order_focus
    return order_focus(result, output)


def _focus_view(report):
    if report.get("focus_version") == FOCUS_VERSION:
        return report
    ids, selected = select_focus(report.get("products", []), report.get("summary", {}), report.get("parameters", {}))
    products = []
    for original in report.get("products", []):
        p = dict(original)
        p.pop("focus", None)
        p.pop("focus_reason", None)
        if p["id"] in selected:
            choice = selected[p["id"]]
            p["focus"] = {k: v for k, v in choice.items() if k not in {"id", "score"}}
            p["focus_reason"] = choice["reason"]
        products.append(p)
    return {**report, "products": products, "highlights": ids, "focus_version": FOCUS_VERSION}
