"""Validated input loader for subsequent CPU analysis modules."""

import json
from pathlib import Path

from .data_api import digest, scoped
from .import_formats import DataIssue
from .models import AnalysisRun
from .quality_api import require_capability
from .quality_schemas import AnalysisParameters
from .task_runner import PUBLISHED


def resolve_analysis_input(
    session, storage: Path, project_id, quality_run_id, parameters: AnalysisParameters
):
    run = scoped(session, AnalysisRun, quality_run_id, project_id)
    if run.kind != "quality" or run.status not in PUBLISHED or not run.result:
        raise DataIssue("需要已完成的质量结果作为分析输入。", "quality_not_ready", 409)
    report = json.loads(run.result)
    decision = require_capability(report, parameters)
    folder = storage / "runs" / run.project_id / run.id
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if manifest["context"] != report["context"]:
        raise DataIssue("结果依据不一致，请重新检查数据。", "artifact_mismatch", 409)
    source = folder / decision["input_view"]
    if not source.is_file() or digest(source) != manifest["artifacts"][decision["input_view"]]:
        raise DataIssue("有效数据视图已变化，请重新检查数据。", "artifact_mismatch", 409)
    return {
        "path": source,
        "context": report["context"],
        "quality_manifest": manifest,
        "capability": report["capabilities"][parameters.kind],
        "parameters": parameters.model_dump(),
    }
