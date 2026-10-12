"""Versioned product evidence. Monetary calculations retain Decimal precision."""

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal, localcontext
from math import ceil

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import RobustScaler

from .amounts import AMOUNT_CONTEXT

INSIGHTS_VERSION = "product-insights-v1"
TYPE_LABELS = {
    "physical": "实物商品",
    "fee_service": "费用或服务",
    "accounting": "记账项目",
    "unknown": "商品类型待确认",
}
TYPE_VALUES = {
    "physical": "physical",
    "实物": "physical",
    "实物商品": "physical",
    "fee_service": "fee_service",
    "费用": "fee_service",
    "服务": "fee_service",
    "accounting": "accounting",
    "记账": "accounting",
    "记账项目": "accounting",
}
UCI_SPECIAL_CODES = {
    "POST": "fee_service",
    "DOT": "fee_service",
    "C2": "fee_service",
    "BANK CHARGES": "fee_service",
    "M": "accounting",
    "D": "accounting",
    "AMAZONFEE": "fee_service",
    "CRUK": "accounting",
    "S": "accounting",
}


def item_semantics(key, rows, sources, parameters):
    override = parameters.get("item_types", {}).get(key)
    if override:
        return {
            "kind": override,
            "label": TYPE_LABELS[override],
            "source": "user_mapping",
            "version": "item-type-v1",
        }
    kinds = set()
    for row in rows:
        value = TYPE_VALUES.get(str(row.get("item_type") or "").strip())
        if value:
            kinds.add(value)
    if len(kinds) == 1:
        kind = kinds.pop()
        return {
            "kind": kind,
            "label": TYPE_LABELS[kind],
            "source": "mapped_source_field",
            "version": "item-type-v1",
        }
    if not kinds and all(s["mapping"].get("status_rule") == "uci_cancel_prefix" for s in sources):
        kind = UCI_SPECIAL_CODES.get(key.strip().upper())
        if kind:
            return {
                "kind": kind,
                "label": TYPE_LABELS[kind],
                "source": "uci-online-retail-special-codes-v1",
                "version": "item-type-v1",
            }
    return {
        "kind": "unknown",
        "label": TYPE_LABELS["unknown"],
        "source": "conflicting_types" if kinds else "not_provided",
        "version": "item-type-v1",
    }


def _total(entries, field):
    return sum((b[field] for _, b in entries), Decimal(0))


def _abc(products):
    if not products or any(p["amount"] is None for p in products):
        return
    total = sum((Decimal(str(p["amount"])) for p in products), Decimal(0))
    if total <= 0:
        return
    groups = defaultdict(list)
    for p in products:
        groups[Decimal(str(p["amount"]))].append(p)
    cumulative, rank = Decimal(0), 1
    for amount in sorted(groups, reverse=True):
        group = sorted(groups[amount], key=lambda p: p["id"])
        band = (
            "A"
            if cumulative < total * Decimal("0.8")
            else ("B" if cumulative < total * Decimal("0.95") else "C")
        )
        cumulative += amount * len(group)
        for p in group:
            p["profile"].update(
                amount_share=float(amount / total),
                amount_rank=rank,
                cumulative_share=float(cumulative / total),
                contribution_band=band if len(products) >= 5 else None,
            )
            if band == "A" and len(products) >= 5 and amount > 0:
                p["profile"]["labels"].append("销售额贡献较高")
        rank += len(group)


