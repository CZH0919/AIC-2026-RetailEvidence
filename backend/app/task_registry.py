"""Explicit extension points; adding an algorithm never enables browser-supplied code."""

TASK_SPECS = {
    "sales": {
        "report": "sales_report.json",
        "artifacts": [
            "sales_report.json",
            "sales_products.csv",
            "sales_row_audit.csv",
            "sales_backtests.csv",
        ],
    },
    "quality": {
        "report": "quality_report.json",
        "artifacts": [
            "normalized.parquet",
            "row_audit.parquet",
            "rf_orders.parquet",
            "rfm_orders.parquet",
            "amount_orders.parquet",
            "basket_items.parquet",
            "quality_report.json",
        ],
    },
    "clustering": {
        "report": "cluster_report.json",
        "artifacts": [
            "customer_features.parquet",
            "cluster_assignments.csv",
            "cluster_candidates.csv",
            "cluster_report.json",
        ],
    },
    "association": {
        "report": "association_report.json",
        "artifacts": [
            "frequent_itemsets.csv",
            "association_rules.csv",
            "completion_evaluation.csv",
            "association_report.json",
        ],
    },
}


def run_registered(job, progress):
    if job["kind"] == "sales":
        from .retail_engine import process_retail

        return process_retail(job, progress)
    if job["kind"] == "quality":
        from pathlib import Path

        from .quality import process_quality

        return process_quality(
            Path(job["source"]),
            Path(job["raw_source"]),
            Path(job["output"]),
            job["mapping"],
            job["policy"],
            job["scope"],
            job["context"],
            progress,
        )
    if job["kind"] == "clustering":
        from .clustering import process_clustering

        return process_clustering(job, progress)
    if job["kind"] == "association":
        from .association import process_association

        return process_association(job, progress)
    raise ValueError("Unsupported job kind")


def completion_state(kind, report):
    if kind == "sales":
        if not report["summary"]["products"]:
            return "not_applicable"
        return (
            "completed_with_warnings"
            if report["quality"]["excluded_rows"] or not report["summary"]["complete_month"]
            else "succeeded"
        )
    if kind == "quality":
        caps = report["capabilities"]
        if not any(c["allowed"] for c in caps.values()):
            return "not_applicable"
        if report["duplicate_candidates"] or any(c["state"] != "available" for c in caps.values()):
            return "completed_with_warnings"
        return "succeeded"
    if kind == "clustering":
        if not report["summary"]["customers"] or not report["candidates"]:
            return "not_applicable"
        if not report["summary"]["publishable"]:
            return "completed_with_warnings"
        return "succeeded"
    if kind == "association":
        if not report["summary"]["baskets"]:
            return "not_applicable"
        if not report["summary"]["publishable"]:
            return "completed_with_warnings"
        return "succeeded"
    raise ValueError("Unsupported result kind")
