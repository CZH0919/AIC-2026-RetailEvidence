"""Comparable periods and explicit per-product anomaly coverage for report readers."""

from calendar import monthrange
from copy import deepcopy
from datetime import date, timedelta

SIGNAL_VERSION = "sales-signals-v1"


def calendar_days(start, end):
    start, end = date.fromisoformat(start), date.fromisoformat(end)
    return [(start + timedelta(days=i)).isoformat() for i in range((end - start).days + 1)]


def unexplained_gaps(observed, start, end, closed=()):
    """Three consecutive store-wide absent days warrant checking, not zero fill.

    A single item's absence is not a store-wide gap. Explicit closures explain
    missing store records; normal isolated weekly days off remain unaffected.
    """
    observed, closed = set(observed), set(closed)
    gaps, block = [], []
    for day in calendar_days(start, end) + [None]:
        if day and day not in observed and day not in closed:
            block.append(day)
        else:
            if len(block) >= 3:
                gaps.extend(block)
            block = []
    return gaps


def comparison(month, current, previous, daily=False):
    start = date.fromisoformat(month + "-01")
    end = start.replace(day=monthrange(start.year, start.month)[1])
    previous_end = start - timedelta(days=1)
    return {
        "kind": "week" if daily else "month",
        "current_start": (end - timedelta(days=6)).isoformat() if daily else start.isoformat(),
        "current_end": end.isoformat(),
        "previous_start": (end - timedelta(days=13)).isoformat() if daily else previous_end.replace(day=1).isoformat(),
        "previous_end": (end - timedelta(days=7)).isoformat() if daily else previous_end.isoformat(),
        "current_quantity": current, "previous_quantity": previous,
        "status": "available" if previous is not None and previous > 0 else "no_baseline",
    }


def comparison_text(c):
    if c["status"] == "missing_records":
        return "这段时间没有完整的销售记录，暂不比较。"
    if c["status"] == "closed":
        return "比较期间包含停业日期，暂不比较销量涨跌。"
    if c["status"] == "legacy_unknown":
        return "旧报告未保存完整的比较数量，请重新生成月报。"
    if c["current_quantity"] is None or c["previous_quantity"] is None:
        return "比较期间的记录不足，暂不比较。"
    scope = (f'{c["current_start"]} 至 {c["current_end"]} 售出 {c["current_quantity"]:g}，'
             f'{c["previous_start"]} 至 {c["previous_end"]} 售出 {c["previous_quantity"]:g}。')
    return scope + ("前期销量为零，不计算涨跌百分比。" if c["previous_quantity"] == 0 else "")


def anomaly_check(product, report, gaps):
    daily = product.get("daily", [])
    saved = product.get("anomaly_check")
    anomalies = product.get("anomalies", [])
    if not daily:
        return {"status": "monthly_summary", "message": "需要每天的销售记录，才能检查异常日期。", "tested_dates": []}
    if saved:
        result = dict(saved)
        result["tested_dates"] = [d for d in saved.get("tested_dates", []) if d not in gaps]
        if result["tested_dates"]:
            result["status"] = "detected" if anomalies else "clear"
            result["message"] = f"{len(anomalies)}天销量明显偏高或偏低" if anomalies else "已检查的日期未发现明显异常"
        elif saved.get("tested_dates"):
            result.update(status="insufficient", message="销售记录不完整，暂时无法检查异常。")
        return result
    if anomalies:
        return {"status": "detected", "message": f"{len(anomalies)}天销量明显偏高或偏低", "tested_dates": None,
                "reference_label": "此前相同星期的通常销量" if report.get("anomaly", {}).get("method", "").startswith("weekday_") else "历史参考销量",
                "coverage_note": "旧报告未记录完整的检查日期。"}
    if report.get("anomaly", {}).get("status") == "unavailable":
        incomplete = not report.get("summary", {}).get("complete_month") or bool(gaps)
        return {"status": "insufficient", "message": "销售记录不完整，暂时无法检查异常。" if incomplete else "历史记录不足，暂时无法判断。", "tested_dates": []}
    return {"status": "legacy_unknown", "message": "旧报告未记录这件商品是否完成异常检查。", "tested_dates": None}