def enrich_products(products, by_item, daily, dates, month, previous_month, comparable, params):
    """Return reconciled changes and independently usable product profiles."""
    first_dates = {k: min(d for d, _ in rows) for k, rows in by_item.items()}
    for p in products:
        key = p["id"]
        profile = {
            "version": INSIGHTS_VERSION,
            "labels": [],
            "amount_share": None,
            "amount_rank": None,
            "contribution_band": None,
            "weekly_cv": None,
            "nonzero_day_share": None,
            "complete_weeks": 0,
            "first_observed": first_dates[key],
            "last_observed": max(d for d, _ in by_item[key]),
        }
        known_start = params.get("item_start_dates", {}).get(key, first_dates[key])
        valid = [
            d
            for d in dates
            if d.isoformat() >= known_start
            and d.isoformat() not in set(params.get("missing_dates", []))
            and d.isoformat() not in set(params.get("closed_dates", []))
        ]
        if valid:
            quantities = [
                float(daily.get((d.isoformat(), key), {}).get("quantity", 0)) for d in valid
            ]
            profile["nonzero_day_share"] = float(np.count_nonzero(quantities) / len(quantities))
            profile["observed_days"] = len(valid)
            if profile["nonzero_day_share"] < 0.5:
                profile["labels"].append("间歇成交")
            weeks = defaultdict(list)
            for d, q in zip(valid, quantities, strict=True):
                weeks[(d - timedelta(days=d.weekday())).isoformat()].append(q)
            weekly = [sum(q) for q in weeks.values() if len(q) == 7]
            profile["complete_weeks"] = len(weekly)
            if len(weekly) >= 8 and np.mean(weekly) > 0:
                cv = float(np.std(weekly) / np.mean(weekly))
                profile["weekly_cv"] = cv
                profile["labels"].append(
                    "周销量较稳定"
                    if cv <= 0.5
                    else ("周销量有波动" if cv <= 1 else "周销量波动较大")
                )
        p["profile"] = profile
    _abc(products)
    changes = []
    if comparable:
        with localcontext(AMOUNT_CONTEXT):
            for key, entries in by_item.items():
                now = [(d, b) for d, b in entries if d.startswith(month)]
                old = [(d, b) for d, b in entries if d.startswith(previous_month)]
                if not now and not old:
                    continue
                q0, q1 = _total(old, "quantity"), _total(now, "quantity")
                amount_ok = not any(b["amount_missing"] for _, b in now + old)
                r0, r1 = _total(old, "amount"), _total(now, "amount")
                row = {
                    "item_id": key,
                    "period": "common"
                    if now and old
                    else ("only_current" if now else "only_previous"),
                    "previous_quantity": float(q0),
                    "current_quantity": float(q1),
                    "quantity_change": float(q1 - q0),
                    "amount_change": float(r1 - r0) if amount_ok else None,
                    "quantity_effect": None,
                    "price_effect": None,
                    "previous_amount": float(r0) if amount_ok else None,
                    "current_amount": float(r1) if amount_ok else None,
                }
                if amount_ok and q0 > 0 and q1 > 0:
                    quantity_effect = (q1 - q0) * (r0 / q0 + r1 / q1) / 2
                    # Reconcile display cents; the residual is allocated to price contribution.
                    quantity_cents = quantity_effect.quantize(Decimal("0.01"))
                    total_cents = (r1 - r0).quantize(Decimal("0.01"))
                    row.update(
                        quantity_effect=float(quantity_cents),
                        price_effect=float(total_cents - quantity_cents),
                        previous_price=float(r0 / q0),
                        current_price=float(r1 / q1),
                    )
                changes.append(row)
    change_lookup = {r["item_id"]: r for r in changes}
    for p in products:
        p["contribution"] = change_lookup.get(p["id"])
        labels = p["profile"]["labels"]
        if p["flags"]:
            p["focus_reason"] = p["reason"]
        elif "销售额贡献较高" in labels:
            p["flags"].append("contribution")
            p["focus_reason"] = (
                f"占本月销售额 {p['profile']['amount_share']:.1%}，可优先了解销售表现。"
            )
        else:
            p["focus_reason"] = "；".join(labels)
        if not p["reason"]:
            p["reason"] = p["focus_reason"]
    names = {p["id"]: p["name"] for p in products}
    for row in changes:
        row["name"] = names.get(row["item_id"], row["item_id"])
    changes.sort(key=lambda r: (-abs(r["amount_change"] or 0), r["item_id"]))
    amounts_ok = bool(changes) and all(r["amount_change"] is not None for r in changes)
    return {
        "version": INSIGHTS_VERSION,
        "comparable": comparable,
        "items": changes,
        "amount_change": float(sum((Decimal(str(r["amount_change"])) for r in changes), Decimal(0)))
        if amounts_ok
        else None,
        "notice": "比较两个完整月份；成交均价变化包含折扣及销售组合的影响，不能据此判断原因。",
        "rounding": "量价贡献按分展示；成交均价贡献吸收舍入差额，两项相加等于金额变化。",
    }


