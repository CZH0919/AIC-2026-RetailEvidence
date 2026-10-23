"""Select up to three material, product-specific actions from saved sales evidence."""

from datetime import date, timedelta
from hashlib import sha256
from math import isfinite
from statistics import mean, median, pstdev

ACTION_VERSION = "sales-actions-v2"
# A movement must affect at least 0.2% of store sales, or 5% of its largest
# product's sales. Percent growth alone cannot qualify a small outlier.
STORE_IMPACT_FLOOR = 0.002
LEADER_IMPACT_FLOOR = 0.05
MIN_CHANGE = 0.25
NON_MERCHANDISE_NAMES = {
    "MANUAL", "POSTAGE", "DOTCOM POSTAGE", "BANK CHARGES", "DISCOUNT", "MAILOUT",
    "AMAZON FEE", "AMAZONFEE", "运费", "邮费", "手续费", "记账", "折扣",
}


def _number(value):
    return isinstance(value, (int, float)) and isfinite(value) and value >= 0


def _eligible(product):
    item_type = product.get("item_type") or {}
    return (
        item_type.get("kind", "unknown") not in {"fee_service", "accounting"}
        and item_type.get("source") != "conflicting_types"
        and str(product.get("name", "")).strip().upper() not in NON_MERCHANDISE_NAMES
        and _number(product.get("quantity"))
    )


def _fmt(value):
    return f"{value:,.2f}".rstrip("0").rstrip(".") if value % 1 else f"{value:,.0f}"


def _weeks(product, params):
    daily = product.get("daily", [])[-28:]
    if len(daily) != 28 or not all(_number(p.get("quantity")) for p in daily):
        return None
    blocked = set(params.get("missing_dates") or []) | set(params.get("closed_dates") or [])
    start = date.fromisoformat(daily[0]["date"])
    if any(p["date"] != (start + timedelta(days=i)).isoformat() or p["date"] in blocked
           for i, p in enumerate(daily)):
        return None
    values = [p["quantity"] for p in daily]
    # Sparse orders are not evidence of sustained weekly demand.
    if sum(v > 0 for v in values) < 14:
        return None
    return daily, [sum(values[i:i + 7]) for i in range(0, 28, 7)]


def _trend(product, params):
    evidence = _weeks(product, params)
    if not evidence:
        return None
    daily, weeks = evidence
    if min(weeks) <= 0 or abs(weeks[-1] - weeks[0]) < 3:
        return None
    direction = 1 if weeks[-1] > weeks[0] else -1
    if any((b - a) * direction <= 0 for a, b in zip(weeks, weeks[1:])):
        return None
    if abs(weeks[-1] / weeks[0] - 1) < MIN_CHANGE:
        return None
    # Remove identified abnormal days and verify that the direction survives.
    abnormal = {a["date"] for a in product.get("anomalies", [])}
    adjusted = []
    for i in range(0, 28, 7):
        normal = [d["quantity"] for d in daily[i:i + 7] if d["date"] not in abnormal]
        if len(normal) < 5:
            return None
        adjusted.append(mean(normal) * 7)
    if any((b - a) * direction <= 0 for a, b in zip(adjusted, adjusted[1:])):
        return None
    if direction > 0 and max(d["quantity"] for d in daily[-7:]) > weeks[-1] / 2:
        return None
    return {
        "signal": "growth" if direction > 0 else "decline",
        "period": [daily[0]["date"], daily[-1]["date"]],
        "quantities": weeks,
        "quantity_impact": abs(weeks[-1] - weeks[0]),
        "reason": f"{daily[0]['date'][5:]} 至 {daily[-1]['date'][5:]}，四周销量依次为 "
                  + " → ".join(_fmt(v) for v in weeks) + "。",
    }


def _spike(product, params):
    anomalies = [a for a in product.get("anomalies", [])
                 if _number(a.get("actual")) and _number(a.get("reference"))
                 and a["actual"] > a["reference"]]
    if not 1 <= len(anomalies) <= 2:
        return None
    peak = max(anomalies, key=lambda a: a["actual"] - a["reference"])
    blocked = set(params.get("missing_dates") or []) | set(params.get("closed_dates") or [])
    abnormal = {a["date"] for a in product.get("anomalies", [])}
    history = [d["quantity"] for d in product.get("daily", [])
               if d["date"] < peak["date"] and d["date"] not in abnormal | blocked
               and _number(d.get("quantity"))][-21:]
    if len(history) < 14 or sum(v > 0 for v in history) < len(history) / 2:
        return None
    baseline = median(history)
    if baseline <= 0 or not mean(history) or pstdev(history) / mean(history) > 0.75:
        return None
    difference = peak["actual"] - max(baseline, peak["reference"])
    if peak["actual"] < 3 * max(baseline, peak["reference"]) or difference < max(3, product["quantity"] * 0.2):
        return None
    return {"signal": "spike", "period": [peak["date"], peak["date"]],
            "quantity_impact": difference, "quantities": [baseline, peak["actual"]],
            "reason": f"{peak['date'][5:]} 售出 {_fmt(peak['actual'])}，此前普通销售日每天约 {_fmt(baseline)}。"}


