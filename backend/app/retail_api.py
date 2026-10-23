import asyncio
import hashlib
import json
import logging
import os
from datetime import date
from decimal import ROUND_CEILING, Decimal
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import defer

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
from .sales_views import encode, ensure_views, product_bytes
from .sales_recommendations import recommendations


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


def report_row(session, run_id, project_id, storage=None):
    run = scoped(session, AnalysisRun, run_id, project_id)
    if run.kind != "sales" or run.status not in PUBLISHED or not run.result:
        raise DataIssue("月报尚未完成。", "report_not_ready", 409)
    from .sales_signals import signal_view
    from .sales_focus import focus_view
    output = storage / "runs" / str(project_id) / str(run_id) if storage is not None else None
    return run, focus_view(signal_view(json.loads(run.result)), output)


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

    @router.get("/reports")
    def reports(project_id: UUID):
        from .report_navigation import report_catalog
        with app.state.sessions() as session:
            return report_catalog(session, project_id)

    @router.get("/runs/{run_id}/pairings")
    def pairings(project_id: UUID, run_id: UUID, version_id: UUID, preferred: UUID | None = None):
        from .report_navigation import month_pairings
        with app.state.sessions() as session:
            run = workspace_row(session, project_id, run_id)
            if run.status not in PUBLISHED:
                raise DataIssue("月报尚未完成。", "report_not_ready", 409)
            return month_pairings(session, run, str(version_id), str(preferred) if preferred else None)

    @router.get("/runs/{run_id}/automatic")
    def automatic_status(project_id: UUID, run_id: UUID):
        from .sales_automation import read_state
        with app.state.sessions() as session:
            return read_state(session, workspace_row(session, project_id, run_id))

    @router.post("/runs/{run_id}/automatic")
    def automatic_start(project_id: UUID, run_id: UUID, retry: bool = False):
        from .sales_automation import enroll, read_state
        with app.state.sessions() as session:
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            run = workspace_row(session, project_id, run_id)
            if run.status not in PUBLISHED:
                raise DataIssue("月报生成后会自动开始。", "report_not_ready", 409)
            enroll(session, run, retry)
            session.commit()
            return read_state(session, run)

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
        from .sales_automation import initial_state
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
                            "auto_analysis": initial_state(),
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

    def workspace_row(session, project_id, run_id):
        run = session.scalar(
            select(AnalysisRun)
            .options(defer(AnalysisRun.result))
            .where(AnalysisRun.id == str(run_id), AnalysisRun.project_id == str(project_id))
        )
        if not run or run.kind != "sales":
            raise HTTPException(404, "没有找到这份月报。")
        return run

    def view_directory(session, run):
        if run.status not in PUBLISHED:
            raise DataIssue("月报尚未完成。", "report_not_ready", 409)
        output = app.state.storage / "runs" / run.project_id / run.id
        return ensure_views(output, run.id, lambda: json.loads(run.result))

    @router.get("/runs/{run_id}/workspace")
    def workspace(project_id: UUID, run_id: UUID, view: Literal["overview", "products"] = "overview"):
        with app.state.sessions() as session:
            run = workspace_row(session, project_id, run_id)
            metadata = run_read(run)
            metadata["parameters"] = json.loads(run.parameters)
            if run.status not in PUBLISHED:
                return {**metadata, "result": None}
            directory = view_directory(session, run)
            # These bytes were serialized at report publication, avoiding a second
            # decode and FastAPI's recursive encoding of thousands of products.
            base = (directory / (view + ".json")).read_bytes()
            result = base[:-1] + b',' + encode(recommendations(session, run, directory))[1:]
            body = encode(metadata)[:-1] + b',"result":' + result + b'}'
            return Response(body, media_type="application/json")

    @router.get("/runs/{run_id}/product")
    def product_detail(project_id: UUID, run_id: UUID, item_id: str):
        with app.state.sessions() as session:
            run = workspace_row(session, project_id, run_id)
            directory = view_directory(session, run)
            try:
                body = product_bytes(directory, item_id)
            except KeyError:
                raise HTTPException(404, "没有找到这件商品。") from None
            return Response(body, media_type="application/json")

    @router.get("/runs/{run_id}/records")
    def records(project_id: UUID, run_id: UUID):
        with app.state.sessions() as session:
            run = workspace_row(session, project_id, run_id)
            if run.status not in PUBLISHED:
                raise DataIssue("月报尚未完成。", "report_not_ready", 409)
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
                run, report = report_row(session, run_id, project_id, app.state.storage)
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

    @router.get("/runs/{run_id}/action-customers")
    def action_customers(project_id: UUID, run_id: UUID, action_id: str):
        import csv
        import io

        with app.state.sessions() as session:
            run = workspace_row(session, project_id, run_id)
            directory = view_directory(session, run)
            choices = recommendations(session, run, directory)
            action = next((a for a in choices['actions'] if a['id'] == action_id
                           and a.get('target', {}).get('kind') == 'customer'), None)
            if action is None:
                raise HTTPException(404, '没有这条客户建议。')
            target = action['target']
            cluster_run = scoped(session, AnalysisRun, target['run_id'], project_id)
            if cluster_run.kind != 'clustering' or cluster_run.status not in PUBLISHED:
                raise HTTPException(404, '这份客户分组不可用。')
        if target.get('opportunity'):
            from .customer_opportunities import VERSION, FIELDS, load
            folder = app.state.storage / 'runs' / str(project_id) / cluster_run.id
            evidence = load(folder)
            if target['opportunity'] != VERSION or not evidence or not evidence.get('opportunities'):
                raise HTTPException(404, '没有这份回访名单。')
            output = io.StringIO(newline='')
            writer = csv.writer(output)
            writer.writerow(['客户编号', '购买日期数', '平时购买间隔（天）', '上次购买日期', '本次间隔（天）', '超过此天数才入选'])
            with (folder/'customer_followup.csv').open(encoding='utf-8', newline='') as stream:
                for row in csv.DictReader(stream):
                    values = [row.get(k) or '' for k in FIELDS]
                    writer.writerow(["'" + v if v.lstrip().startswith(('=', '+', '-', '@')) else v for v in values])
            return Response(('\ufeff' + output.getvalue()).encode('utf-8'), media_type='text/csv',
                            headers={'Content-Disposition': 'attachment; filename="customer-followup.csv"'})
        path = app.state.storage / 'runs' / str(project_id) / cluster_run.id / 'cluster_assignments.csv'
        if not path.is_file():
            raise HTTPException(404, '没有找到客户分组表。')
        output = io.StringIO(newline='')
        writer = csv.writer(output)
        writer.writerow(['客户编号', '距上次购买天数', '购买次数', '历史购买金额'])
        with path.open(encoding='utf-8-sig', newline='') as stream:
            for row in csv.DictReader(stream):
                if row.get('cluster') != str(target['cluster']):
                    continue
                values = [row.get(k) or '' for k in ['customer_id', 'recency_days', 'frequency', 'monetary']]
                writer.writerow(["'" + v if v.lstrip().startswith(('=', '+', '-', '@')) else v for v in values])
        return Response(('\ufeff' + output.getvalue()).encode('utf-8'), media_type='text/csv',
                        headers={'Content-Disposition': 'attachment; filename="selected-customers.csv"'})

    @router.put("/runs/{run_id}/actions/{action_id:path}")
    def action(project_id: UUID, run_id: UUID, action_id: str, payload: ActionInput):
        with app.state.sessions() as session:
            run = workspace_row(session, project_id, run_id)
            directory = view_directory(session, run)
            choices = recommendations(session, run, directory)
            available = choices['actions'] + choices['previous_actions']
            if action_id not in {a["id"] for a in available}:
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
            _, report = report_row(session, run_id, project_id, app.state.storage)
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
            _, report = report_row(session, run_id, project_id, app.state.storage)
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
            need = max(Decimal("0"), Decimal(str(prediction["quantity"]))
                       + Decimal(str(payload.reserve)) - Decimal(str(payload.available))
                       - Decimal(str(payload.incoming)))
            pack = Decimal(str(payload.pack_size))
            value = {
                "input": payload.model_dump(mode="json"),
                "forecast": prediction,
                "suggested_quantity": float(
                    (need / pack).to_integral_value(rounding=ROUND_CEILING) * pack
                ),
                "notice": "仅为七天总量参考；晚到货可能导致期间缺货，未考虑保质期和采购预算。",
            }
        with app.state.sessions() as session:
            return save_record(session, run_id, "inventory:" + payload.item_id, value)

    @router.get("/runs/{run_id}/report")
    def export_report(project_id: UUID, run_id: UUID, all_attention: bool = False):
        with app.state.sessions() as session:
            run, report = report_row(session, run_id, project_id, app.state.storage)
            report = {**report, **recommendations(session, run, view_directory(session, run))}
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
            _, report = report_row(session, run_id, project_id, app.state.storage)
        if artifact == "sales_report.json":
            return Response(encode(report), media_type="application/json",
                            headers={"Content-Disposition": 'attachment; filename="sales_report.json"'})
        if artifact == "sales_products.csv":
            import csv, io
            stream = io.StringIO()
            path = app.state.storage / "runs" / str(project_id) / str(run_id) / artifact
            products = {p["id"]: p for p in report["products"]}
            with path.open(encoding="utf-8-sig", newline="") as source:
                reader = csv.DictReader(source)
                writer = csv.DictWriter(stream, fieldnames=reader.fieldnames)
                writer.writeheader()
                for row in reader:
                    key = row["id"]
                    p = products.get(key) or (products.get(key[1:]) if key.startswith("'") else None)
                    if p:
                        row.update(change=p["change"], reason=p["reason"], attention=bool(p["flags"]))
                    writer.writerow(row)
            return Response(stream.getvalue().encode("utf-8-sig"), media_type="text/csv",
                            headers={"Content-Disposition": 'attachment; filename="sales_products.csv"'})
        path = app.state.storage / "runs" / str(project_id) / str(run_id) / artifact
        return FileResponse(path, filename=artifact)

    @router.post("/runs/{run_id}/ask")
    async def ask(project_id: UUID, run_id: UUID, payload: QuestionInput):
        from .sales_assistant import compose, infer_answer, prepare_answer

        def prepare():
            with app.state.sessions() as session:
                run, report = report_row(session, run_id, project_id, app.state.storage)
                if payload.item_id and payload.item_id not in {p["id"] for p in report["products"]}:
                    raise DataIssue("请选择本次月报中的商品。", "unknown_evidence")
                saved = session.scalars(select(SalesRecord).where(SalesRecord.run_id == str(run_id))).all()
                records = {r.entry_key: {"value": json.loads(r.value), "revision": r.revision,
                                        "updated_at": r.updated_at} for r in saved}
                # Use the same screened recommendations as the visible month report.
                report = {**report, **recommendations(session, run, view_directory(session, run))}
                return prepare_answer(report, payload.question, payload.item_id, records)

        prepared = await asyncio.to_thread(prepare)
        fallback = {**compose(prepared), "run_id": str(run_id)}
        if prepared['direct'] or all(len(f['variants']) == 1 for f in prepared['facts']):
            return {**fallback, "response_source": "computed"}
        if ai_lock.locked() or app.state.import_lock.locked():
            return {**fallback, "response_source": "model_busy"}
        async with ai_lock:
            try:
                value = await asyncio.to_thread(infer_answer, prepared, payload.question,
                    os.environ.get("AIC_AI_URL", "http://127.0.0.1:8081/v1/chat/completions"))
                return {**value, "run_id": str(run_id), "response_source": "model",
                        "model": "qwen2.5-1.5b-instruct-q4_k_m"}
            except (OSError, ValueError, KeyError, TypeError) as exc:
                logging.getLogger(__name__).warning("Sales answer unavailable or rejected: %s", type(exc).__name__)
                return {**fallback, "response_source": "model_unavailable"}

    app.include_router(router)
