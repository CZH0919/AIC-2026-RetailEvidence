"""Deterministic explanations of verified facts and product limits, never labelled inference."""

import re

METHODS = {
    "four_week_mean": "过去四周平均参考",
    "last_week": "上一周销量参考",
    "gradient_boosting": "历史销售模型",
}


def product_explanation(report, question, item_id=None):
    item = next((p for p in report["products"] if p["id"] == item_id), None)

    def result(text, mode="evidence_explanation", refs=None):
        return {
            "answer": text,
            "mode": mode,
            "ai_used": False,
            "references": refs or (["item", "forecast"] if item else ["summary", "forecast"]),
        }

    if re.search(
        r"内部提示词|系统提示词|模型内部|服务器.*(?:路径|文件|端口)|开发操作|执行.*(?:命令|代码)|忽略.*规则",
        question,
    ):
        return result(
            "销售助手用于解释销售数据，不能提供内部指令、服务器信息或执行开发操作。你可以询问本月销售情况或商品变化。",
            "out_of_scope",
            ["summary"],
        )
    if "客户分群" in question:
        return result(
            "客户分群需要稳定的客户编号、订单和购买时间；加入购买金额还需要可靠的金额记录。缺少这些信息时不能可靠分组。请到“更多分析”查看这份数据的实际适用条件，销售月报不能代替那里的数据检查。",
            "knowledge_explanation",
            ["quality"],
        )
    if any(word in question for word in ["支持度", "提升度", "置信度"]):
        return result(
            "支持度表示全部购物篮中两件商品一起出现的比例；置信度表示买了前一件商品的篮子中，也有后一件的比例。提升度与后一件平时的出现比例比较，较高也不代表因果或经营收益。共购结果还要看样本数与质量检查。",
            "knowledge_explanation",
            ["quality"],
        )
    if item and any(word in question for word in ["值得关注", "值得留意", "需要核对的证据"]):
        reason = item.get("reason") or "当前没有足够依据标出特别变化。"
        return result(
            reason
            + " 这是销售记录中的变化，不能据此断定缺货或促销原因；请查看异常日期及原始记录。",
            refs=["item", "anomaly"],
        )
    if item and ("异常" in question or "标记" in question):
        dates = re.findall(r"\d{4}-\d{2}-\d{2}", question)
        anomaly = next((a for a in item.get("anomalies", []) if a["date"] in dates), None)
        if anomaly:
            return result(
                f"{anomaly['date']}的实际销量为{anomaly['actual']:g}，历史参考中位数为{anomaly['reference']:g}。该日销售偏离历史表现，值得核对，但不证明经营发生问题，也不能据此确定原因。",
                refs=["item", "anomaly"],
            )
        return result(
            "异常标记表示当天销量偏离历史表现，不等于已经查明经营问题。请点击异常日期查看实际销量、历史参考和来源记录，再在问题中写明日期；缺货、促销或漏记都需要你核实。",
            "clarification",
            ["item", "anomaly"],
        )
    if "预测" in question or "七天" in question or "进货" in question or "补货" in question:
        forecast = item.get("forecast") if item else None
        if not forecast:
            if not item and report.get("forecast", {}).get("published_items"):
                return result(
                    "本次报告有部分商品的可用预测，请先打开要核对的商品详情。销售表不能自动确认库存，也不能仅凭预测确定进货量；涉及利润还需要成本与费用资料。",
                    "clarification"
                    if "预测" in question and "利润" not in question
                    else "data_limit",
                )
            return result(
                "这份月报或当前商品没有可用的七天预测。请在商品详情查看历史长度、逐日记录与回测限制；不能把本月销量直接当作采购量。",
                "data_limit",
            )
        quantity = forecast["quantity"]
        method = METHODS.get(forecast["method"], "已核对的历史方法")
        detail = {
            "four_week_mean": "参考最近四周的销售记录估计七天累计销量",
            "last_week": "用上一周的销量作七天参考",
            "gradient_boosting": "用历史销量特征估计，再与简单历史方法比较",
        }.get(forecast["method"], "依据历史销量并进行回测")
        text = (
            f"本商品采用{method}，{detail}。"
            f"{forecast['start']}至{forecast['end']}约{quantity:,.2f}{report['summary']['unit']}；"
            f"历史验证中七天总量平均差约{forecast['validation_mae']:,.2f}{report['summary']['unit']}。"
            "预测不能直接等同采购量；还要核对预测起点的可售库存、确定到货、备用量和包装单位。"
            "销售表不能自动确认这些库存信息，也不保证不会缺货。"
        )
        return result(text)
    return None
