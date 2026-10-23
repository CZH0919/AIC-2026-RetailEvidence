"""Delete a project and its owned records, retaining a server-side recovery copy."""

import json
import shutil
from uuid import UUID, uuid4

from fastapi import Query
from sqlalchemy import delete, select, update

from .import_formats import DataIssue
from .import_jobs import exclusive
from .models import (
    AnalysisRun, CleaningPolicy, DatasetVersion, ImportDraft, MappingVersion,
    Project, RunEvent, SalesRecord,
)
from .task_runner import TERMINAL


def install_project_deletion(app):
    @app.delete("/api/projects/{project_id}")
    async def delete_project(project_id: UUID, revision: int = Query(ge=1)):
        identity = str(project_id)
        # Reuse the import/worker lease so files cannot be written while moved.
        async with exclusive(app):
            with app.state.sessions() as session:
                moved = []
                try:
                    # Acquire the SQLite write lock and reject an outdated confirmation.
                    changed = session.execute(update(Project).where(
                        Project.id == identity, Project.revision == revision,
                    ).values(revision=revision + 1))
                    if changed.rowcount != 1:
                        if session.get(Project, identity) is None:
                            raise DataIssue("这个店铺已不存在，请刷新列表。", "not_found", 404)
                        raise DataIssue("店铺资料已更新，请刷新后再删除。", "revision_conflict", 409)
                    active = session.scalar(select(AnalysisRun.id).where(
                        AnalysisRun.project_id == identity,
                        AnalysisRun.status.not_in(TERMINAL),
                    ).limit(1))
                    if active:
                        raise DataIssue("这个店铺还有分析任务，请先完成或停止任务，再删除。", "project_busy", 409)
                    version_ids = list(session.scalars(select(DatasetVersion.id).where(DatasetVersion.project_id == identity)))
                    run_ids = list(session.scalars(select(AnalysisRun.id).where(AnalysisRun.project_id == identity)))
                    draft_ids = list(session.scalars(select(ImportDraft.id).where(ImportDraft.project_id == identity)))
                    owned = [
                        (SalesRecord, SalesRecord.run_id.in_(run_ids)),
                        (RunEvent, RunEvent.run_id.in_(run_ids)),
                        (AnalysisRun, AnalysisRun.project_id == identity),
                        (CleaningPolicy, CleaningPolicy.dataset_version_id.in_(version_ids)),
                        (MappingVersion, MappingVersion.dataset_version_id.in_(version_ids)),
                        (DatasetVersion, DatasetVersion.project_id == identity),
                        (ImportDraft, ImportDraft.project_id == identity),
                        (Project, Project.id == identity),
                    ]
                    storage = app.state.storage.resolve()
                    backup = storage / "deleted_projects" / f"{identity}-{uuid4()}"
                    backup.mkdir(parents=True)
                    rows = {model.__tablename__: [dict(row) for row in session.execute(
                        select(model.__table__).where(condition)
                    ).mappings()] for model, condition in owned}
                    # Restore the original revision in the recovery copy.
                    rows["projects"][0]["revision"] = revision
                    (backup / "records.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
                    paths = [storage / "datasets" / "projects" / identity, storage / "runs" / identity]
                    paths += [storage / "imports" / str(UUID(value)) for value in draft_ids]
                    paths += [storage / "run_logs" / f"{UUID(value)}.log" for value in run_ids]
                    for source in paths:
                        if source.is_symlink() or not source.resolve().is_relative_to(storage):
                            raise DataIssue("数据目录无法安全处理，请联系维护者。", "storage_path_invalid", 503)
                        if source.exists():
                            destination = backup / "files" / source.relative_to(storage)
                            destination.parent.mkdir(parents=True, exist_ok=True)
                            shutil.move(str(source), str(destination))
                            moved.append((source, destination))
                    for model, condition in owned:
                        session.execute(delete(model).where(condition))
                    session.commit()
                except Exception:
                    session.rollback()
                    for source, destination in reversed(moved):
                        source.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(destination), str(source))
                    raise
        return {"id": identity, "deleted": True}
