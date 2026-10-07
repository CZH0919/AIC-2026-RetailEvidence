import asyncio
import hashlib
import importlib.metadata
import json
import logging
import os
import platform
import shutil
import sys
import time

import psutil
from sqlalchemy import select

from .data_api import digest, dump, write_json
from .locks import FileLease
from .models import AnalysisRun, CleaningPolicy, DatasetVersion, MappingVersion, RunEvent, timestamp
from .settings import PROJECT_ROOT
from .task_registry import TASK_SPECS, completion_state

logger = logging.getLogger(__name__)
TERMINAL = {
    "succeeded",
    "completed_with_warnings",
    "not_applicable",
    "failed",
    "cancelled",
    "resource_limited",
    "interrupted",
}
PUBLISHED = {"succeeded", "completed_with_warnings", "not_applicable"}
PHASES = {
    "normalizing": "正在核验记录与字段。",
    "selecting": "正在检查订单与分析范围。",
    "preparing_views": "正在整理各项分析的有效数据。",
    "publishing": "正在保存质量结果。",
}


def event(session, run, status, message):
    run.status, run.message = status, message
    session.add(RunEvent(run_id=run.id, status=status, message=message))


class TaskRunner:
    def __init__(self, app, database_path, *, worker_command=None, timeout_override=None):
        self.app = app
        self.sessions = app.state.sessions
        self.storage = app.state.storage
        self.lease = FileLease(database_path.with_name("." + database_path.name + ".worker.lock"))
        self.worker_command = worker_command or [sys.executable, "-B", "-m", "app.task_worker"]
        self.timeout_override = timeout_override  # Only injectable by trusted in-process tests.
        self.stopping = False
        self.loop_task = None
        self.process = None
        self.code_hash = hashlib.sha256(
            b"".join(
                p.relative_to(PROJECT_ROOT).as_posix().encode() + p.read_bytes()
                for p in sorted((PROJECT_ROOT / "backend" / "app").glob("*.py"))
            )
        ).hexdigest()

    def start(self):
        self.loop_task = asyncio.create_task(self.loop())

    async def stop(self):
        self.stopping = True
        if self.loop_task:
            try:
                await asyncio.wait_for(asyncio.shield(self.loop_task), timeout=12)
            except TimeoutError:
                self.loop_task.cancel()
                try:
                    await self.loop_task
                except asyncio.CancelledError:
                    pass
        self.lease.release()

    def recovery(self):
        with self.sessions() as session:
            for run in session.scalars(select(AnalysisRun).where(AnalysisRun.status == "running")):
                event(session, run, "interrupted", "上次处理已中断，原数据保留；请确认后重新提交。")
                run.phase, run.finished_at, run.error_code = (
                    "interrupted",
                    timestamp(),
                    "service_restarted",
                )
                run.result = None
            session.commit()

    async def loop(self):
        recovered = False
        try:
            while not self.stopping:
                if not self.lease.acquire():
                    await asyncio.sleep(0.5)
                    continue
                if not recovered:
                    self.recovery()
                    recovered = True
                with self.sessions() as session:
                    identity = session.scalar(
                        select(AnalysisRun.id)
                        .where(AnalysisRun.status == "queued")
                        .order_by(AnalysisRun.created_at, AnalysisRun.id)
                        .limit(1)
                    )
                if identity:
                    try:
                        await self.execute(identity)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        logger.exception("Task consumer error")
                        self.finish(
                            identity,
                            "failed",
                            "处理未完成，原始数据仍保留，请重试。",
                            "internal_error",
                        )
                await asyncio.sleep(0.2)
        finally:
            self.lease.release()

    def finish(self, identity, status, message, code=None, peak=0):
        with self.sessions() as session:
            run = session.get(AnalysisRun, identity)
            if run and run.status not in TERMINAL:
                event(session, run, status, message)
                run.phase, run.finished_at, run.error_code = status, timestamp(), code
                run.peak_rss_bytes = max(run.peak_rss_bytes, peak)
                session.commit()

    async def terminate_child(self):
        if self.process and self.process.returncode is None:
            try:
                self.process.terminate()
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(self.process.wait(), timeout=3)
            except TimeoutError:
                self.process.kill()
                await self.process.wait()

    async def execute(self, identity):
        if self.app.state.import_lock.locked():
            return
        async with self.app.state.import_lock:
            heavy = FileLease(self.storage / ".import.lock")
            if not heavy.acquire():
                return
            staging = None
            final = None
            published = False
            staging_owned = False
            final_owned = False
            peak = 0
            try:
                with self.sessions() as session:
                    run = session.get(AnalysisRun, identity)
                    if run.status != "queued":
                        return
                    if run.cancel_requested:
                        self.finish(identity, "cancelled", "已取消处理。")
                        return
                    if shutil.disk_usage(self.storage).free < 20 * 1024**3:
                        self.finish(
                            identity,
                            "resource_limited",
                            "可用存储空间不足，请联系维护者。",
                            "disk_limit",
                        )
                        return
                    version = session.get(DatasetVersion, run.dataset_version_id)
                    mapping = session.get(MappingVersion, run.mapping_version_id)
                    policy = session.get(CleaningPolicy, run.policy_id)
                    parameters = json.loads(run.parameters)
                    specification = TASK_SPECS[run.kind]
                    final = self.storage / "runs" / run.project_id / run.id
                    staging = final.with_name(".working-" + run.id)
                    if final.exists() or staging.exists():
                        self.finish(
                            identity,
                            "failed",
                            "存在未完成的产物，请联系维护者核验。",
                            "artifact_conflict",
                        )
                        return
                    staging.mkdir(parents=True)
                    staging_owned = True
                    source = self.storage / "datasets" / "projects" / run.project_id / version.id
                    config = json.loads(mapping.config)
                    context = {
                        "project_id": run.project_id,
                        "data_version_id": version.id,
                        "mapping_revision": mapping.revision,
                        "policy_id": policy.id,
                        "run_id": run.id,
                    }
                    job = {
                        "kind": run.kind,
                        "parent_pid": os.getpid(),
                        "source": str(
                            source / "mappings" / str(mapping.revision) / "canonical.parquet"
                        ),
                        "raw_source": str(source / "raw.parquet"),
                        "output": str(staging),
                        "mapping": config,
                        "policy": json.loads(policy.config),
                        "scope": parameters["scope"],
                        "context": context,
                    }
                    inputs = {
                        "context": context,
                        "source_sha256": version.sha256,
                        "mapping_sha256": hashlib.sha256(mapping.config.encode()).hexdigest(),
                        "policy_sha256": policy.config_sha256,
                        "parameters": parameters,
                        "code_sha256": self.code_hash,
                        "application_version": "0.3.0",
                        "python": platform.python_version(),
                        "dependencies": {
                            name: importlib.metadata.version(name)
                            for name in ["pyarrow", "sqlalchemy", "psutil", "pydantic"]
                        },
                    }
                    event(session, run, "running", "开始检查数据质量。")
                    run.phase, run.started_at = "normalizing", timestamp()
                    session.commit()
                write_json(staging / ".job.json", job)
                env = {
                    **os.environ,
                    "PYTHONPATH": str(PROJECT_ROOT / "backend"),
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "OMP_NUM_THREADS": "2",
                    "OPENBLAS_NUM_THREADS": "2",
                    "MKL_NUM_THREADS": "2",
                    "NUMEXPR_NUM_THREADS": "2",
                }
                with (staging / "worker.log").open("wb") as log:
                    self.process = await asyncio.create_subprocess_exec(
                        *self.worker_command,
                        str(staging / ".job.json"),
                        env=env,
                        stdout=log,
                        stderr=log,
                    )
                    started = time.monotonic()
                    timeout = self.timeout_override or parameters["timeout_seconds"]
                    reason = None
                    while self.process.returncode is None:
                        with self.sessions() as session:
                            run = session.get(AnalysisRun, identity)
                            cancelled = bool(run.cancel_requested)
                            try:
                                progress = json.loads((staging / ".progress.json").read_text())
                                run.phase = progress["phase"]
                                run.progress = max(run.progress, min(99, int(progress["progress"])))
                                run.message = PHASES.get(run.phase, "正在检查数据质量。")
                            except (FileNotFoundError, ValueError, KeyError):
                                pass
                            try:
                                proc = psutil.Process(self.process.pid)
                                rss = sum(
                                    p.memory_info().rss
                                    for p in [proc, *proc.children(recursive=True)]
                                )
                                peak = max(peak, rss)
                            except psutil.Error:
                                pass
                            run.peak_rss_bytes = peak
                            session.commit()
                        if self.stopping:
                            reason = (
                                "interrupted",
                                "服务停止，处理已中断；请确认后重新提交。",
                                "service_stopped",
                            )
                        elif cancelled:
                            reason = ("cancelled", "已取消处理，原始数据保持完整。", None)
                        elif time.monotonic() - started > timeout:
                            reason = (
                                "resource_limited",
                                "处理超过本次时限，请缩小范围后重试。",
                                "timeout",
                            )
                        elif peak > parameters["memory_mb"] * 1024**2:
                            reason = (
                                "resource_limited",
                                "处理达到内存预算，请缩小范围后重试。",
                                "memory_limit",
                            )
                        if reason:
                            await self.terminate_child()
                            self.finish(identity, *reason, peak=peak)
                            return
                        await asyncio.sleep(0.2)
                    if self.process.returncode:
                        try:
                            code = json.loads((staging / ".error.json").read_text())["code"]
                        except (OSError, ValueError, KeyError):
                            code = "worker_error"
                        status = "resource_limited" if code == "memory_limit" else "failed"
                        self.finish(
                            identity,
                            status,
                            "处理未完成，原数据已保留，请调整范围或联系维护者。",
                            code,
                            peak,
                        )
                        return
                if not all((staging / name).is_file() for name in specification["artifacts"]):
                    self.finish(
                        identity,
                        "failed",
                        "结果未完整生成，未发布本次结果。",
                        "incomplete_artifacts",
                        peak,
                    )
                    return
                report = json.loads((staging / specification["report"]).read_text(encoding="utf-8"))
                if report["context"] != context:
                    raise ValueError("Result context mismatch")
                hashes = {
                    name: await asyncio.to_thread(digest, staging / name)
                    for name in specification["artifacts"]
                }
                write_json(
                    staging / "manifest.json",
                    {
                        **inputs,
                        "artifacts": hashes,
                        "peak_rss_bytes": peak,
                        "elapsed_seconds": round(time.monotonic() - started, 3),
                    },
                )
                # Internal job files contain machine-local paths; do not publish them as artifacts.
                for name in [".job.json", ".progress.json", ".progress.tmp"]:
                    (staging / name).unlink(missing_ok=True)
                with self.sessions() as session:
                    run = session.get(AnalysisRun, identity)
                    if run.cancel_requested or self.stopping:
                        self.finish(
                            identity,
                            "cancelled" if run.cancel_requested else "interrupted",
                            "处理已停止，未发布结果。",
                        )
                        return
                    state = completion_state(run.kind, report)
                    staging.rename(final)
                    final_owned = True
                    run.result = dump(report)
                    run.progress, run.phase, run.finished_at = 100, "finished", timestamp()
                    run.peak_rss_bytes = peak
                    event(session, run, state, "质量检查已完成，请查看各项分析的适用条件。")
                    session.commit()
                    published = True
            except asyncio.CancelledError:
                await self.terminate_child()
                self.finish(
                    identity,
                    "interrupted",
                    "服务停止，处理已中断；请重新提交。",
                    "service_stopped",
                    peak,
                )
                raise
            finally:
                await self.terminate_child()
                self.process = None
                if staging_owned and staging and staging.exists():
                    # Retain only a bounded diagnostic log outside the published result directory.
                    log_path = staging / "worker.log"
                    if log_path.exists():
                        logs = self.storage / "run_logs"
                        logs.mkdir(exist_ok=True)
                        with log_path.open("rb") as stream:
                            (logs / (identity + ".log")).write_bytes(stream.read(65536))
                    shutil.rmtree(staging)
                if final_owned and final and final.exists() and not published:
                    # Only a final directory created by this execution may be removed.
                    with self.sessions() as session:
                        run = session.get(AnalysisRun, identity)
                        if run.status not in PUBLISHED:
                            shutil.rmtree(final)
                heavy.release()
