"""Deterministic, bounded quality preparation. No clustering or association mining here."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pyarrow as pa
import pyarrow.parquet as pq

from .amounts import AMOUNT_CONTEXT, money
from .data_schemas import FIELDS

REASONS = {
    "included": "纳入当前有效视图",
    "filtered_out": "不在已选业务范围",
    "order_boundary_unknown": "订单边界尚未确认",
    "missing_order": "缺少订单标识",
    "order_conflict": "同一订单的客户、时间或币种相互冲突",
    "cancelled": "取消记录",
    "returned": "退货记录",
    "unknown_status": "交易状态含义不明确",
    "invalid_quantity": "数量缺失或无法解析",
    "nonpositive_quantity": "数量非正",
    "duplicate_removed": "按已确认策略移除完全重复记录",
    "missing_customer": "订单包含缺失客户标识",
    "invalid_time": "订单时间缺失或无法明确解析",
    "missing_item": "缺少商品标识",
    "incomplete_basket": "购物篮成员不完整",
    "amount_unavailable": "没有确认可用的金额口径",
    "invalid_amount": "金额缺失、非法或非正",
    "conflicting_order_amount": "同单订单总额不一致",
    "amount_source_conflict": "金额来源不一致，需确认口径",
    "partial_order_amount": "订单仅保留部分明细，缺少对应行金额",
    "unknown_currency": "订单包含未知币种",
    "incomplete_customer_amount": "客户包含金额不完整的订单",
    "invalid_unit_price": "单价无法解析",
    "invalid_line_amount": "行金额无法解析",
    "invalid_order_amount": "订单总额无法解析",
    "duplicate_candidate": "完全重复候选",
}
COMMON_PRIORITY = [
    "order_boundary_unknown",
    "missing_order",
    "order_conflict",
    "cancelled",
    "returned",
    "unknown_status",
    "invalid_quantity",
    "nonpositive_quantity",
    "duplicate_removed",
]
NORMAL_SCHEMA = pa.schema(
    [("source_row_id", pa.string())]
    + [(key, pa.string()) for key in FIELDS]
    + [
        ("source_line_amount", pa.string()),
        ("issues", pa.list_(pa.string())),
        ("duplicate_candidate", pa.bool_()),
    ]
)
ORDER_SCHEMA = pa.schema(
    [
        ("order_id", pa.string()),
        ("customer_id", pa.string()),
        ("event_time", pa.string()),
        ("currency", pa.string()),
        ("amount", pa.string()),
        ("amount_source", pa.string()),
        ("source_rows", pa.int64()),
        ("effective_source_rows", pa.int64()),
        ("selected_rows", pa.int64()),
        ("partial_order", pa.bool_()),
    ]
)
AUDIT_SCHEMA = pa.schema(
    [
        ("source_row_id", pa.string()),
        ("order_id", pa.string()),
        ("item_id", pa.string()),
        ("primary_reason", pa.string()),
        ("rf_reason", pa.string()),
        ("rfm_reason", pa.string()),
        ("amount_reason", pa.string()),
        ("association_reason", pa.string()),
        ("issues", pa.list_(pa.string())),
    ]
)
BASKET_SCHEMA = pa.schema([("order_id", pa.string()), ("item_id", pa.string())])


class RowsWriter:
    def __init__(self, path, schema):
        self.schema = schema
        self.writer = pq.ParquetWriter(path, schema, compression="zstd")
        self.buffer = []
        self.count = 0

    def add(self, row):
        self.buffer.append(row)
        self.count += 1
        if len(self.buffer) >= 2000:
            self.flush()

    def flush(self):
        if self.buffer:
            self.writer.write_table(pa.Table.from_pylist(self.buffer, schema=self.schema))
            self.buffer = []

    def close(self):
        self.flush()
        self.writer.close()


def parse_time(value, config):
    if not value:
        return None
    try:
        moment = (
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            if config["time_format"] == "iso8601"
            else datetime.strptime(value, config["time_format"])
        )
        if moment.tzinfo is None:
            zone = ZoneInfo(config["timezone"])
            early, late = moment.replace(tzinfo=zone, fold=0), moment.replace(tzinfo=zone, fold=1)
            if early.utcoffset() != late.utcoffset():
                return (
                    None  # Ambiguous or nonexistent local wall time, never silently choose a fold.
                )
            if early.astimezone(UTC).astimezone(zone).replace(tzinfo=None) != moment:
                return None
            moment = early
        return moment.astimezone(UTC).isoformat(timespec="seconds")
    except (ValueError, TypeError, KeyError, OverflowError):
        return None


def normalize(row, mapping, policy):
    result = dict(row)
    issues = []
    for key in ["order_id", "item_id", "customer_id"]:
        if result.get(key) is not None and policy["trim_identifiers"]:
            result[key] = result[key].strip() or None
    if mapping["order_boundary"] == "unavailable":
        issues.append("order_boundary_unknown")
    if not result.get("order_id"):
        issues.append("missing_order")
    if not result.get("item_id"):
        issues.append("missing_item")
    if not result.get("customer_id"):
        issues.append("missing_customer")
    result["event_time"] = parse_time(row.get("event_time"), mapping)
    if not result["event_time"]:
        issues.append("invalid_time")
    rule = mapping["status_rule"]
    status = "unknown"
    if rule == "all_forward":
        status = "forward"
    elif rule == "uci_cancel_prefix":
        status = (
            "cancelled" if (result.get("order_id") or "").upper().startswith("C") else "forward"
        )
    elif rule == "status_column":
        status = mapping["status_values"].get(row.get("record_status"), "unknown")
    result["record_status"] = status
    if status != "forward":
        issues.append(
            {"cancelled": "cancelled", "return": "returned"}.get(status, "unknown_status")
        )
    for key in ["quantity", "unit_price", "line_amount", "order_amount"]:
        number = money(row.get(key))
        result[key] = str(number) if number is not None else None
        if row.get(key) is not None and number is None:
            issues.append("invalid_" + key)
    if mapping["columns"].get("quantity"):
        if result["quantity"] is None:
            issues.append("invalid_quantity")
        elif Decimal(result["quantity"]) <= 0:
            issues.append("nonpositive_quantity")
    currency = (row.get("currency") or "").strip().upper()
    result["currency"] = currency if re.fullmatch("[A-Z]{3}", currency) else None
    result["source_line_amount"] = result["line_amount"]
    if mapping["amount_mode"] == "quantity_unit_price":
        quantity, price = money(result["quantity"]), money(result["unit_price"])
        derived = (
            AMOUNT_CONTEXT.multiply(quantity, price)
            if quantity is not None and price is not None
            else None
        )
        declared = money(result["line_amount"])
        if derived is not None and (
            declared is not None and derived != declared or "invalid_line_amount" in issues
        ):
            issues.append("amount_source_conflict")
        result["line_amount"] = str(derived) if derived is not None else None
    if not result["currency"]:
        issues.append("unknown_currency")
    result["issues"] = list(dict.fromkeys(issues))
    return result


def line_value(row, mode):
    direct = money(row.get("line_amount"))
    quantity, price = money(row.get("quantity")), money(row.get("unit_price"))
    derived = (
        AMOUNT_CONTEXT.multiply(quantity, price)
        if quantity is not None and price is not None
        else None
    )
    value = derived if mode == "quantity_unit_price" else direct
    if mode == "order_amount" and value is None:
        value = derived
    conflict = direct is not None and derived is not None and direct != derived
    return value, conflict


@dataclass(slots=True)
class Order:
    rows: int = 0
    effective_rows: int = 0
    customer: str | None = None
    time: str | None = None
    currency: str | None = None
    conflict: bool = False
    customer_missing: bool = False
    time_invalid: bool = False
    currency_missing: bool = False
    basket_incomplete: bool = False
    total: Decimal | None = None
    total_conflict: bool = False
    total_invalid: bool = False
    line_sum: Decimal = Decimal(0)
    lines_complete: bool = True
    source_amount_conflict: bool = False
    selected: int = 0
    before_scope: int = 0
    selected_line_sum: Decimal = Decimal(0)
    selected_lines_complete: bool = True
    items: set = field(default_factory=set)
    amount: Decimal | None = None
    amount_reason: str = "amount_unavailable"
    amount_source: str = "none"
    rf_reason: str = "included"
    rfm_reason: str = "included"

    def observe(self, row, policy, mode):
        self.rows += 1
        for column, attribute in [
            ("customer_id", "customer"),
            ("event_time", "time"),
            ("currency", "currency"),
        ]:
            value = row.get(column)
            previous = getattr(self, attribute)
            if value is not None:
                if previous is not None and previous != value:
                    self.conflict = True
                setattr(self, attribute, value if previous is None else previous)
        self.customer_missing |= row["customer_id"] is None
        self.time_invalid |= row["event_time"] is None
        self.currency_missing |= row["currency"] is None
        self.basket_incomplete |= bool(
            set(row["issues"]) & {"missing_item", "invalid_quantity", "unknown_status"}
        )
        if policy["duplicates"] == "drop_exact" and row["duplicate_candidate"]:
            return
        self.effective_rows += 1
        total = money(row["order_amount"])
        if total is not None:
            self.total_conflict |= self.total is not None and self.total != total
            self.total = total if self.total is None else self.total
        self.total_invalid |= "invalid_order_amount" in row["issues"]
        value, conflict = line_value(row, mode)
        self.source_amount_conflict |= conflict or "amount_source_conflict" in row["issues"]
        if value is None or value <= 0:
            self.lines_complete = False
        else:
            self.line_sum = AMOUNT_CONTEXT.add(self.line_sum, value)


def in_scope(row, scope, zone):
    if scope.get("countries") and row.get("country") not in scope["countries"]:
        return False
    if scope.get("item_ids") and row.get("item_id") not in scope["item_ids"]:
        return False
    if scope.get("currency") and row.get("currency") != scope["currency"]:
        return False
    if scope.get("date_start") or scope.get("date_end"):
        if not row["event_time"]:
            return False
        day = datetime.fromisoformat(row["event_time"]).astimezone(zone).date().isoformat()
        if scope.get("date_start") and day < scope["date_start"]:
            return False
        if scope.get("date_end") and day > scope["date_end"]:
            return False
    return True


def common_reason(row, order, scope, zone, policy):
    issues = set(row["issues"])
    if order and order.conflict:
        issues.add("order_conflict")
    if row["duplicate_candidate"] and policy["duplicates"] == "drop_exact":
        issues.add("duplicate_removed")
    reason = next((key for key in COMMON_PRIORITY if key in issues), None)
    return reason or ("included" if in_scope(row, scope, zone) else "filtered_out")


def finalize_order(order, mapping, policy):
    mode = mapping["amount_mode"]
    order.source_amount_conflict |= order.total_conflict or order.total_invalid
    if order.customer_missing:
        order.rf_reason = "missing_customer"
    elif order.time_invalid:
        order.rf_reason = "invalid_time"
    if mode == "none":
        reason = "amount_unavailable"
    elif order.currency_missing:
        reason = "unknown_currency"
    elif mode == "order_amount" and order.total_conflict:
        reason = "conflicting_order_amount"
    elif mode == "order_amount" and (
        order.total is None or order.total_invalid or order.total <= 0
    ):
        reason = "invalid_amount"
    elif mode == "order_amount" and order.selected < order.effective_rows:
        if order.selected_lines_complete:
            reason = "included"
            order.amount, order.amount_source = order.selected_line_sum, "selected_lines"
        else:
            reason = "partial_order_amount"
    elif mode == "order_amount":
        reason = "included"
        order.amount, order.amount_source = order.total, "order_amount_once"
    elif not order.selected_lines_complete:
        reason = "invalid_amount"
    else:
        reason = "included"
        order.amount, order.amount_source = order.selected_line_sum, mode
    if order.lines_complete and order.total is not None and order.line_sum != order.total:
        order.source_amount_conflict = True
    if (
        reason == "included"
        and order.source_amount_conflict
        and not policy["accept_selected_amount_source"]
    ):
        reason = "amount_source_conflict"
    order.amount_reason = reason
    if reason != "included":
        order.amount = None
    order.rfm_reason = order.rf_reason if order.rf_reason != "included" else reason


def customer_metrics(orders):
    customers = {}
    dates = []
    for order in orders:
        value = customers.setdefault(order.customer, [0, order.time, Decimal(0)])
        value[0] += 1
        value[1] = max(value[1], order.time)
        if order.amount is not None:
            value[2] = AMOUNT_CONTEXT.add(value[2], order.amount)
        dates.append(order.time)
    days = (
        (datetime.fromisoformat(max(dates)) - datetime.fromisoformat(min(dates))).total_seconds()
        / 86400
        if dates
        else 0
    )
    return customers, days


def capability(allowed, reasons, limited=False, state=None):
    return {
        "allowed": allowed,
        "state": state
        or ("limited" if allowed and limited else "available" if allowed else "unavailable"),
        "reasons": reasons,
    }


def process_quality(
    source: Path,
    raw_source: Path,
    output: Path,
    mapping,
    policy,
    scope,
    context,
    progress=lambda *args: None,
):
    output.mkdir(parents=True, exist_ok=True)
    total_rows = pq.ParquetFile(source).metadata.num_rows
    if total_rows != pq.ParquetFile(raw_source).metadata.num_rows:
        raise ValueError("Raw/canonical row counts differ")
    orders, seen = {}, set()
    issues = Counter()
    missing = Counter()
    duplicate_count = 0
    zone = ZoneInfo(mapping.get("timezone") or "UTC")
    writer = RowsWriter(output / "normalized.parquet", NORMAL_SCHEMA)
    processed = 0
    try:
        pairs = zip(
            pq.ParquetFile(source).iter_batches(batch_size=2000),
            pq.ParquetFile(raw_source).iter_batches(batch_size=2000),
            strict=True,
        )
        for canonical_batch, raw_batch in pairs:
            for original, raw in zip(
                canonical_batch.to_pylist(), raw_batch.to_pylist(), strict=True
            ):
                assert original["source_row_id"] == raw.pop("source_row_id")
                fingerprint = hashlib.sha256(
                    json.dumps(raw, sort_keys=True, ensure_ascii=False).encode()
                ).digest()
                duplicate = fingerprint in seen
                seen.add(fingerprint)
                row = normalize(original, mapping, policy)
                row["duplicate_candidate"] = duplicate
                duplicate_count += int(duplicate)
                for key in FIELDS:
                    missing[key] += int(row.get(key) is None)
                issues.update(row["issues"])
                if row["order_id"]:
                    orders.setdefault(row["order_id"], Order()).observe(
                        row, policy, mapping["amount_mode"]
                    )
                writer.add(row)
                processed += 1
            progress("normalizing", int(35 * processed / max(1, total_rows)))
    finally:
        writer.close()
    del seen
    progress("selecting", 38)
    normalized = output / "normalized.parquet"
    for batch in pq.ParquetFile(normalized).iter_batches(batch_size=2000):
        for row in batch.to_pylist():
            order = orders.get(row["order_id"])
            if common_reason(row, order, {}, zone, policy) == "included":
                order.before_scope += 1
            if common_reason(row, order, scope, zone, policy) != "included":
                continue
            order.selected += 1
            value, _ = line_value(row, mapping["amount_mode"])
            if value is None or value <= 0:
                order.selected_lines_complete = False
            else:
                order.selected_line_sum = AMOUNT_CONTEXT.add(order.selected_line_sum, value)
            if row["item_id"]:
                order.items.add(row["item_id"])
    selected = {identity: order for identity, order in orders.items() if order.selected}
    for order in selected.values():
        finalize_order(order, mapping, policy)
    incomplete_customers = {
        o.customer
        for o in selected.values()
        if o.rf_reason == "included" and o.amount_reason != "included"
    }
    for order in selected.values():
        if order.rf_reason == "included" and order.customer in incomplete_customers:
            order.rfm_reason = "incomplete_customer_amount"
    # Monetary data is never silently imputed or combined across currencies.
    rf_orders = [o for o in selected.values() if o.rf_reason == "included"]
    rfm_orders = [o for o in selected.values() if o.rfm_reason == "included"]
    customers, span = customer_metrics(rf_orders)
    monetary_customers, monetary_span = customer_metrics(rfm_orders)
    currencies = sorted({o.currency for o in selected.values() if o.amount is not None})
    baskets = {
        identity: o for identity, o in selected.items() if o.items and not o.basket_incomplete
    }
    items = set()
    for order in baskets.values():
        items.update(order.items)
    max_basket = max((len(o.items) for o in baskets.values()), default=0)
    excluded_baskets = sum(o.basket_incomplete for o in selected.values())
    rf_errors, rfm_errors, basket_errors = [], [], []
    if mapping["order_boundary"] == "unavailable" or not mapping["columns"].get("order_id"):
        note = "订单边界尚未确认，请检查订单字段；不能凭商品行猜测订单。"
        rf_errors.append(note)
        rfm_errors.append(note)
        basket_errors.append(note)
    if not mapping["columns"].get("customer_id"):
        rf_errors.append("尚未对应客户标识，请检查字段或使用购物篮分析。")
        rfm_errors.append("尚未对应客户标识，请检查字段或使用购物篮分析。")
    if not mapping["columns"].get("event_time"):
        rf_errors.append("尚未对应交易时间，请检查字段。")
        rfm_errors.append("尚未对应交易时间，请检查字段。")
    elif not rf_orders and missing["event_time"]:
        rf_errors.append("时间缺失或不能按当前格式解析，请核对时间格式与时区。")
        rfm_errors.append("时间缺失或不能按当前格式解析，请核对时间格式与时区。")
    if not mapping["columns"].get("item_id"):
        basket_errors.append("尚未对应可靠商品标识，请检查商品字段。")
    if len(customers) < 50:
        rf_errors.append(f"有效客户 {len(customers)} 个，至少需要 50 个。")
    if span < 7:
        rf_errors.append("有效交易时间跨度不足 7 天。")
    if len({(v[0], v[1]) for v in customers.values()}) < 2:
        rf_errors.append("客户的购买频次与最近时间缺少差异。")
    if len(monetary_customers) < 50:
        rfm_errors.append(f"金额完整客户 {len(monetary_customers)} 个，至少需要 50 个。")
    if monetary_span < 7:
        rfm_errors.append("金额完整数据的时间跨度不足 7 天。")
    if len({tuple(v) for v in monetary_customers.values()}) < 2:
        rfm_errors.append("金额完整客户的购买行为缺少差异。")
    if mapping["amount_mode"] == "none":
        rfm_errors.append("未确认金额来源，可先使用 RF。")
    if len(currencies) > 1:
        rfm_errors.append("包含多种币种，请选择一种币种后重新检查。")
    if incomplete_customers and policy["monetary_subset"] != "complete_customers":
        rfm_errors.append("部分客户金额不完整；可使用 RF，或明确选择金额完整客户。")
    if any(o.amount_reason == "amount_source_conflict" for o in selected.values()):
        rfm_errors.append("存在金额来源不一致，请确认采用的口径后重新检查。")
    if len(baskets) < 200:
        basket_errors.append(f"完整有效购物篮 {len(baskets)} 个，至少需要 200 个。")
    if len(items) < 2:
        basket_errors.append("有效商品种类不足 2 类。")
    over_budget = len(baskets) > 100000 or len(items) > 5000 or max_basket > 100
    if over_budget:
        basket_errors.append("购物篮或商品规模超出分析范围，请缩小业务筛选范围。")
    caps = {
        "rf": capability(not rf_errors, rf_errors, len(rf_orders) < len(orders)),
        "rfm": capability(not rfm_errors, rfm_errors, len(rfm_orders) < len(orders)),
        "association": capability(
            not basket_errors,
            basket_errors,
            len(baskets) < len(orders),
            "resource_limited" if over_budget else None,
        ),
    }
    progress("preparing_views", 65)
    view_writers = {
        name: RowsWriter(output / (name + ".parquet"), ORDER_SCHEMA)
        for name in ["rf_orders", "rfm_orders", "amount_orders"]
    }
    basket_writer = RowsWriter(output / "basket_items.parquet", BASKET_SCHEMA)
    try:
        for identity, order in selected.items():
            record = {
                "order_id": identity,
                "customer_id": order.customer,
                "event_time": order.time,
                "currency": order.currency,
                "amount": str(order.amount) if order.amount is not None else None,
                "amount_source": order.amount_source,
                "source_rows": order.rows,
                "effective_source_rows": order.effective_rows,
                "selected_rows": order.selected,
                "partial_order": order.selected < order.effective_rows,
            }
            if order.rf_reason == "included":
                view_writers["rf_orders"].add(record)
            if order.rfm_reason == "included":
                view_writers["rfm_orders"].add(record)
            if order.amount_reason == "included":
                view_writers["amount_orders"].add(record)
            if identity in baskets:
                for item in sorted(order.items):
                    basket_writer.add({"order_id": identity, "item_id": item})
    finally:
        for view in view_writers.values():
            view.close()
        basket_writer.close()
    audit = RowsWriter(output / "row_audit.parquet", AUDIT_SCHEMA)
    counts = {name: Counter() for name in ["common", "rf", "rfm", "amount", "association"]}
    samples = []
    try:
        for batch in pq.ParquetFile(normalized).iter_batches(batch_size=2000):
            for row in batch.to_pylist():
                order = orders.get(row["order_id"])
                primary = common_reason(row, order, scope, zone, policy)
                reasons = {"common": primary}
                if primary != "included":
                    reasons.update(
                        {name: primary for name in ["rf", "rfm", "amount", "association"]}
                    )
                else:
                    reasons.update(
                        rf=order.rf_reason,
                        rfm=order.rfm_reason,
                        amount=order.amount_reason,
                        association="incomplete_basket" if order.basket_incomplete else "included",
                    )
                for name, reason in reasons.items():
                    counts[name][reason] += 1
                record = {
                    "source_row_id": row["source_row_id"],
                    "order_id": row["order_id"],
                    "item_id": row["item_id"],
                    "primary_reason": primary,
                    "rf_reason": reasons["rf"],
                    "rfm_reason": reasons["rfm"],
                    "amount_reason": reasons["amount"],
                    "association_reason": reasons["association"],
                    "issues": list(
                        dict.fromkeys(
                            row["issues"]
                            + (["duplicate_candidate"] if row["duplicate_candidate"] else [])
                            + (["order_conflict"] if order and order.conflict else [])
                        )
                    ),
                }
                audit.add(record)
                if len(samples) < 20 and any(v != "included" for v in reasons.values()):
                    samples.append(record)
    finally:
        audit.close()
    assert all(sum(c.values()) == total_rows for c in counts.values()), (
        "Exclusion accounting mismatch"
    )
    warnings = []
    if duplicate_count:
        strategy_name = "保留" if policy["duplicates"] == "keep" else "按确认策略移除"
        warnings.append(f"发现 {duplicate_count} 条完全重复候选；当前策略为{strategy_name}。")
    if incomplete_customers:
        warnings.append("金额不完整客户未进入 RFM 视图，RF 仍保留符合条件的客户。")
    if excluded_baskets:
        warnings.append(f"{excluded_baskets} 个已知不完整购物篮整体排除，未只删除坏行。")
    if any(o.amount_source == "selected_lines" for o in selected.values()):
        warnings.append("部分订单按可靠的保留行金额计算，未分摊原订单总额。")
    warnings.append("购物篮完整性仅针对所提供数据，不保证覆盖真实订单的全部明细。")
    reference_time = max((o.time for o in rf_orders), default=None)
    report = {
        "engine_version": "quality-v1",
        "context": context,
        "scope": scope,
        "policy": policy,
        "mapping": mapping,
        "raw_rows": total_rows,
        "unique_source_orders": len(orders),
        "duplicate_candidates": duplicate_count,
        "missing_counts": dict(missing),
        "issue_counts": dict(issues),
        "views": {
            key: {
                "included_rows": counter["included"],
                "excluded_rows": total_rows - counter["included"],
                "primary_reasons": dict(counter),
            }
            for key, counter in counts.items()
        },
        "summary": {
            "selected_orders": len(selected),
            "rf_orders": len(rf_orders),
            "rf_customers": len(customers),
            "unique_rf_profiles": len({(v[0], v[1]) for v in customers.values()}),
            "rfm_orders": len(rfm_orders),
            "rfm_customers": len(monetary_customers),
            "unique_rfm_profiles": len({tuple(v) for v in monetary_customers.values()}),
            "amount_orders": view_writers["amount_orders"].count,
            "currencies": currencies,
            "complete_baskets": len(baskets),
            "incomplete_baskets": excluded_baskets,
            "scope_empty_orders": sum(
                o.before_scope > 0 and not o.selected for o in orders.values()
            ),
            "orders_without_effective_rows": sum(not o.selected for o in orders.values()),
            "singleton_baskets": sum(len(o.items) == 1 for o in baskets.values()),
            "unique_items": len(items),
            "max_basket_size": max_basket,
            "time_span_days": round(span, 3),
            "latest_valid_order_time": reference_time,
            "incomplete_amount_customers": len(incomplete_customers),
        },
        "capabilities": caps,
        "warnings": warnings,
        "exclusion_samples": samples,
        "reason_labels": REASONS,
        "evidence": [
            {
                "evidence_id": f"{context['run_id']}:quality:{key}",
                "metric_name": key,
                "numerator": counter["included"],
                "denominator": total_rows,
                "unit": "rows",
                "value": counter["included"],
                "filters": scope,
                "limitations": "Effective views differ by capability",
                **context,
            }
            for key, counter in counts.items()
        ],
    }
    (output / "quality_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    progress("publishing", 95)
    return report