def signal_view(report):
    """Apply display corrections without modifying the stored report or its totals."""
    if report.get("signal_version") == SIGNAL_VERSION or not report.get("month"):
        return report
    report = deepcopy(report)
    products = report.get("products", [])
    params = report.get("parameters", {})
    month = report["month"]
    start = month + "-01"
    end = f'{month}-{monthrange(int(month[:4]), int(month[5:]))[1]:02d}'
    closed = set(params.get("closed_dates", []))
    observed = {d["date"] for p in products for d in p.get("daily", []) if d.get("recorded") or (d.get("quantity") or 0) > 0}
    gaps = set(report.get("coverage", {}).get("unexplained_dates", []))
    if any(p.get("daily") for p in products):
        gaps.update(unexplained_gaps(observed, start, end, closed))
    gaps.update(params.get("missing_dates", []))
    report["coverage"] = {**report.get("coverage", {}), "unexplained_dates": sorted(gaps)}
    for p in products:
        daily = p.get("daily", [])
        for d in daily:
            if d["date"] in gaps:
                d["quantity"] = None
        if daily:
            c = comparison(month, None, None, True)
            window = [d for d in daily if c["previous_start"] <= d["date"] <= c["current_end"]]
            if any(d["date"] in closed for d in window):
                c["status"] = "closed"
            elif (not report.get("summary", {}).get("complete_month") or len(window) != 14
                  or any(d.get("quantity") is None for d in window)):
                c["status"] = "missing_records"
            else:
                c = comparison(month, sum(d["quantity"] for d in window[-7:]), sum(d["quantity"] for d in window[:7]), True)
        else:
            c = p.get("comparison")
            if not c:
                prior = (p.get("contribution") or {}).get("previous_quantity")
                change = p.get("change")
                if prior is None and change is not None and change > -1:
                    prior = round(p["quantity"] / (1 + change), 6)
                c = comparison(month, p.get("quantity"), prior)
                if prior is None:
                    c["status"] = "legacy_unknown"
                elif change is None:
                    c["status"] = "missing_records"
        p["comparison"] = c
        p["change"] = ((c["current_quantity"] - c["previous_quantity"]) / c["previous_quantity"]
                       if c["status"] == "available" else None)
        p["flags"] = [f for f in p.get("flags", []) if f not in ("growth", "decline", "anomaly")]
        if p["change"] is not None and abs(p["change"]) >= .25 and abs(c["current_quantity"] - c["previous_quantity"]) >= 3:
            p["flags"].append("growth" if p["change"] > 0 else "decline")
        p["anomalies"] = [a for a in p.get("anomalies", []) if a["date"] not in gaps]
        # Old aggregated events cannot be safely adjusted after removing dates.
        p["anomaly_events"] = [e for e in p.get("anomaly_events", []) if not set(e.get("dates", [])) & gaps]
        if p["anomalies"]:
            p["flags"].append("anomaly")
        p["anomaly_check"] = anomaly_check(p, report, gaps)
        p["reason"] = comparison_text(c) + " " + p["anomaly_check"]["message"]
        if p.get("focus_reason"):
            p["focus_reason"] = comparison_text(c)
    for d in report.get("chart", []):
        if d["date"] in gaps:
            d["quantity"], d["amount"] = None, None
    report["attention_ids"] = [p["id"] for p in products if p["flags"]]
    report["highlights"] = [k for k in report.get("highlights", []) if k in set(report["attention_ids"])]
    report["summary"]["attention_total"] = len(report["attention_ids"])
    report["signal_version"] = SIGNAL_VERSION
    return report
