import asyncio
import hashlib
import json
import logging
import math
import os
from datetime import date
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy import func, select

from .data_api import digest, dump, scoped
from .import_formats import DataIssue
from .models import (
    AnalysisRun,
    CleaningPolicy,
    DatasetVersion,
    MappingVersion,
    Project,
    RunEvent,
    SalesRecord,
    timestamp,
)
from .quality_api import run_read
from .quality_schemas import CleaningConfig
from .retail_export import render_report
from .retail_schemas import ActionInput, InventoryInput, ItemNoteInput, QuestionInput, RetailInput
from .task_runner import PUBLISHED


def resolve_sources(session, storage, project_id, entries):
    result, hashes = [], set()
    for entry in entries:
        version = scoped(session, DatasetVersion, entry["version_id"], project_id)
        mapping = session.scalar(
            select(MappingVersion).where(
                MappingVersion.dataset_version_id == version.id,
                MappingVersion.revision == entry["mapping_revision"],
            )
        )
        if not mapping:
            raise DataIssue("字段版本不存在，请刷新后再试。", "mapping_missing")
        config = json.loads(mapping.config)
        if not config["columns"].get("item_id") or not config["columns"].get("quantity"):
            raise DataIssue("销售月报需要商品标识和销量，请先调整字段。", "sales_fields_missing")
        if config.get("record_kind") != "monthly_summary" and not config["columns"].get(
            "event_time"
        ):
            raise DataIssue("请对应日期，或明确选择月度汇总并填写月份。", "sales_date_missing")
        if version.sha256 in hashes:
            raise DataIssue("选中了内容相同的文件，请保留一个版本。", "duplicate_source")
        hashes.add(version.sha256)
        path = (
            storage
            / "datasets"
            / "projects"
            / str(project_id)
            / version.id
            / "mappings"
            / str(mapping.revision)
            / "canonical.parquet"
        )
        if not path.is_file():
            raise DataIssue("数据文件不可用，请联系维护者。", "source_missing")
        result.append(
            {
                "version_id": version.id,
                "mapping_revision": mapping.revision,
                "mapping_id": mapping.id,
                "mapping": config,
                "path": str(path),
                "canonical_sha256": digest(path),
                "filename": version.filename,
                "number": version.number,
                "source_sha256": version.sha256,
            }
        )
    return result


def report_row(session, run_id, project_id):
    run = scoped(session, AnalysisRun, run_id, project_id)
    if run.kind != "sales" or run.status not in PUBLISHED or not run.result:
        raise DataIssue("月报尚未完成。", "report_not_ready", 409)
    return run, json.loads(run.result)


def save_record(session, run_id, key, value, expected=None):
    session.connection().exec_driver_sql("BEGIN IMMEDIATE")
    row = session.scalar(
        select(SalesRecord).where(SalesRecord.run_id == str(run_id), SalesRecord.entry_key == key)
    )
    if expected is not None and expected != (row.revision if row else 0):
        raise DataIssue("这条记录已更新，请刷新后再修改。", "revision_conflict", 409)
    if not row:
        row = SalesRecord(run_id=str(run_id), entry_key=key, value=dump(value), revision=1)
        session.add(row)
    else:
        row.value, row.revision, row.updated_at = dump(value), row.revision + 1, timestamp()
    session.commit()
    return {"value": value, "revision": row.revision, "updated_at": row.updated_at}


