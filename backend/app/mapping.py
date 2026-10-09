"""Conservative name-based suggestions; business meaning always needs confirmation."""

import re
from datetime import datetime

from .data_schemas import FIELDS, MappingInput
from .import_formats import DataIssue

ALIASES = {
    "order_id": ["orderid", "invoiceno", "invoice", "basketid", "订单编号", "订单号", "购物篮编号"],
    "item_id": ["itemid", "productid", "stockcode", "商品编号", "商品编码"],
    "item_name": ["itemname", "productname", "description", "商品名称"],
    "customer_id": ["customerid", "客户编号", "客户id"],
    "event_time": [
        "eventtime",
        "invoicedate",
        "orderdate",
        "date",
        "日期",
        "销售日期",
        "交易时间",
        "订单时间",
    ],
    "quantity": ["quantity", "qty", "数量", "销量", "销售数量"],
    "unit_price": ["unitprice", "单价"],
    "line_amount": ["lineamount", "linetotal", "行金额", "明细金额", "销售额", "实收金额"],
    "order_amount": ["orderamount", "ordertotal", "订单总额"],
    "currency": ["currency", "币种"],
    "record_status": ["recordstatus", "orderstatus", "交易状态"],
    "country": ["country", "国家", "地区"],
    "category": ["category", "商品分类"],
}


def normalize(text):
    return re.sub(r"[\s_\-]", "", text).casefold()


def suggestions(columns):
    proposed, warnings = {}, []
    for field, aliases in ALIASES.items():
        matches = [c["key"] for c in columns if normalize(c["name"]) in aliases]
        if len(matches) == 1:
            proposed[field] = matches[0]
        elif matches:
            warnings.append(f"「{FIELDS[field]}」有多个候选列，请手动选择。")
    for c in columns:
        if normalize(c["name"]) in {"amount", "total", "price", "金额", "总价"}:
            warnings.append(f"「{c['name']}」的金额层级不明确，未自动映射。")
    return {"columns": proposed, "warnings": warnings, "method": "exact_alias_v1"}


def validate_mapping(mapping: MappingInput, preview: dict, options: dict, confirm=True):
    columns = {c["key"] for c in preview["columns"]}
    chosen = {k: v for k, v in mapping.columns.items() if v}
    if set(chosen.values()) - columns:
        raise DataIssue("字段对应关系已失效，请重新选择。", "mapping_columns")
    if confirm and not mapping.confirmed:
        raise DataIssue("请确认字段和业务含义后再保存。", "confirmation_required")
    if not chosen:
        raise DataIssue("请至少对应一个字段。", "mapping_empty")
    if mapping.record_kind == "monthly_summary" and not mapping.summary_month:
        raise DataIssue("月汇总需要确认所属月份。", "summary_month_required")
    if mapping.record_kind != "transactions" and (
        mapping.order_boundary != "unavailable"
        or chosen.get("order_id")
        or mapping.amount_mode == "order_amount"
    ):
        raise DataIssue(
            "销售汇总没有逐笔订单，请取消订单字段并使用行金额或不使用金额。", "summary_boundary"
        )
    if mapping.order_boundary != "unavailable" and not chosen.get("order_id"):
        raise DataIssue("请指定订单或购物篮标识列；无法确定时选择边界未知。")
    if mapping.order_boundary == "unavailable" and chosen.get("order_id"):
        raise DataIssue("已指定订单标识，请明确其订单 / 购物篮含义。")
    if mapping.order_boundary == "row_basket" and options["shape"] != "basket_list":
        raise DataIssue("只有明确选择每行一个购物篮时，才能使用原始行作为篮子边界。")
    if options["shape"] == "basket_list" and (
        mapping.order_boundary != "row_basket"
        or chosen.get("order_id") != "c0"
        or chosen.get("item_id") != "c1"
    ):
        raise DataIssue("每行购物篮格式必须保留生成的购物篮标识与商品标识。")
    needed = {
        "line_amount": ["line_amount"],
        "quantity_unit_price": ["quantity", "unit_price"],
        "order_amount": ["order_amount", "order_id"],
    }.get(mapping.amount_mode, [])
    if any(not chosen.get(key) for key in needed):
        raise DataIssue("当前金额口径缺少对应字段，请补充或选择不使用金额。")
    if mapping.amount_mode != "none" and not (mapping.currency_constant or chosen.get("currency")):
        raise DataIssue("使用金额前请明确币种。")
    if mapping.currency_constant and chosen.get("currency"):
        raise DataIssue("币种列与固定币种只能选择一种来源。")
    if chosen.get("quantity") and not mapping.quantity_unit.strip():
        raise DataIssue("请说明数量单位，例如件、包或原始单位。")
    if chosen.get("event_time") and not (mapping.time_format and mapping.timezone):
        raise DataIssue("请明确交易时间格式和所属时区。")
    if mapping.status_rule == "uci_cancel_prefix" and not chosen.get("order_id"):
        raise DataIssue("C 前缀规则需要订单标识列。")
    if mapping.status_rule == "status_column" and (
        not chosen.get("record_status") or not mapping.status_values
    ):
        raise DataIssue("请指定状态列，并填写原始状态与含义的对应关系。")
    warnings = []
    if mapping.order_boundary == "unavailable":
        warnings.append("订单边界未知，暂不声明订单或购物篮分析能力。")
    if mapping.status_rule == "unspecified":
        warnings.append("取消 / 退货含义尚不明确，保留原始记录，后续需核验。")
    if mapping.amount_mode == "order_amount":
        warnings.append("订单总额只可按订单计一次，不可逐行累加；同单金额冲突需拦截。")
    if mapping.amount_mode == "quantity_unit_price":
        warnings.append("数量 × 单价仅用于确认的完整明细，缺失值保留未知，不填零。")
    time_key = chosen.get("event_time")
    if time_key:
        bad = 0
        for row in preview["rows"]:
            value = row.get(time_key)
            if value:
                try:
                    if mapping.time_format == "iso8601":
                        datetime.fromisoformat(value.replace("Z", "+00:00"))
                    else:
                        datetime.strptime(value, mapping.time_format)
                except ValueError:
                    bad += 1
        if bad:
            warnings.append(f"预览中有 {bad} 条时间与选定格式不一致，原值将保留待核验。")
    return {
        "warnings": warnings,
        "checked_preview_rows": len(preview["rows"]),
        "quality_processing": "pending",
        "business_aggregation": "not_performed",
    }
