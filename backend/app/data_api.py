"""Project-scoped imports and append-only dataset / mapping versions."""

import asyncio
import hashlib
import json
import re
import shutil
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import func, select

from .data_schemas import ConfirmImport, ParseOptions, ReviseMapping, SaveDraft
from .import_formats import DataIssue
from .import_jobs import exclusive, run_job
from .mapping import validate_mapping
from .models import DatasetVersion, ImportDraft, MappingVersion, Project, timestamp
from .settings import MAX_FILE_BYTES


def dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2)


def write_json(path, value):
    path.write_text(dump(value) + "\n", encoding="utf-8")


def digest(path):
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024**2), b""):
            sha.update(chunk)
    return sha.hexdigest()


def safe_filename(value):
    name = value.replace("\\", "/").split("/")[-1]
    if not name or len(name) > 200 or re.search(r"[\x00-\x1f\x7f]", name):
        raise DataIssue("文件名需为 1–200 个字符，且不包含控制字符。")
    suffix = Path(name).suffix.lower()
    if suffix not in {".csv", ".xlsx"}:
        raise DataIssue("仅支持 CSV 和 XLSX 文件。", "unsupported_format", 415)
    return name, suffix


def scoped(session, cls, identity, project_id):
    value = session.get(cls, str(identity))
    if value is None or value.project_id != str(project_id):
        raise HTTPException(404, "没有找到这份数据，请返回项目重新选择。")
    return value


def require_project(session, project_id):
    if not session.get(Project, str(project_id)):
        raise HTTPException(404, "这个项目不存在，请返回项目库重新选择。")


def latest_mapping(session, version_id):
    return session.scalar(
        select(MappingVersion)
        .where(MappingVersion.dataset_version_id == version_id)
        .order_by(MappingVersion.revision.desc())
        .limit(1)
    )


def mapping_read(row):
    return {
        "id": row.id,
        "revision": row.revision,
        "created_at": row.created_at,
        "config": json.loads(row.config),
        "validation": json.loads(row.validation),
    }


def version_read(session, row, full=True):
    result = {
        k: getattr(row, k)
        for k in (
            "id",
            "project_id",
            "number",
            "filename",
            "sha256",
            "bytes",
            "row_count",
            "source_dataset",
            "created_at",
        )
    }
    current = latest_mapping(session, row.id)
    result["mapping_revision"] = current.revision
    if full:
        result.update(
            options=json.loads(row.options),
            preview=json.loads(row.preview),
            mapping=mapping_read(current),
        )
    return result


def draft_read(row):
    return {
        **{
            k: getattr(row, k)
            for k in (
                "id",
                "filename",
                "suffix",
                "bytes",
                "sha256",
                "source_dataset",
                "created_at",
                "preview_token",
                "finalized_version_id",
            )
        },
        **{
            k: json.loads(getattr(row, k)) if getattr(row, k) else None
            for k in ("inspection", "options", "preview", "mapping_draft")
        },
    }


def check_token(draft, token):
    if not draft.preview_token or token != draft.preview_token:
        raise DataIssue("文件预览已变化，请重新预览并确认。", "preview_conflict", 409)