def install_retail_routes(app):
    router = APIRouter(prefix="/api/projects/{project_id}/sales")
    ai_lock = asyncio.Lock()

    @router.get("/sources/{version_id}")
    async def source_info(project_id: UUID, version_id: UUID):
        def inspect():
            import calendar
            from datetime import datetime, timedelta
            from zoneinfo import ZoneInfo

            import pyarrow.parquet as pq

            from .quality import parse_time

            with app.state.sessions() as session:
                version = scoped(session, DatasetVersion, version_id, project_id)
                mapping = session.scalar(
                    select(MappingVersion)
                    .where(MappingVersion.dataset_version_id == version.id)
                    .order_by(MappingVersion.revision.desc())
                )
                config = json.loads(mapping.config)
                path = (
                    app.state.storage
                    / "datasets"
                    / "projects"
                    / str(project_id)
                    / version.id
                    / "mappings"
                    / str(mapping.revision)
                    / "canonical.parquet"
                )
                revision = mapping.revision
            days = set()
            if config.get("record_kind") == "monthly_summary" and config.get("summary_month"):
                days.add(config["summary_month"] + "-01")
            elif config["columns"].get("event_time"):
                for batch in pq.ParquetFile(path).iter_batches(
                    batch_size=2000, columns=["event_time"]
                ):
                    for value in batch.column(0).to_pylist():
                        parsed = parse_time(value, config)
                        if parsed:
                            days.add(
                                datetime.fromisoformat(parsed)
                                .astimezone(ZoneInfo(config["timezone"]))
                                .date()
                                .isoformat()
                            )
            first, last = (min(days), max(days)) if days else (None, None)
            if last and config.get("record_kind") == "monthly_summary":
                end = date.fromisoformat(last)
                last = end.replace(day=calendar.monthrange(end.year, end.month)[1]).isoformat()
            suggested = last[:7] if last else config.get("summary_month")
            if last and config.get("record_kind", "transactions") != "monthly_summary":
                end = date.fromisoformat(last)
                if end.day != calendar.monthrange(end.year, end.month)[1] and first[:7] != last[:7]:
                    suggested = (end.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
            return {
                "version_id": str(version_id),
                "mapping_revision": revision,
                "start": first,
                "end": last,
                "months": sorted({d[:7] for d in days}),
                "suggested_month": suggested,
                "mapping": config,
            }

        return await asyncio.to_thread(inspect)

    @router.post("/runs", status_code=202)
    async def create_report(project_id: UUID, payload: RetailInput):
        params = payload.model_dump(mode="json", exclude={"idempotency_key"})
        request_hash = hashlib.sha256(dump(params).encode()).hexdigest()

        def submit():
            with app.state.sessions() as session:
                session.connection().exec_driver_sql("BEGIN IMMEDIATE")
                old = session.scalar(
                    select(AnalysisRun).where(
                        AnalysisRun.project_id == str(project_id),
                        AnalysisRun.idempotency_key == payload.idempotency_key,
                    )
                )
                if old:
                    if old.request_sha256 != request_hash:
                        raise DataIssue(
                            "重复提交的设置不同，请重新提交。", "idempotency_conflict", 409
                        )
                    return run_read(old, True)
                sources = resolve_sources(session, app.state.storage, project_id, params["sources"])
                params["source_hashes"] = {s["version_id"]: s["canonical_sha256"] for s in sources}
                primary = sources[-1]
                policy_config = dump(CleaningConfig(duplicates=payload.duplicates).model_dump())
                policy_sha = hashlib.sha256(policy_config.encode()).hexdigest()
                policy = session.scalar(
                    select(CleaningPolicy).where(
                        CleaningPolicy.mapping_version_id == primary["mapping_id"],
                        CleaningPolicy.config_sha256 == policy_sha,
                    )
                )
                if not policy:
                    number = (
                        session.scalar(
                            select(func.max(CleaningPolicy.number)).where(
                                CleaningPolicy.dataset_version_id == primary["version_id"]
                            )
                        )
                        or 0
                    ) + 1
                    policy = CleaningPolicy(
                        id=str(uuid4()),
                        dataset_version_id=primary["version_id"],
                        mapping_version_id=primary["mapping_id"],
                        number=number,
                        config=policy_config,
                        config_sha256=policy_sha,
                    )
                    session.add(policy)
                    session.flush()
                run = AnalysisRun(
                    id=str(uuid4()),
                    project_id=str(project_id),
                    dataset_version_id=primary["version_id"],
                    mapping_version_id=primary["mapping_id"],
                    policy_id=policy.id,
                    kind="sales",
                    idempotency_key=payload.idempotency_key,
                    request_sha256=request_hash,
                    parameters=dump(
                        {
                            "sales": params,
                            "timeout_seconds": payload.budget_seconds,
                            "memory_mb": 8192,
                        }
                    ),
                )
                session.add(run)
                session.flush()
                session.add(RunEvent(run_id=run.id, status="queued", message="月报已加入队列。"))
                session.commit()
                return run_read(run, True)

        return await asyncio.to_thread(submit)

    @router.get("/runs/{run_id}/records")
    def records(project_id: UUID, run_id: UUID):
        with app.state.sessions() as session:
            report_row(session, run_id, project_id)
            rows = session.scalars(
                select(SalesRecord).where(SalesRecord.run_id == str(run_id))
            ).all()
            return {
                "items": {
                    r.entry_key: {
                        "value": json.loads(r.value),
                        "revision": r.revision,
                        "updated_at": r.updated_at,
                    }
                    for r in rows
                }
            }

    @router.get("/runs/{run_id}/item-records")
    async def item_records(project_id: UUID, run_id: UUID, item_id: str, day: date):
        def read():
            import csv

            import pyarrow.parquet as pq

            with app.state.sessions() as session:
                run, report = report_row(session, run_id, project_id)
                if not any(p["id"] == item_id for p in report["products"]):
                    raise DataIssue("这款商品不在本次月报中。", "unknown_evidence")
                if day.strftime("%Y-%m") != report["month"]:
                    raise DataIssue("请选择本次月报中的日期。", "outside_scope")
                sources = resolve_sources(
                    session,
                    app.state.storage,
                    project_id,
                    json.loads(run.parameters)["sales"]["sources"],
                )
            path = (
                app.state.storage / "runs" / str(project_id) / str(run_id) / "sales_row_audit.csv"
            )
            wanted, count = {}, 0
            with path.open(encoding="utf-8-sig", newline="") as stream:
                for row in csv.DictReader(stream):
                    if row["item_id"] == item_id and row["date"] == day.isoformat():
                        count += 1
                        if count <= 100:
                            wanted[row["version_id"], row["source_row_id"]] = row["reason"]
            result = []
            for source in sources:
                expected = next(
                    s["canonical_sha256"]
                    for s in report["sources"]
                    if s["version_id"] == source["version_id"]
                )
                if source["canonical_sha256"] != expected:
                    raise DataIssue("来源哈希与本次报告不一致。", "artifact_mismatch")
                for batch in pq.ParquetFile(source["path"]).iter_batches(batch_size=2000):
                    for raw in batch.to_pylist():
                        key = source["version_id"], str(raw["source_row_id"])
                        if key in wanted:
                            result.append(
                                {
                                    "source_row_id": raw["source_row_id"],
                                    "filename": source["filename"],
                                    "version_id": source["version_id"],
                                    "quantity": raw.get("quantity"),
                                    "line_amount": raw.get("line_amount"),
                                    "unit_price": raw.get("unit_price"),
                                    "event_time": raw.get("event_time"),
                                    "reason": wanted[key],
                                }
                            )
            return {
                "run_id": str(run_id),
                "item_id": item_id,
                "date": day.isoformat(),
                "count": count,
                "shown": len(result),
                "items": result,
            }

        return await asyncio.to_thread(read)

    @router.put("/runs/{run_id}/actions/{action_id:path}")
    def action(project_id: UUID, run_id: UUID, action_id: str, payload: ActionInput):
        with app.state.sessions() as session:
            _, report = report_row(session, run_id, project_id)
            if action_id not in {a["id"] for a in report["actions"]}:
                raise HTTPException(404, "没有这条行动建议。")
        with app.state.sessions() as session:
            return save_record(
                session,
                run_id,
                "action:" + action_id,
                payload.model_dump(exclude={"expected_revision"}),
                payload.expected_revision,
            )

    @router.put("/runs/{run_id}/item-notes")
    def item_note(project_id: UUID, run_id: UUID, payload: ItemNoteInput):
        with app.state.sessions() as session:
            _, report = report_row(session, run_id, project_id)
            if payload.item_id not in {p["id"] for p in report["products"]}:
                raise DataIssue("商品不在这份月报中。", "item_missing", 404)
            if payload.day and payload.day.strftime("%Y-%m") != report["month"]:
                raise DataIssue("记录日期必须属于本次月报月份。", "note_date")
            value = payload.model_dump(mode="json", exclude={"expected_revision"})
            value["source"] = "user_note"
            key = "note:" + dump([payload.item_id, value["day"]])
            return save_record(session, run_id, key, value, payload.expected_revision)

    @router.post("/runs/{run_id}/inventory")
    def inventory(project_id: UUID, run_id: UUID, payload: InventoryInput):
        with app.state.sessions() as session:
            _, report = report_row(session, run_id, project_id)
            product = next((p for p in report["products"] if p["id"] == payload.item_id), None)
            if not product or not product["forecast"]:
                raise DataIssue(
                    "这款商品没有可发布的预测，暂不能计算备货量。", "forecast_unavailable"
                )
            kind = product.get("item_type", {}).get("kind", "unknown")
            if kind in {"fee_service", "accounting"}:
                raise DataIssue("费用、服务或记账项目不适用实物备货计算。", "not_stockable")
            if kind == "unknown" and not payload.physical_confirmed:
                raise DataIssue("请确认这是一款可备货的实物商品。", "item_type_unconfirmed")
            prediction = product["forecast"]
            origin = date.fromisoformat(prediction["start"])
            if payload.snapshot_date != origin or not payload.confirmed:
                raise DataIssue(
                    "库存日期需与预测起点相同，并确认库存和已下单数量。", "inventory_date"
                )
            if payload.incoming and (
                not payload.arrival_date
                or not origin <= payload.arrival_date <= date.fromisoformat(prediction["end"])
            ):
                raise DataIssue("仅能扣除预测这七天内确定到货的数量。", "inventory_arrival")
            need = max(
                0, prediction["quantity"] + payload.reserve - payload.available - payload.incoming
            )
            value = {
                "input": payload.model_dump(mode="json"),
                "forecast": prediction,
                "suggested_quantity": math.ceil(need / payload.pack_size) * payload.pack_size,
                "notice": "仅为七天总量参考；晚到货可能导致期间缺货，未考虑保质期和采购预算。",
            }
        with app.state.sessions() as session:
            return save_record(session, run_id, "inventory:" + payload.item_id, value)

    @router.get("/runs/{run_id}/report")
    def export_report(project_id: UUID, run_id: UUID, all_attention: bool = False):
        with app.state.sessions() as session:
            _, report = report_row(session, run_id, project_id)
            project = session.get(Project, str(project_id))
            return HTMLResponse(
                render_report(report, project.name, all_attention),
                headers={
                    "Content-Disposition": f'attachment; filename="sales-{report["month"]}.html"'
                },
            )

    @router.get("/runs/{run_id}/files/{artifact}")
    def artifact(project_id: UUID, run_id: UUID, artifact: str):
        allowed = {
            "sales_products.csv",
            "sales_row_audit.csv",
            "sales_backtests.csv",
            "sales_report.json",
            "manifest.json",
        }
        if artifact not in allowed:
            raise HTTPException(404, "没有这份文件。")
        with app.state.sessions() as session:
            report_row(session, run_id, project_id)
        path = app.state.storage / "runs" / str(project_id) / str(run_id) / artifact
        return FileResponse(path, filename=artifact)

    @router.post("/runs/{run_id}/ask")
    async def ask(project_id: UUID, run_id: UUID, payload: QuestionInput):
        from .sales_assistant import compose, infer_order, prepare_answer

        with app.state.sessions() as session:
            _, report = report_row(session, run_id, project_id)
            if payload.item_id and payload.item_id not in {p["id"] for p in report["products"]}:
                raise DataIssue("请选择本次月报中的商品。", "unknown_evidence")
            saved = session.scalars(
                select(SalesRecord).where(SalesRecord.run_id == str(run_id))
            ).all()
            records = {
                r.entry_key: {
                    "value": json.loads(r.value),
                    "revision": r.revision,
                    "updated_at": r.updated_at,
                }
                for r in saved
            }
            pairing = None
            sources = {s["version_id"]: s["mapping_revision"] for s in report["sources"]}
            runs = session.scalars(
                select(AnalysisRun)
                .where(
                    AnalysisRun.project_id == str(project_id),
                    AnalysisRun.kind == "association",
                    AnalysisRun.status.in_(PUBLISHED),
                )
                .order_by(AnalysisRun.created_at.desc())
                .limit(30)
            ).all()
            for candidate in runs:
                if candidate.result:
                    value = json.loads(candidate.result)
                    context = value.get("context", {})
                    source_id = context.get("data_version_id")
                    if source_id in sources and sources[source_id] == context.get(
                        "mapping_revision"
                    ):
                        pairing = value
                        break
        prepared = prepare_answer(report, payload.question, payload.item_id, records, pairing)
        fallback = {**compose(prepared), "run_id": str(run_id)}
        if ai_lock.locked() or app.state.import_lock.locked():
            return fallback
        async with ai_lock:
            try:
                value = await asyncio.to_thread(
                    infer_order,
                    prepared,
                    payload.question,
                    os.environ.get("AIC_AI_URL", "http://127.0.0.1:8081/v1/chat/completions"),
                )
                return {**value, "run_id": str(run_id), "model": "qwen2.5-1.5b-instruct-q4_k_m"}
            except (OSError, ValueError, KeyError, TypeError) as exc:
                logging.getLogger(__name__).warning("Sales answer composition rejected: %s", exc)
                return fallback

    app.include_router(router)
