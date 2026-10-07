import asyncio
import hashlib
import json
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from .data_api import dump, require_project, scoped
from .import_formats import DataIssue
from .models import AnalysisRun, CleaningPolicy, DatasetVersion, MappingVersion, RunEvent, timestamp
from .quality_schemas import AnalysisParameters, PolicyInput, QualityRunInput
from .task_registry import TASK_SPECS
from .task_runner import PUBLISHED, TERMINAL, event


def policy_read(row, mapping):
    return {
        "id": row.id,
        "number": row.number,
        "mapping_revision": mapping.revision,
        "config": json.loads(row.config),
        "created_at": row.created_at,
    }


def run_read(row, full=False):
    result = {
        key: getattr(row, key)
        for key in [
            "id",
            "project_id",
            "dataset_version_id",
            "policy_id",
            "kind",
            "status",
            "phase",
            "progress",
            "message",
            "created_at",
            "started_at",
            "finished_at",
            "error_code",
            "peak_rss_bytes",
        ]
    }
    if full:
        result["parameters"] = json.loads(row.parameters)
        result["result"] = (
            json.loads(row.result) if row.result and row.status in PUBLISHED else None
        )
    return result


def require_capability(report, parameters: AnalysisParameters):
    decision = report["capabilities"][parameters.kind]
    if not decision["allowed"]:
        raise DataIssue(
            "当前数据暂不支持这项分析：" + " ".join(decision["reasons"]),
            "capability_unavailable",
            409,
        )
    if parameters.kind in {"rf", "rfm"}:
        customers = report["summary"][parameters.kind + "_customers"]
        if parameters.k_max > customers:
            raise DataIssue("分群数不能超过有效客户数。", "invalid_parameters")
    return {
        "allowed": True,
        "kind": parameters.kind,
        "input_view": {
            "rf": "rf_orders.parquet",
            "rfm": "rfm_orders.parquet",
            "association": "basket_items.parquet",
        }[parameters.kind],
        "quality_context": report["context"],
        "parameters": parameters.model_dump(),
        "notice": "仅校验分析输入与参数，不执行分析。",
    }