def install_data_routes(app):
    router = APIRouter(prefix="/api")

    def draft_dir(identity):
        return app.state.storage / "imports" / str(identity)

    def version_dir(project_id, identity):
        return app.state.storage / "datasets" / "projects" / str(project_id) / str(identity)

    def public_catalog():
        result = []
        for key, filename in [
            ("online_retail", "source.xlsx"),
            ("online_retail_ii", "source.xlsx"),
            ("groceries", "groceries.csv"),
        ]:
            folder = app.state.public_data / key
            meta = folder / "dataset_manifest.json"
            if meta.is_file() and (folder / filename).is_file():
                manifest = json.loads(meta.read_text(encoding="utf-8"))
                result.append(
                    {
                        "id": key,
                        "title": manifest["source"]["title"],
                        "filename": filename,
                        "bytes": (folder / filename).stat().st_size,
                        "source_url": manifest["source"]["page"],
                        "license": manifest["source"]["license"],
                        "profile": manifest.get("profile"),
                    }
                )
        return result

    @router.get("/public-datasets")
    def public_datasets():
        return {"items": public_catalog()}

    @router.get("/projects/{project_id}/imports")
    def list_imports(project_id: UUID):
        with app.state.sessions() as session:
            require_project(session, project_id)
            rows = session.scalars(
                select(ImportDraft)
                .where(
                    ImportDraft.project_id == str(project_id),
                    ImportDraft.finalized_version_id.is_(None),
                )
                .order_by(ImportDraft.created_at.desc())
                .limit(10)
            ).all()
            return {"items": [draft_read(r) for r in rows]}

    async def finish_upload(
        session, project_id, identity, filename, suffix, folder, total, sha, source=None
    ):
        inspection = {"kind": "csv", "sheets": []}
        if suffix == ".xlsx":
            inspection = await run_job(folder, "inspect", source=str(folder / f"source{suffix}"))
        if source:
            manifest = json.loads(
                (app.state.public_data / source / "dataset_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            expected = (
                manifest.get("profile", {}).get("csv_sha256")
                if source == "groceries"
                else next(a["sha256"] for a in manifest["assets"] if a["file"] == "source.xlsx")
            )
            if expected != sha:
                raise DataIssue(
                    "公开数据内容与来源记录不一致，请联系维护者核验。", "source_changed", 409
                )
            inspection["source_manifest"] = manifest
        draft = ImportDraft(
            id=identity,
            project_id=str(project_id),
            filename=filename,
            suffix=suffix,
            bytes=total,
            sha256=sha,
            inspection=dump(inspection),
            source_dataset=source,
        )
        session.add(draft)
        session.commit()
        return draft_read(draft)

    @router.post("/projects/{project_id}/imports", status_code=201)
    async def upload(project_id: UUID, request: Request, filename: str = Query(max_length=300)):
        name, suffix = safe_filename(filename)
        length = request.headers.get("content-length", "0")
        if not length.isdigit() or int(length) > MAX_FILE_BYTES:
            raise DataIssue("文件超过 100 MiB，请缩小后重试。", "file_limit", 413)
        async with exclusive(app):
            with app.state.sessions() as session:
                require_project(session, project_id)
                identity = str(uuid4())
                folder = draft_dir(identity)
                folder.mkdir(parents=True)
                saved = False
                try:
                    total, sha = 0, hashlib.sha256()
                    with (folder / f"source{suffix}").open("xb") as out:
                        async for chunk in request.stream():
                            total += len(chunk)
                            if total > MAX_FILE_BYTES:
                                raise DataIssue(
                                    "文件超过 100 MiB，请缩小后重试。", "file_limit", 413
                                )
                            sha.update(chunk)
                            out.write(chunk)
                    if not total:
                        raise DataIssue("文件为空，请重新选择。")
                    result = await finish_upload(
                        session, project_id, identity, name, suffix, folder, total, sha.hexdigest()
                    )
                    saved = True
                    return result
                finally:
                    if not saved:
                        shutil.rmtree(folder)

    @router.post("/projects/{project_id}/imports/public/{dataset}", status_code=201)
    async def import_public(project_id: UUID, dataset: str):
        entry = next((p for p in public_catalog() if p["id"] == dataset), None)
        if entry is None:
            raise HTTPException(404, "这份公开数据暂不可用。")
        async with exclusive(app):
            with app.state.sessions() as session:
                require_project(session, project_id)
                identity = str(uuid4())
                folder = draft_dir(identity)
                folder.mkdir(parents=True)
                saved = False
                try:
                    suffix = Path(entry["filename"]).suffix
                    source = app.state.public_data / dataset / entry["filename"]
                    target = folder / f"source{suffix}"
                    await asyncio.to_thread(shutil.copyfile, source, target)
                    sha = await asyncio.to_thread(digest, target)
                    result = await finish_upload(
                        session,
                        project_id,
                        identity,
                        entry["title"] + suffix,
                        suffix,
                        folder,
                        target.stat().st_size,
                        sha,
                        dataset,
                    )
                    saved = True
                    return result
                finally:
                    if not saved:
                        shutil.rmtree(folder)

    @router.post("/projects/{project_id}/imports/{draft_id}/preview")
    async def preview(project_id: UUID, draft_id: UUID, options: ParseOptions):
        async with exclusive(app):
            with app.state.sessions() as session:
                draft = scoped(session, ImportDraft, draft_id, project_id)
                if draft.finalized_version_id:
                    raise DataIssue(
                        "这份文件已保存为版本，请上传新文件。", "already_finalized", 409
                    )
                folder = draft_dir(draft_id)
                token = str(uuid4())
                target = folder / f"raw-{token}.parquet"
                try:
                    result = await run_job(
                        folder,
                        "parse",
                        source=str(folder / f"source{draft.suffix}"),
                        output=str(target),
                        options=options.model_dump(),
                    )
                    old = draft.preview_token
                    draft.options, draft.preview, draft.preview_token = (
                        dump(options.model_dump()),
                        dump(result),
                        token,
                    )
                    draft.mapping_draft = None
                    session.commit()
                    if old:
                        (folder / f"raw-{old}.parquet").unlink(missing_ok=True)
                    return draft_read(draft)
                except BaseException:
                    target.unlink(missing_ok=True)
                    raise

    @router.put("/projects/{project_id}/imports/{draft_id}/mapping-draft")
    async def save_draft(project_id: UUID, draft_id: UUID, payload: SaveDraft):
        async with exclusive(app):
            with app.state.sessions() as session:
                draft = scoped(session, ImportDraft, draft_id, project_id)
                check_token(draft, payload.preview_token)
                if draft.finalized_version_id:
                    raise DataIssue("这份文件已保存为版本。", "already_finalized", 409)
                draft.mapping_draft = dump(payload.mapping.model_dump())
                session.commit()
                return draft_read(draft)

    @router.delete("/projects/{project_id}/imports/{draft_id}")
    async def discard(project_id: UUID, draft_id: UUID):
        async with exclusive(app):
            with app.state.sessions() as session:
                draft = scoped(session, ImportDraft, draft_id, project_id)
                if draft.finalized_version_id:
                    raise DataIssue("已保存版本不能作为草稿删除。", "already_finalized", 409)
                session.delete(draft)
                session.commit()
                folder = draft_dir(draft_id)
                if folder.exists():
                    shutil.rmtree(folder)
                return {"discarded": True}

    async def make_mapping(folder, raw, revision, mapping, validation):
        directory = folder / "mappings" / str(revision)
        directory.mkdir(parents=True)
        result = await run_job(
            directory,
            "canonical",
            source=str(raw),
            output=str(directory / "canonical.parquet"),
            mapping=mapping.model_dump(),
        )
        write_json(
            directory / "mapping.json",
            {
                "revision": revision,
                "config": mapping.model_dump(),
                "validation": validation,
                "canonical": result,
            },
        )

    @router.post("/projects/{project_id}/imports/{draft_id}/confirm", status_code=201)
    async def confirm(project_id: UUID, draft_id: UUID, payload: ConfirmImport):
        async with exclusive(app):
            with app.state.sessions() as session:
                draft = scoped(session, ImportDraft, draft_id, project_id)
                check_token(draft, payload.preview_token)
                if draft.finalized_version_id:
                    version = session.get(DatasetVersion, draft.finalized_version_id)
                    first = session.scalar(
                        select(MappingVersion).where(
                            MappingVersion.dataset_version_id == version.id,
                            MappingVersion.revision == 1,
                        )
                    )
                    if json.loads(first.config) != payload.mapping.model_dump():
                        raise DataIssue(
                            "文件已使用另一份字段设置保存，请在版本中另建映射。",
                            "already_finalized",
                            409,
                        )
                    return version_read(session, version)
                parsed, options = json.loads(draft.preview), json.loads(draft.options)
                validation = validate_mapping(payload.mapping, parsed, options)
                identity = str(uuid4())
                final = version_dir(project_id, identity)
                staging = final.with_name(".building-" + identity)
                staging.mkdir(parents=True)
                saved = False
                try:
                    origin = draft_dir(draft_id)
                    await asyncio.to_thread(
                        shutil.copyfile,
                        origin / f"source{draft.suffix}",
                        staging / f"source{draft.suffix}",
                    )
                    await asyncio.to_thread(
                        shutil.copyfile,
                        origin / f"raw-{draft.preview_token}.parquet",
                        staging / "raw.parquet",
                    )
                    await make_mapping(
                        staging, staging / "raw.parquet", 1, payload.mapping, validation
                    )
                    number = (
                        session.scalar(
                            select(func.max(DatasetVersion.number)).where(
                                DatasetVersion.project_id == str(project_id)
                            )
                        )
                        or 0
                    ) + 1
                    version = DatasetVersion(
                        id=identity,
                        project_id=str(project_id),
                        number=number,
                        filename=draft.filename,
                        suffix=draft.suffix,
                        sha256=draft.sha256,
                        bytes=draft.bytes,
                        row_count=parsed["row_count"],
                        options=draft.options,
                        preview=draft.preview,
                        source_dataset=draft.source_dataset,
                    )
                    write_json(
                        staging / "version.json",
                        {
                            "id": identity,
                            "number": number,
                            "source": f"source{draft.suffix}",
                            "raw": "raw.parquet",
                            "sha256": draft.sha256,
                            "options": options,
                            "preview": parsed,
                            "source_dataset": draft.source_dataset,
                            "source_manifest": json.loads(draft.inspection).get("source_manifest"),
                            "initial_mapping": "mappings/1/mapping.json",
                        },
                    )
                    staging.rename(final)
                    session.add(version)
                    session.flush()
                    session.add(
                        MappingVersion(
                            id=str(uuid4()),
                            dataset_version_id=identity,
                            revision=1,
                            config=dump(payload.mapping.model_dump()),
                            validation=dump(validation),
                        )
                    )
                    draft.finalized_version_id = identity
                    session.get(Project, str(project_id)).updated_at = timestamp()
                    session.commit()
                    saved = True
                    shutil.rmtree(origin)
                    return version_read(session, version)
                finally:
                    if staging.exists():
                        shutil.rmtree(staging)
                    if not saved and final.exists():
                        shutil.rmtree(final)

    @router.get("/projects/{project_id}/versions")
    def versions(project_id: UUID):
        with app.state.sessions() as session:
            require_project(session, project_id)
            rows = session.scalars(
                select(DatasetVersion)
                .where(DatasetVersion.project_id == str(project_id))
                .order_by(DatasetVersion.number.desc())
            ).all()
            return {"items": [version_read(session, r, full=False) for r in rows]}

    @router.get("/projects/{project_id}/versions/{version_id}")
    def version_detail(project_id: UUID, version_id: UUID):
        with app.state.sessions() as session:
            return version_read(session, scoped(session, DatasetVersion, version_id, project_id))

    @router.get("/projects/{project_id}/versions/{version_id}/mappings")
    def mappings(project_id: UUID, version_id: UUID):
        with app.state.sessions() as session:
            scoped(session, DatasetVersion, version_id, project_id)
            rows = session.scalars(
                select(MappingVersion)
                .where(MappingVersion.dataset_version_id == str(version_id))
                .order_by(MappingVersion.revision.desc())
            ).all()
            return {"items": [mapping_read(r) for r in rows]}

    @router.post("/projects/{project_id}/versions/{version_id}/mappings", status_code=201)
    async def revise(project_id: UUID, version_id: UUID, payload: ReviseMapping):
        async with exclusive(app):
            with app.state.sessions() as session:
                version = scoped(session, DatasetVersion, version_id, project_id)
                current = latest_mapping(session, version.id)
                if current.revision != payload.expected_revision:
                    raise DataIssue("字段版本已更新，请刷新后再保存。", "revision_conflict", 409)
                validation = validate_mapping(
                    payload.mapping, json.loads(version.preview), json.loads(version.options)
                )
                revision = current.revision + 1
                folder = version_dir(project_id, version_id)
                # Only create this revision; previous artifacts remain unchanged.
                target = folder / "mappings" / str(revision)
                if target.exists():
                    raise DataIssue(
                        "该字段版本有未完成的记录，请联系维护者核验。", "artifact_conflict", 409
                    )
                saved = False
                try:
                    await make_mapping(
                        folder, folder / "raw.parquet", revision, payload.mapping, validation
                    )
                    row = MappingVersion(
                        id=str(uuid4()),
                        dataset_version_id=version.id,
                        revision=revision,
                        config=dump(payload.mapping.model_dump()),
                        validation=dump(validation),
                    )
                    session.add(row)
                    session.commit()
                    saved = True
                    return mapping_read(row)
                finally:
                    if not saved and target.exists():
                        shutil.rmtree(target)

    app.include_router(router)