def rank_focus(products):
    """Rank impact within each evidence category, then diversify the short summary."""

    def impact(p):
        change = p.get("contribution") or {}
        value = abs(change.get("amount_change") or 0)
        if not value:
            value = (p["amount"] or p["quantity"]) * min(abs(p["change"] or 0), 2)
        if p["anomalies"]:
            price = p["amount"] / p["quantity"] if p["amount"] is not None and p["quantity"] else 1
            value = max(
                value, sum(abs(a["actual"] - a["reference"]) for a in p["anomalies"]) * price
            )
        return value or p["amount"] or p["quantity"]

    products.sort(key=lambda p: (-impact(p), p["id"]))
    attention = [p["id"] for p in products if p["flags"]]
    selected = []
    for flag in ["anomaly", "decline", "growth", "contribution"]:
        p = next((p for p in products if flag in p["flags"] and p["id"] not in selected), None)
        if p:
            selected.append(p["id"])
    selected += [key for key in attention if key not in selected]
    return attention, selected[:5]


def product_clusters(products):
    candidates = [
        p
        for p in products
        if p["profile"]["weekly_cv"] is not None
        and p["profile"]["nonzero_day_share"] is not None
        and p["change"] is not None
        and p["amount"] is not None
    ]
    result = {
        "version": "product-kmeans-v1",
        "status": "unavailable",
        "candidates": [],
        "eligible_items": len(candidates),
        "reason": "可比较且历史充足的商品不足。",
    }
    if len(candidates) < 50:
        return result
    raw = np.asarray(
        [
            [
                np.log1p(p["amount"]),
                p["profile"]["weekly_cv"],
                p["profile"]["nonzero_day_share"],
                p["change"],
                np.log1p(p["profile"].get("observed_days", 0)),
            ]
            for p in candidates
        ]
    )
    if len(np.unique(raw, axis=0)) < 2:
        return result
    scaler = RobustScaler().fit(raw)
    transformed = scaler.transform(raw)
    best = None
    for k in range(2, min(6, len(np.unique(raw, axis=0)) - 1) + 1):
        model = KMeans(n_clusters=k, random_state=42, n_init=10).fit(transformed)
        labels = model.labels_
        silhouette = float(
            silhouette_score(transformed, labels, sample_size=min(2000, len(raw)), random_state=42)
        )
        stability = []
        for offset in range(5):
            sample = np.random.default_rng(142 + offset).choice(
                len(raw), int(0.8 * len(raw)), replace=False
            )
            sub_scaler = RobustScaler().fit(raw[sample])
            sub = KMeans(n_clusters=k, random_state=52 + offset, n_init=10).fit_predict(
                sub_scaler.transform(raw[sample])
            )
            stability.append(float(adjusted_rand_score(labels[sample], sub)))
        ari = float(np.median(stability))
        floor = int(np.bincount(labels).min())
        passed = silhouette >= 0.15 and ari >= 0.65 and floor >= max(5, ceil(len(raw) * 0.02))
        row = {
            "k": k,
            "silhouette": silhouette,
            "ari_median": ari,
            "min_cluster_size": floor,
            "numeric_gate": passed,
        }
        result["candidates"].append(row)
        if passed and (best is None or silhouette > best[0]):
            best = (silhouette, labels)
    if best:
        result.update(
            status="evaluated",
            reason="分组需确认能增加可解释信息后才展示。",
            assignments={p["id"]: int(label) for p, label in zip(candidates, best[1], strict=True)},
            publishable=False,
            interpretation_review_required=True,
        )
    else:
        result.update(
            status="evaluated",
            reason="分组区分度或稳定性不足，继续使用商品表现描述。",
            publishable=False,
        )
    return result
