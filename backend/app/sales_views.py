"""Read projections of immutable sales reports; no analysis is recalculated here."""

import hashlib
import json
import os
import shutil
import tempfile
import threading
import zipfile
from pathlib import Path

from .sales_actions import action_view, build_actions

VIEW_DIR = ".sales-views-v6"
_build_lock = threading.Lock()


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def product_key(item_id):
    return hashlib.sha256(item_id.encode("utf-8")).hexdigest() + ".json"


def write_views(output, report):
    """Publish all derived files together so readers never see a partial cache."""
    output = Path(output)
    target = output / VIEW_DIR
    if target.is_dir():
        return target
    output.mkdir(parents=True, exist_ok=True)
    trial = Path(tempfile.mkdtemp(prefix=".sales-views-building-", dir=output))
    try:
        from .sales_focus import focus_view
        report = focus_view(action_view(report), output)
        products = report["products"]
        counts = {
            "forecast": sum(bool(p.get("forecast")) for p in products),
            "anomaly": sum(bool(p.get("anomalies")) for p in products),
            "has_daily": any(p.get("daily") for p in products),
        }
        base = {**report, "workspace_counts": counts}
        candidates = build_actions(products, parameters=report.get("parameters"),
                                   summary=report.get("summary"), month=report.get("month"), limit=None)
        action_input = {k: report.get(k) for k in ["context", "month", "summary", "sources", "parameters"]}
        action_input.update(candidates=candidates,
                            previous_actions=report.get("previous_actions", []) + report.get("actions", []),
                            products=[{k: p.get(k) for k in ["id", "name", "quantity", "amount", "item_type"]} for p in products])
        (trial / "action-input.json").write_bytes(encode(action_input))
        base.pop("actions", None)
        base.pop("previous_actions", None)
        # The list keeps every field used by sorting, filtering and type review.
        # Only the large daily series is fetched separately on opening a product.
        compact = [{**p, "daily": [], "has_daily": bool(p.get("daily"))} for p in products]
        (trial / "products.json").write_bytes(encode({**base, "products": compact}))
        wanted = set(report["highlights"]) | {a["item_id"] for a in report["actions"]}
        overview = {**base, "products": [p for p in products if p["id"] in wanted]}
        changes = report.get("change_drivers")
        if changes:
            overview["change_drivers"] = {**changes, "items": changes.get("items", [])[:5]}
        (trial / "overview.json").write_bytes(encode(overview))
        with zipfile.ZipFile(trial / "details.zip", "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
            for product in products:
                archive.writestr(product_key(product["id"]), encode(product))
        (trial / "manifest.json").write_bytes(encode({"run_id": report["context"]["run_id"]}))
        try:
            os.rename(trial, target)
        except OSError:
            if not target.is_dir():
                raise
        return target
    finally:
        if trial.exists():
            shutil.rmtree(trial)


def ensure_views(output, run_id, load_report):
    target = Path(output) / VIEW_DIR
    if (target / "manifest.json").is_file():
        return target
    # Used once for old reports; new reports create projections in the worker.
    with _build_lock:
        if not (target / "manifest.json").is_file():
            report = load_report()
            if report["context"]["run_id"] != run_id:
                raise ValueError("Report identity mismatch")
            return write_views(output, report)
    return target


def product_bytes(directory, item_id):
    with zipfile.ZipFile(Path(directory) / "details.zip") as archive:
        return archive.read(product_key(item_id))
