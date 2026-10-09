"""Sales reports independent of customer/order capabilities, with row-level provenance."""

import calendar as month_calendar
import csv
import json
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal, localcontext
from pathlib import Path
from zoneinfo import ZoneInfo

import pyarrow.parquet as pq

from .amounts import AMOUNT_CONTEXT, money
from .data_api import digest, write_json
from .import_formats import DataIssue
from .quality import normalize
from .sales_mining import MODEL_VERSION, anomaly_series, calendar, forecast_series

REASONS = {
    "included": "纳入销售统计",
    "cancelled": "取消记录",
    "returned": "退货记录",
    "unknown_status": "状态未确认",
    "invalid_quantity": "数量无法使用",
    "missing_item": "商品标识缺失",
    "invalid_time": "日期无法使用",
    "duplicate_removed": "按已确认策略去重",
    "replaced_range": "被新版本覆盖",
    "outside_scope": "不在统计截止日期内",
    "order_conflict": "同单日期、客户或币种冲突",
}


def source_rows(source):
    config = source["mapping"]
    policy = {"trim_identifiers": True}
    for batch in pq.ParquetFile(source["path"]).iter_batches(batch_size=2000):
        for raw in batch.to_pylist():
            row = normalize(raw, config, policy)
            row["version_id"] = source["version_id"]
            if config.get("record_kind") == "monthly_summary":
                row["day"] = config["summary_month"] + "-01"
            elif row["event_time"]:
                row["day"] = (
                    datetime.fromisoformat(row["event_time"])
                    .astimezone(ZoneInfo(config["timezone"]))
                    .date()
                    .isoformat()
                )
            else:
                row["day"] = None
            yield row


def reason_for(row, config):
    if not row.get("item_id"):
        return "missing_item"
    if not row["day"]:
        return "invalid_time"
    if row["record_status"] != "forward":
        return {"cancelled": "cancelled", "return": "returned"}.get(
            row["record_status"], "unknown_status"
        )
    q = money(row.get("quantity"))
    if (
        q is None
        or q < 0
        or (q == 0 and config.get("record_kind", "transactions") == "transactions")
    ):
        return "invalid_quantity"
    return "included"


def action_for(product):
    name = product["name"]
    if "anomaly" in product["flags"]:
        return {
            "id": "check:" + product["id"],
            "item_id": product["id"],
            "title": f"先查一下{name}的销售记录",
            "text": "这款商品有几天卖得和平常差别比较大。"
            "先看看有没有缺货、大单或漏记，再决定下次怎么进。",
            "reason": product["reason"],
            "review": "下次进货前核对",
            "evidence": product["id"],
        }
    if "decline" in product["flags"]:
        return {
            "id": "review:" + product["id"],
            "item_id": product["id"],
            "title": f"先看看{name}为什么卖少了",
            "text": "先确认是否缺货、停业或结束活动。原因没查清之前，别直接按下降幅度减少进货。",
            "reason": product["reason"],
            "review": "下次进货前核对",
            "evidence": product["id"],
        }
    if "growth" in product["flags"]:
        return {
            "id": "stock:" + product["id"],
            "item_id": product["id"],
            "title": f"下次进货前看看{name}还剩多少",
            "text": "最近卖得更多了，先核对库存和到货时间，再决定是否补一些。",
            "reason": product["reason"],
            "review": "下次进货前核对",
            "evidence": product["id"],
        }
    return None