def install_quality_routes(app):
    router = APIRouter(prefix="/api/projects/{project_id}")

    @router.post("/versions/{version_id}/policies", status_code=201)
    def create_policy(project_id: UUID, version_id: UUID, payload: PolicyInput):
        config = dump(payload.config.model_dump())
        sha = hashlib.sha256(config.encode()).hexdigest()
        with app.state.sessions() as session:
            # Serialize policy numbering without a long data-processing transaction.
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            scoped(session, DatasetVersion, version_id, project_id)
            mapping = session.scalar(
                select(MappingVersion).where(
                    MappingVersion.dataset_version_id == str(version_id),
                    MappingVersion.revision == payload.mapping_revision,
                )
            )
            if not mapping:
                raise HTTPException(404, "没有找到这份字段版本。")
            existing = session.scalar(
                select(CleaningPolicy).where(
                    CleaningPolicy.mapping_version_id == mapping.id,
                    CleaningPolicy.config_sha256 == sha,
                )
            )
            if existing:
                return policy_read(existing, mapping)
            number = (
                session.scalar(
                    select(func.max(CleaningPolicy.number)).where(
                        CleaningPolicy.dataset_version_id == str(version_id)
                    )
                )
                or 0
            ) + 1
            row = CleaningPolicy(
                id=str(uuid4()),
                dataset_version_id=str(version_id),
                mapping_version_id=mapping.id,
                number=number,
                config=config,
                config_sha256=sha,
            )
            session.add(row)
            session.commit()
            return policy_read(row, mapping)

    @router.get("/versions/{version_id}/policies")
    def policies(project_id: UUID, version_id: UUID):
        with app.state.sessions() as session:
            scoped(session, DatasetVersion, version_id, project_id)
            rows = session.scalars(
                select(CleaningPolicy)
                .where(CleaningPolicy.dataset_version_id == str(version_id))
                .order_by(CleaningPolicy.number.desc())
            ).all()
            return {
                "items": [
                    policy_read(row, session.get(MappingVersion, row.mapping_version_id))
                    for row in rows
                ]
            }

    @router.post("/runs", status_code=202)
    def submit(project_id: UUID, payload: QualityRunInput):
        parameters = payload.model_dump(mode="json", exclude={"idempotency_key"})
        sha = hashlib.sha256(json.dumps(parameters, sort_keys=True).encode()).hexdigest()
        with app.state.sessions() as session:
            version = scoped(session, DatasetVersion, payload.dataset_version_id, project_id)
            policy = session.get(CleaningPolicy, str(payload.policy_id))
            if not policy or policy.dataset_version_id != version.id:
                raise HTTPException(404, "清洗策略不属于这份数据版本。")
            mapping = session.get(MappingVersion, policy.mapping_version_id)
            config = json.loads(mapping.config)
            scope = parameters["scope"]
            checks = [
                (scope.get("date_start") or scope.get("date_end"), "event_time", "交易时间"),
                (scope.get("countries"), "country", "国家 / 地区"),
                (scope.get("item_ids"), "item_id", "商品标识"),
            ]
            for active, key, title in checks:
                if active and not config["columns"].get(key):
                    raise DataIssue(f"未对应{title}，无法使用这个筛选条件。", "scope_unavailable")
            if scope.get("currency") and not (
                config["columns"].get("currency") or config.get("currency_constant")
            ):
                raise DataIssue("数据没有明确币种，不能通过筛选补造币种。", "scope_unavailable")
            existing = session.scalar(
                select(AnalysisRun).where(
                    AnalysisRun.project_id == str(project_id),
                    AnalysisRun.idempotency_key == payload.idempotency_key,
                )
            )
            if existing:
                if existing.request_sha256 != sha:
                    raise DataIssue(
                        "同一提交标识对应了不同设置，请重新提交。", "idempotency_conflict", 409
                    )
                return run_read(existing, True)
            row = AnalysisRun(
                id=str(uuid4()),
                project_id=str(project_id),
                dataset_version_id=version.id,
                mapping_version_id=mapping.id,
                policy_id=policy.id,
                kind="quality",
                idempotency_key=payload.idempotency_key,
                request_sha256=sha,
                parameters=dump(parameters),
            )
            session.add(row)
            try:
                session.flush()
                session.add(RunEvent(run_id=row.id, status="queued", message="已加入处理队列。"))
                session.commit()
            except IntegrityError:
                session.rollback()
                existing = session.scalar(
                    select(AnalysisRun).where(
                        AnalysisRun.project_id == str(project_id),
                        AnalysisRun.idempotency_key == payload.idempotency_key,
                    )
                )
                if existing and existing.request_sha256 == sha:
                    return run_read(existing, True)
                raise DataIssue(
                    "提交设置发生冲突，请刷新后重试。", "idempotency_conflict", 409
                ) from None
            return run_read(row, True)

    @router.get("/runs")
    def list_runs(
        project_id: UUID,
        dataset_version_id: UUID | None = None,
        kind: str | None = Query(default=None, max_length=32),
        limit: int = Query(default=30, ge=1, le=100),
    ):
        with app.state.sessions() as session:
            require_project(session, project_id)
            query = select(AnalysisRun).where(AnalysisRun.project_id == str(project_id))
            if kind:
                if kind not in TASK_SPECS:
                    raise DataIssue("请选择有效的处理类型。", "invalid_kind")
                query = query.where(AnalysisRun.kind == kind)
            if dataset_version_id:
                scoped(session, DatasetVersion, dataset_version_id, project_id)
                query = query.where(AnalysisRun.dataset_version_id == str(dataset_version_id))
            rows = session.scalars(query.order_by(AnalysisRun.created_at.desc()).limit(limit)).all()
            return {"items": [run_read(row) for row in rows]}

    @router.get("/runs/{run_id}")
    def detail(project_id: UUID, run_id: UUID):
        with app.state.sessions() as session:
            run = scoped(session, AnalysisRun, run_id, project_id)
            result = run_read(run, True)
            events = session.scalars(
                select(RunEvent).where(RunEvent.run_id == run.id).order_by(RunEvent.id).limit(50)
            ).all()
            result["events"] = [
                {"status": row.status, "message": row.message, "created_at": row.created_at}
                for row in events
            ]
            return result

    @router.post("/runs/{run_id}/cancel")
    def cancel(project_id: UUID, run_id: UUID):
        with app.state.sessions() as session:
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            run = scoped(session, AnalysisRun, run_id, project_id)
            if run.status in TERMINAL:
                return run_read(run, True)
            run.cancel_requested = 1
            if run.status == "queued":
                event(session, run, "cancelled", "已取消等待中的处理。")
                run.finished_at, run.phase = timestamp(), "cancelled"
            else:
                run.message = "正在取消当前处理。"
            session.commit()
            return run_read(run, True)

    @router.post("/runs/{run_id}/eligibility")
    def eligibility(project_id: UUID, run_id: UUID, payload: AnalysisParameters):
        with app.state.sessions() as session:
            run = scoped(session, AnalysisRun, run_id, project_id)
            if run.status not in PUBLISHED or not run.result:
                raise DataIssue("请先完成数据质量检查。", "quality_not_ready", 409)
            return require_capability(json.loads(run.result), payload)

    @router.get("/runs/{run_id}/rows")
    async def rows(
        project_id: UUID,
        run_id: UUID,
        view: str = "row_audit",
        offset: int = Query(default=0, ge=0, le=10000),
        limit: int = Query(default=20, ge=1, le=100),
    ):
        allowed = {"row_audit", "rf_orders", "rfm_orders", "amount_orders", "basket_items"}
        if view not in allowed:
            raise DataIssue("请选择有效的数据视图。", "invalid_view")
        with app.state.sessions() as session:
            run = scoped(session, AnalysisRun, run_id, project_id)
            if run.status not in PUBLISHED:
                raise DataIssue("结果尚未完成，暂不能查看明细。", "quality_not_ready", 409)
        path = app.state.storage / "runs" / str(project_id) / str(run_id) / (view + ".parquet")

        def read_preview():
            import pyarrow.parquet as pq

            file = pq.ParquetFile(path)
            remaining, result = offset, []
            for batch in file.iter_batches(batch_size=500):
                if remaining >= batch.num_rows:
                    remaining -= batch.num_rows
                    continue
                result.extend(
                    batch.slice(
                        remaining, min(limit - len(result), batch.num_rows - remaining)
                    ).to_pylist()
                )
                remaining = 0
                if len(result) >= limit:
                    break
            return {
                "view": view,
                "items": result,
                "total": file.metadata.num_rows,
                "offset": offset,
                "limit": limit,
            }

        return await asyncio.to_thread(read_preview)

    app.include_router(router)
