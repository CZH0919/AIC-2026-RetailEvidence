"""Specific, user-facing reasons for withholding a sales forecast."""

REASONS = {
    "monthly_summary": (
        "这份表按月汇总，无法还原每天的销量。",
        "请上传带销售日期和数量的订单明细或每日汇总。",
    ),
    "coverage_unconfirmed": (
        "尚未确认完整的销售日期范围。",
        "重新生成月报时，请核对记录是否完整，并填写覆盖日期和缺失日期。",
    ),
    "month_incomplete": (
        "确认的记录范围没有覆盖分析月份的全部日期。",
        "补齐该月记录后重新分析；缺失记录不能当作零销量。",
    ),
    "check_only": (
        "这次只核对销售记录，没有计算预测。",
        "在销售总览在“更多”中选择“生成月报”，核对记录范围后开始分析。",
    ),
    "history_short": (
        "用于预测的日记录范围不足 90 天。",
        "补充至少 90 天的完整日记录，再重新分析。",
    ),
    "item_history_short": (
        "这款商品的早期记录不足以检验预测效果。",
        "补充该商品更早的完整日记录；首次出现前的日期不会自动当作零销量。",
    ),
    "recent_history_short": (
        "这款商品还没有连续 90 天的可用日记录。",
        "积累或补充该商品至少 90 天的完整日记录，再重新分析。",
    ),
    "missing_days": (
        "这款商品的历史记录中有缺失日期，无法连续比较销量。",
        "核对并补齐缺失日期；已确认未营业的日期应标为停业，不能用零填补未知记录。",
    ),
    "early_sales_sparse": (
        "早期连续 28 天内，成交日期少于 4 天，无法可靠检验预测效果。",
        "继续积累重复成交记录；目前可以先查看已记录销量和商品贡献。",
    ),
    "recent_sales_sparse": (
        "最近 28 天内，成交日期少于 4 天。",
        "继续积累成交记录，当前先依据实际销量安排经营。",
    ),
    "capacity_limit": (
        "本次预测已达到 1,000 个商品的处理上限，未包含这款商品。",
        "如需单独分析，请整理同一业务范围内、商品更少的销售表。",
    ),
    "comparison_unavailable": (
        "可用于核对预测效果的连续历史记录不足。",
        "补齐历史记录后重新分析；当前仍可查看实际销售表现。",
    ),
    "validation_error": (
        "这款商品的历史预测误差较大，暂不提供数量参考。",
        "先核对异常销售、缺货或漏记情况，再结合实际销量判断；补充新记录后可重新分析。",
    ),
    "no_eligible_items": ("当前没有满足预测条件的商品。", "在商品详情中查看各商品缺少的条件。"),
}


def unavailable(code):
    message, next_step = REASONS[code]
    return {"code": code, "message": message, "next_step": next_step}


def report_blocker(kind, complete, complete_month, check_only):
    if kind == "monthly_summary":
        return unavailable("monthly_summary")
    if check_only:
        return unavailable("check_only")
    if not complete:
        return unavailable("coverage_unconfirmed")
    if not complete_month:
        return unavailable("month_incomplete")
    return None
