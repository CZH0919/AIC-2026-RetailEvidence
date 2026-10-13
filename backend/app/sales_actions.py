"""Small, traceable action groups; never infer physical goods from unknown item types."""

from collections import defaultdict

TYPE_NAMES = {
    "physical": "实物商品",
    "unknown": "类型待确认的记录",
    "fee_service": "费用或服务项目",
    "accounting": "记账项目",
}
REASON_NAMES = {"anomaly": "异常变化", "decline": "销量下降", "growth": "销量增长"}


def _reason(product):
    return next((f for f in ("anomaly", "decline", "growth") if f in product["flags"]), None)


def _impact(product, monetary):
    change = product.get("contribution") or {}
    value = abs(change.get("amount_change" if monetary else "quantity_change") or 0)
    scale = (product["amount"] or 0) if monetary else product["quantity"]
    value = max(value, scale * min(abs(product.get("change") or 0), 2))
    unit = product["amount"] / product["quantity"] if monetary and product["quantity"] else 1
    anomaly = sum(abs(a["actual"] - a["reference"]) for a in product["anomalies"]) * unit
    return max(value, anomaly)


def build_actions(products):
    monetary = bool(products) and all(p["amount"] is not None for p in products)
    buckets = defaultdict(list)
    for product in products:
        reason = _reason(product)
        if not reason:
            continue
        kind = product.get("item_type", {}).get("kind", "unknown")
        buckets[kind if kind in TYPE_NAMES else "unknown", reason].append(product)

    def priority(product):
        profile = product.get("profile") or {}
        return (
            -_impact(product, monetary),
            -(profile.get("contribution_band") == "A"),
            -max((e.get("strength", 0) for e in product.get("anomaly_events", [])), default=0),
            product["id"],
        )

    groups = []
    for (kind, reason), members in buckets.items():
        members.sort(key=priority)
        first = members[0]
        title = f"核对{TYPE_NAMES[kind]}的{REASON_NAMES[reason]}"
        if kind == "physical":
            text = {
                "anomaly": "先核对异常日期的记录，了解是否有大单、缺货或活动，再决定是否调整备货。",
                "decline": "先核对库存、营业情况和活动变化，原因未确认前不要直接按降幅减少进货。",
                "growth": "先核对这些商品的库存和到货时间，再决定是否需要补货。",
            }[reason]
            review = "下次进货前核对"
        elif kind == "unknown":
            movement = {"anomaly": "异常", "decline": "下降", "growth": "增长"}[reason]
            title = f"先确认{movement}记录的类型"
            text = (
                "先确认这些记录属于实物、费用还是记账项目，再核对变化原因；"
                "类型未确认前不据此安排备货。"
            )
            review = "先确认类型，再决定后续处理"
        else:
            movement = {"anomaly": "异常变化", "decline": "记录数量下降", "growth": "记录数量增长"}
            title = f"核对{TYPE_NAMES[kind]}的{movement[reason]}"
            text = "核对相关日期的数量和金额，确认费用或账务变化的原因；这组记录不用于实物备货。"
            review = "下次账务核对时检查"
        groups.append(
            {
                "id": f"review:{kind}:{reason}",
                "item_id": first["id"],
                "title": title,
                "text": text,
                "reason": first["reason"],
                "review": review,
                "evidence": first["id"],
                "related_items": [p["id"] for p in members],
                "item_type": kind,
                "signal": reason,
                "count": len(members),
                "priority_basis": "amount" if monetary else "quantity",
                "priority_notice": "优先展示变化影响较大的记录，结合销售贡献与异常幅度排序；"
                "影响参考不代表实际损失。",
                "_priority": priority(first),
            }
        )
    groups.sort(key=lambda group: (group["_priority"], group["id"]))
    for group in groups:
        group.pop("_priority")
    return groups[:3]
