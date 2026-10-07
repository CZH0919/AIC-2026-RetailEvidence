import asyncio
import json
import os
import shutil
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from .import_formats import DataIssue
from .settings import PROJECT_ROOT


@asynccontextmanager
async def exclusive(app):
    """Bound expensive jobs across requests and Linux app processes sharing storage."""
    if app.state.import_lock.locked():
        raise DataIssue("另一份文件正在处理，请稍后重试。", "import_busy", 409)
    async with app.state.import_lock:
        root = app.state.storage
        root.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(root).free < 20 * 1024**3:
            raise DataIssue("可用存储空间不足，请联系维护者后重试。", "disk_limit", 507)
        with (root / ".import.lock").open("ab") as handle:
            if sys.platform != "win32":
                import fcntl

                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as exc:
                    raise DataIssue("另一份文件正在处理，请稍后重试。", "import_busy", 409) from exc
            try:
                yield
            finally:
                if sys.platform != "win32":
                    fcntl.flock(handle, fcntl.LOCK_UN)


async def run_job(folder: Path, action: str, **kwargs):
    token = uuid4().hex
    job_path, response_path = folder / f".job-{token}.json", folder / f".result-{token}.json"
    job_path.write_text(
        json.dumps({"action": action, "response": str(response_path), **kwargs}), encoding="utf-8"
    )
    env = {
        **os.environ,
        "PYTHONPATH": str(PROJECT_ROOT / "backend"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "OMP_NUM_THREADS": "2",
        "OPENBLAS_NUM_THREADS": "2",
        "MKL_NUM_THREADS": "2",
        "NUMEXPR_NUM_THREADS": "2",
    }
    process = None
    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-B",
            "-m",
            "app.import_worker",
            str(job_path),
            env=env,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            await asyncio.wait_for(process.wait(), timeout=600)
        except TimeoutError as exc:
            raise DataIssue(
                "处理超过 10 分钟，请缩小文件后重试。", "processing_timeout", 408
            ) from exc
        if process.returncode or not response_path.exists():
            raise DataIssue("文件处理未完成，请缩小文件或稍后重试。", "worker_failed", 422)
        response = json.loads(response_path.read_text(encoding="utf-8"))
        if "error" in response:
            raise DataIssue(**response["error"])
        return response["result"]
    finally:
        if process and process.returncode is None:
            process.kill()
            await process.wait()
        job_path.unlink(missing_ok=True)
        response_path.unlink(missing_ok=True)