def process_retail(job, progress):
    output = Path(job["output"])
    params = job["parameters"]
    month = params["month"]
    month_start = date.fromisoformat(month + "-01")
    month_end = month_start.replace(
        day=month_calendar.monthrange(month_start.year, month_start.month)[1]
    )
    previous_end = month_start.fromordinal(month_start.toordinal() - 1)
    previous_month = previous_end.strftime("%Y-%m")
    sources = sorted(job["sources"], key=lambda s: s["number"])
    kinds = {s["mapping"].get("record_kind", "transactions") for s in sources}
    if len(kinds) != 1:
        raise DataIssue("明细、日汇总和月汇总请分别生成月报，不能叠加计算。", "mixed_shapes")
    kind = next(iter(kinds))
    semantic = {
        (s["mapping"]["quantity_unit"], s["mapping"]["amount_mode"], s["mapping"].get("timezone"))
        for s in sources
    }
    if len(semantic) != 1:
        raise DataIssue("合并文件的数量单位、金额口径或时区不同，请先统一。", "mixed_semantics")
    mapping = sources[-1]["mapping"]
    progress("sales_quality", 5)
    ranges, conflicts = [], set()
    for source in sources:
        frozen_hash = params.get("source_hashes", {}).get(source["version_id"])
        if frozen_hash and source["canonical_sha256"] != frozen_hash:
            raise DataIssue("提交后的来源文件已变化，请重新确认。", "artifact_mismatch")
        if digest(Path(source["path"])) != source["canonical_sha256"]:
            raise DataIssue("来源文件已变化，请重新确认。", "artifact_mismatch")
        days, orders = set(), {}
        for row in source_rows(source):
            if row["day"]:
                days.add(row["day"])
            if row["day"] and row["day"] > month_end.isoformat():
                continue
            if kind == "transactions" and row.get("order_id"):
                key = row["order_id"]
                state = orders.setdefault(
                    key, {"times": set(), "customers": set(), "currencies": set()}
                )
                for field, bucket in [
                    ("event_time", "times"),
                    ("customer_id", "customers"),
                    ("currency", "currencies"),
                ]:
                    if row.get(field):
                        state[bucket].add(row[field])
                if any(len(v) > 1 for v in state.values()):
                    conflicts.add((source["version_id"], key))
        ranges.append((min(days), max(days)) if days else (None, None))
    for i, (start, end) in enumerate(ranges):
        for other_start, other_end in ranges[:i]:
            if (
                start
                and other_start
                and start <= other_end
                and end >= other_start
                and params["merge_mode"] == "append"
            ):
                raise DataIssue(
                    "选中的文件日期重叠。请取消重复文件，或明确选择用新版本覆盖重叠日期。",
                    "overlapping_sources",
                )
    daily = defaultdict(lambda: {"quantity": Decimal(0), "amount": Decimal(0), "amount_missing": 0})
    names, categories, units = {}, {}, mapping["quantity_unit"]
    excluded = Counter()
    currencies, seen, order_state = set(), set(), {}
    observed = set()
    input_rows = included_rows = duplicates = 0
    missing_order_months, incomplete_order_months = set(), set()
    refund_values, refund_missing = defaultdict(Decimal), Counter()
    audit_path = output / "sales_row_audit.csv"
    with audit_path.open("w", encoding="utf-8-sig", newline="") as audit:
        writer = csv.DictWriter(
            audit, fieldnames=["version_id", "source_row_id", "item_id", "date", "reason"]
        )
        writer.writeheader()
        for index, source in enumerate(sources):
            config = source["mapping"]
            for row in source_rows(source):
                input_rows += 1
                reason = reason_for(row, config)
                if row["day"] and row["day"] > month_end.isoformat():
                    reason = "outside_scope"
                if (
                    row["day"]
                    and params.get("coverage_end")
                    and row["day"] > params["coverage_end"]
                ):
                    reason = "outside_scope"
                if (
                    row["day"]
                    and params.get("coverage_start")
                    and row["day"] < params["coverage_start"]
                ):
                    reason = "outside_scope"
                if params["merge_mode"] == "replace_overlap" and row["day"]:
                    if any(a and a <= row["day"] <= b for a, b in ranges[index + 1 :]):
                        reason = "replaced_range"
                if (source["version_id"], row.get("order_id")) in conflicts:
                    reason = "order_conflict"
                signature = json.dumps(
                    {
                        k: v
                        for k, v in row.items()
                        if k not in {"source_row_id", "version_id", "issues", "duplicate_candidate"}
                    },
                    sort_keys=True,
                )
                if signature in seen:
                    duplicates += 1
                    if params["duplicates"] == "drop_exact":
                        reason = "duplicate_removed"
                seen.add(signature)
                writer.writerow(
                    {
                        "version_id": source["version_id"],
                        "source_row_id": row["source_row_id"],
                        "item_id": row.get("item_id"),
                        "date": row["day"],
                        "reason": reason,
                    }
                )
                if reason != "included":
                    if (
                        reason
                        in {"invalid_quantity", "missing_item", "order_conflict", "unknown_status"}
                        and row["day"]
                    ):
                        incomplete_order_months.add(row["day"][:7])
                    if reason == "returned" and row["day"]:
                        value = money(row.get("line_amount"))
                        if (
                            config["amount_mode"] in {"line_amount", "quantity_unit_price"}
                            and value is not None
                            and row.get("currency")
                        ):
                            refund_values[row["day"][:7]] += abs(value)
                            currencies.add(row["currency"])
                        else:
                            refund_missing[row["day"][:7]] += 1
                    excluded[reason] += 1
                    continue
                included_rows += 1
                if (
                    kind == "transactions"
                    and mapping["order_boundary"] != "unavailable"
                    and not row.get("order_id")
                ):
                    missing_order_months.add(row["day"][:7])
                observed.add(row["day"])
                key = row["item_id"]
                names.setdefault(key, row.get("item_name") or key)
                categories.setdefault(key, row.get("category"))
                bucket = daily[row["day"], key]
                with localcontext(AMOUNT_CONTEXT):
                    bucket["quantity"] += money(row["quantity"])
                    value = money(row.get("line_amount"))
                    if mapping["amount_mode"] in {"line_amount", "quantity_unit_price"}:
                        if (
                            value is not None
                            and value >= 0
                            and row.get("currency")
                            and "amount_source_conflict" not in row["issues"]
                        ):
                            bucket["amount"] += value
                            currencies.add(row["currency"])
                        else:
                            bucket["amount_missing"] += 1
                if (
                    kind == "transactions"
                    and mapping["order_boundary"] != "unavailable"
                    and row.get("order_id")
                ):
                    order_key = (source["version_id"], row["order_id"])
                    state = order_state.setdefault(
                        order_key,
                        {
                            "day": row["day"],
                            "totals": set(),
                            "missing": False,
                            "currency": row.get("currency"),
                        },
                    )
                    total = money(row.get("order_amount"))
                    if total is not None and total >= 0:
                        state["totals"].add(total)
                    else:
                        state["missing"] = True
                    if mapping["amount_mode"] == "order_amount" and row.get("currency"):
                        currencies.add(row["currency"])
    if len(currencies) > 1:
        raise DataIssue("选中数据包含多种币种，不能合计销售额。请分别生成月报。", "mixed_currency")
    progress("sales_summary", 25)
    complete = params["complete_coverage"] and bool(
        params.get("coverage_start") and params.get("coverage_end")
    )
    if (
        complete
        and observed
        and (min(observed) < params["coverage_start"] or max(observed) > params["coverage_end"])
    ):
        raise DataIssue("完整日期范围与记录不一致。", "coverage_conflict")
    complete_month = (
        complete
        and params["coverage_start"] <= month_start.isoformat()
        and params["coverage_end"] >= month_end.isoformat()
    )
    month_days = calendar(month_start.isoformat(), month_end.isoformat())
    closed = set(params["closed_dates"])
    if any(
        d in observed and any(b["quantity"] > 0 for (day, _), b in daily.items() if day == d)
        for d in closed
    ):
        raise DataIssue("标为停业的日期存在销售记录，请核对。", "closed_date_conflict")
    available = sorted({d[:7] for d in observed})
    totals = {}
    for m in [month, previous_month]:
        buckets = [b for (d, _), b in daily.items() if d.startswith(m)]
        quantity = sum((b["quantity"] for b in buckets), Decimal(0))
        amount_missing = sum(b["amount_missing"] for b in buckets)
        amount = sum((b["amount"] for b in buckets), Decimal(0))
        amount_available = (
            mapping["amount_mode"] in {"line_amount", "quantity_unit_price"}
            and bool(buckets)
            and not amount_missing
        )
        orders = [s for s in order_state.values() if s["day"].startswith(m)]
        if mapping["amount_mode"] == "order_amount":
            amount_available = (
                bool(orders)
                and m not in missing_order_months | incomplete_order_months
                and all(
                    len(s["totals"]) == 1 and not s["missing"] and s["currency"] for s in orders
                )
            )
            amount = sum(
                (next(iter(s["totals"])) for s in orders if len(s["totals"]) == 1), Decimal(0)
            )
        totals[m] = {
            "quantity": float(quantity),
            "amount": float(amount) if amount_available else None,
            "amount_missing_rows": amount_missing,
            "orders": (len(orders) or None)
            if m not in missing_order_months | incomplete_order_months
            else None,
            "refund_amount": None
            if refund_missing[m] or m not in refund_values
            else float(refund_values[m]),
        }
    series, dates = {}, []
    if complete and observed and kind != "monthly_summary":
        start = params["coverage_start"]
        cutoff = min(params["coverage_end"], month_end.isoformat())
        dates = calendar(start, cutoff) if start <= cutoff else []
        if dates:
            series = {
                key: [float(daily.get((d.isoformat(), key), {}).get("quantity", 0)) for d in dates]
                for key in names
            }
    forecast = (
        forecast_series(series, dates, progress)
        if complete_month and kind != "monthly_summary" and not params.get("check_only")
        else {
            "status": "unavailable",
            "reason": "需要确认完整日期范围后，才能预测；月汇总不支持日级预测。",
            "predictions": {},
            "metrics": [],
            "version": MODEL_VERSION,
        }
    )
    progress("sales_anomalies", 70)
    anomaly = (
        anomaly_series(series, dates, month, params["closed_dates"])
        if complete_month and kind != "monthly_summary" and not params.get("check_only")
        else {
            "status": "unavailable",
            "reason": "当前记录无法核对完整的历史波动。",
            "items": {},
            "version": MODEL_VERSION,
        }
    )
    by_item = defaultdict(list)
    by_day = defaultdict(list)
    for (day, key), bucket in daily.items():
        by_item[key].append((day, bucket))
        by_day[day].append(bucket)
    products = []
    for key, name in names.items():
        current = [b for d, b in by_item[key] if d.startswith(month)]
        if not current:
            continue
        quantity = float(sum((b["quantity"] for b in current), Decimal(0)))
        has_amount = mapping["amount_mode"] in {"line_amount", "quantity_unit_price"} and not any(
            b["amount_missing"] for b in current
        )
        amount = float(sum((b["amount"] for b in current), Decimal(0))) if has_amount else None
        daily_values = (
            [
                {
                    "date": d.isoformat(),
                    "quantity": float(daily.get((d.isoformat(), key), {}).get("quantity", 0))
                    if complete_month or (d.isoformat(), key) in daily
                    else None,
                    "recorded": (d.isoformat(), key) in daily,
                }
                for d in month_days
            ]
            if kind != "monthly_summary"
            else []
        )
        flags, change, reason = [], None, ""
        if complete_month and kind != "monthly_summary":
            last = sum(v["quantity"] for v in daily_values[-7:])
            prior = sum(v["quantity"] for v in daily_values[-14:-7])
            change = (last - prior) / prior if prior > 0 else None
            if change is not None and abs(change) >= 0.25 and abs(last - prior) >= 3:
                flags.append("growth" if change > 0 else "decline")
                reason = f"月底最后 7 天售出 {last:g} {units}，前 7 天为 {prior:g} {units}。"
        if (
            kind == "monthly_summary"
            and complete_month
            and complete
            and params["coverage_start"] <= previous_end.replace(day=1).isoformat()
        ):
            prior_buckets = [b for d, b in by_item[key] if d.startswith(previous_month)]
            prior = float(sum((b["quantity"] for b in prior_buckets), Decimal(0)))
            if prior_buckets and prior > 0:
                change = (quantity - prior) / prior
                if abs(change) >= 0.25 and abs(quantity - prior) >= 3:
                    flags.append("growth" if change > 0 else "decline")
                    reason = f"本月售出 {quantity:g} {units}，上月为 {prior:g} {units}。"
        anomalies = anomaly["items"].get(key, [])
        if anomalies:
            flags.append("anomaly")
            reason = (
                reason + " " if reason else ""
            ) + f"本月有 {len(anomalies)} 天的销量偏离历史表现，建议核对原因。"
        products.append(
            {
                "id": key,
                "name": name,
                "category": categories[key],
                "quantity": quantity,
                "amount": amount,
                "change": change,
                "flags": flags,
                "reason": reason,
                "daily": daily_values,
                "anomalies": anomalies,
                "forecast": forecast["predictions"].get(key),
                "forecast_reason": forecast.get("reason")
                or (
                    "预测回测误差较大，或该商品在固定回测起点前的记录不足；暂不发布数量。"
                    if key not in forecast["predictions"]
                    else ""
                ),
            }
        )
    products.sort(
        key=lambda p: (
            -len(p["flags"]),
            -(p["amount"] if p["amount"] is not None else p["quantity"]),
            p["id"],
        )
    )
    attention = [p["id"] for p in products if p["flags"]]
    grouped_actions = {}
    for p in products:
        action = action_for(p)
        if action:
            group = action["id"].split(":")[0]
            if group not in grouped_actions:
                action["related_items"] = [p["id"]]
                grouped_actions[group] = action
            else:
                grouped_actions[group]["related_items"].append(p["id"])
    actions = list(grouped_actions.values())[:3]
    for action in actions:
        if len(action["related_items"]) > 1:
            action["text"] += (
                f" 另有 {len(action['related_items']) - 1} 件商品有同类情况，"
                "可在待关注列表一起核对。"
            )
    chart = []
    if kind != "monthly_summary":
        for day in month_days:
            values = by_day[day.isoformat()]
            chart.append(
                {
                    "date": day.isoformat(),
                    "quantity": float(sum((b["quantity"] for b in values), Decimal(0)))
                    if values or complete_month
                    else None,
                    "amount": float(sum((b["amount"] for b in values), Decimal(0)))
                    if totals[month]["amount"] is not None
                    and mapping["amount_mode"] != "order_amount"
                    and (values or complete_month)
                    else None,
                }
            )
    comparative = (
        complete
        and params["coverage_start"] <= previous_end.replace(day=1).isoformat()
        and params["coverage_end"] >= month_end.isoformat()
    )
    previous_chart = []
    if comparative and kind != "monthly_summary":
        for day in calendar(previous_end.replace(day=1).isoformat(), previous_end.isoformat()):
            values = by_day[day.isoformat()]
            previous_chart.append(
                {
                    "date": day.isoformat(),
                    "quantity": float(sum((b["quantity"] for b in values), Decimal(0))),
                    "amount": float(sum((b["amount"] for b in values), Decimal(0)))
                    if totals[previous_month]["amount"] is not None
                    and mapping["amount_mode"] != "order_amount"
                    else None,
                }
            )
    summary = {
        **totals[month],
        "products": len(products),
        "attention_total": len(attention),
        "unit": units,
        "currency": next(iter(currencies), mapping.get("currency_constant")),
        "previous": totals[previous_month] if comparative else None,
        "complete_month": complete_month,
        "amount_label": "按单价计算的销售额"
        if mapping["amount_mode"] == "quantity_unit_price"
        else "正向销售额（退款另计）",
        "average_order": totals[month]["amount"] / totals[month]["orders"]
        if totals[month]["amount"] is not None and totals[month]["orders"]
        else None,
    }
    report = {
        "version": MODEL_VERSION,
        "context": job["context"],
        "month": month,
        "available_months": available,
        "parameters": params,
        "source_ranges": ranges,
        "sources": [
            {
                k: s[k]
                for k in [
                    "version_id",
                    "number",
                    "filename",
                    "mapping_revision",
                    "canonical_sha256",
                ]
            }
            for s in sources
        ],
        "summary": summary,
        "chart": chart,
        "previous_chart": previous_chart,
        "products": products,
        "attention_ids": attention,
        "highlights": attention[:5],
        "actions": actions,
        "forecast": {k: v for k, v in forecast.items() if k not in {"predictions", "backtests"}},
        "anomaly": {k: v for k, v in anomaly.items() if k != "items"},
        "quality": {
            "input_rows": input_rows,
            "included_rows": included_rows,
            "excluded_rows": sum(excluded.values()),
            "duplicate_candidates": duplicates,
            "reasons": [{"code": k, "label": REASONS[k], "count": v} for k, v in excluded.items()],
        },
        "notices": [
            "只统计确认的正向销售，取消和退货不自动扣入净收入。",
            "未提供库存和成本，销量变化不代表缺货、积压或利润变化。",
        ],
    }
    if not complete_month:
        report["notices"].append("本月完整性尚未确认，仅总结提供的记录；缺记录的日期不补成零销量。")
    if duplicates and params["duplicates"] == "keep":
        report["notices"].append("完全重复候选仍按原记录保留，请在数据检查时核对。")
    progress("writing_results", 90)
    with (output / "sales_products.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=["id", "name", "quantity", "amount", "change", "reason", "attention"]
        )
        writer.writeheader()
        for p in products:
            values = {k: p[k] for k in ["id", "name", "quantity", "amount", "change", "reason"]}
            for key in ["id", "name", "reason"]:
                if str(values[key]).lstrip().startswith(("=", "+", "-", "@")):
                    values[key] = "'" + str(values[key])
            writer.writerow({**values, "attention": bool(p["flags"])})
    with (output / "sales_backtests.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        records = forecast.get("backtests", [])
        writer = csv.DictWriter(
            stream, fieldnames=list(records[0]) if records else ["item_id", "origin", "actual"]
        )
        writer.writeheader()
        writer.writerows(records)
    write_json(output / "sales_report.json", report)
    return report
