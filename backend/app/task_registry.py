"""Explicit extension points; adding an algorithm never enables browser-supplied code."""

TASK_SPECS = {
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
}


def run_registered(job, progress):
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
    raise ValueError("Unsupported job kind")


def completion_state(kind, report):
    if kind == "quality":
        caps = report["capabilities"]
        if not any(c["allowed"] for c in caps.values()):
            return "not_applicable"
        if report["duplicate_candidates"] or any(c["state"] != "available" for c in caps.values()):
            return "completed_with_warnings"
        return "succeeded"
    raise ValueError("Unsupported result kind")