def _monthly(product, month):
    c = product.get("contribution") or {}
    previous, current = c.get("previous_quantity"), c.get("current_quantity")
    if not c:
        # Older monthly reports saved the computed percentage, but not the
        # comparison quantities. Retain that evidence without reading raw files.
        change, current = product.get("change"), product["quantity"]
        if not isinstance(change, (int, float)) or not isfinite(change) or change <= -1 or current <= 0:
            return None
        previous = current / (1 + change)
    elif c.get("period") != "common" or not all(_number(v) and v > 0 for v in [previous, current]):
        return None
    difference = current - previous
    if abs(difference) < 3 or abs(difference / previous) < MIN_CHANGE:
        return None
    previous_month = (date.fromisoformat(month + "-01") - timedelta(days=1)).strftime("%Y-%m")
    return {"signal": "growth" if difference > 0 else "decline",
            "period": [previous_month, month], "quantity_impact": abs(difference),
            "quantities": [previous, current], "monthly": True,
            "reason": f"{month} 售出 {_fmt(current)}，上月 {_fmt(previous)}，"
                      f"{'多' if difference > 0 else '少'}卖 {_fmt(abs(difference))}。"}


def build_actions(products, *, parameters=None, summary=None, month=None, limit=3):
    """Rank material demand effects; unknown types receive sales actions only."""
    params, summary = parameters or {}, summary or {}
    if not summary.get("complete_month") or not params.get("complete_coverage") or not month:
        return []
    eligible = [p for p in products if _eligible(p)]
    monetary = bool(eligible) and all(_number(p.get("amount")) for p in eligible) and sum(p["amount"] for p in eligible) > 0
    def scale(p):
        c = p.get("contribution") or {}
        return max(p.get("amount" if monetary else "quantity") or 0,
                   c.get("previous_amount" if monetary else "previous_quantity") or 0)
    total = sum(scale(p) for p in eligible)
    if total <= 0:
        return []
    floor = max(total * STORE_IMPACT_FLOOR, max(map(scale, eligible), default=0) * LEADER_IMPACT_FLOOR)
    candidates = []
    for p in eligible:
        daily = bool(p.get("daily"))
        # Four one-week blocks are compared with a weekly store-sales floor.
        minimum = floor / 4 if daily else floor
        if scale(p) < minimum:
            continue
        c = p.get("contribution") or {}
        quantities = p["quantity"] + (c.get("previous_quantity") or 0)
        amounts = (p.get("amount") or 0) + (c.get("previous_amount") or 0)
        unit_value = amounts / quantities if monetary and quantities else 1
        # Daily data supports sustained trends or isolated spikes; a final-week
        # percentage on its own cannot generate a procurement recommendation.
        if daily:
            evidence = _trend(p, params) or _spike(p, params)
        else:
            previous_start = (date.fromisoformat(month + "-01") - timedelta(days=1)).replace(day=1).isoformat()
            evidence = _monthly(p, month) if params.get("coverage_start") and params["coverage_start"] <= previous_start else None
        if not evidence:
            continue
        impact = evidence["quantity_impact"] * unit_value
        if impact < minimum:
            continue
        kind = (p.get("item_type") or {}).get("kind", "unknown")
        signal, physical = evidence["signal"], kind == "physical"
        if signal == "spike":
            title = "单独确认这笔大单"
            text = "进货先参考平时销量，单独确认这天的大单是否还会再来。" if physical else "单独查看这天的大单，安排销售时先参考平时销量。"
        elif signal == "growth":
            title = "下次优先安排进货" if physical else "优先安排展示，观察销售"
            text = "下次采购可优先安排这款，数量结合库存和销量预测决定。" if physical else "可先放到更容易看到的位置，观察是否继续增长。"
            if evidence.get("monthly"):
                text += "目前比较了两个月，先小范围调整。"
        else:
            title = "下次先小批量采购" if physical else "试做小范围促销，观察销售"
            text = "下次先小批量采购，观察销量是否恢复。" if physical else "先试一次小范围促销或调整摆放，观察销量是否恢复。"
        currency = summary.get("currency") or ""
        share_total = sum(q.get("amount") or 0 for q in eligible) if monetary else sum(q["quantity"] for q in eligible)
        current = p.get("amount") if monetary else p["quantity"]
        share = current / share_total if share_total else 0
        sales = f"本月销售额 {_fmt(current)} {currency}" if monetary else f"本月销量 {_fmt(current)}"
        reason = evidence["reason"] + f" {sales}，占商品{'销售额' if monetary else '销量'} {share:.1%}。"
        identity = sha256((p["id"] + "|" + signal + "|" + "|".join(evidence["period"])).encode()).hexdigest()[:24]
        action = {
            "id": f"{ACTION_VERSION}:{identity}", "item_id": p["id"], "item_name": p["name"],
            "title": f"{p['name']}：{title}", "text": text, "reason": reason,
            "review": "调整后查看下一期销量，再决定是否继续。", "evidence": p["id"],
            "related_items": [p["id"]], "count": 1, "item_type": kind, "signal": signal,
            "version": ACTION_VERSION, "priority_basis": "amount" if monetary else "quantity",
            "selection": {"impact": impact, "minimum_impact": minimum, "sales_share": share,
                          "period": evidence["period"], "quantities": evidence["quantities"],
                          "comparison": "monthly" if evidence.get("monthly") else "daily"},
        }
        candidates.append((impact, scale(p), p["id"], action))
    candidates.sort(key=lambda row: (-row[0], -row[1], row[2]))
    return [row[3] for row in (candidates if limit is None else candidates[:limit])]


def action_view(report):
    """Adapt old reports for the workspace, retaining their original saved actions."""
    from .sales_signals import signal_view
    from .sales_focus import focus_view
    report = focus_view(signal_view(report))
    if report.get("action_version") == ACTION_VERSION:
        return report
    return {**report, "action_version": ACTION_VERSION, "previous_actions": report.get("actions", []),
            "actions": build_actions(report["products"], parameters=report.get("parameters"),
                                     summary=report.get("summary"), month=report.get("month"))}
