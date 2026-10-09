"""Real child-process queue guards in disposable databases; no production service restart."""

import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from app.database import create_database
from app.models import AnalysisRun, CleaningPolicy, DatasetVersion, MappingVersion, Project
from app.task_runner import TaskRunner


class TaskSafetyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.storage = self.root / "storage"
        self.storage.mkdir()
        self.engine, self.sessions = create_database(self.root / "test.sqlite3")
        with self.sessions() as db:
            p = Project(name="Test", name_key="test")
            db.add(p)
            db.flush()
            self.pid = p.id
            v = DatasetVersion(
                id=str(uuid4()),
                project_id=p.id,
                number=1,
                filename="fixture.csv",
                suffix=".csv",
                sha256="a" * 64,
                bytes=1,
                row_count=1,
                options="{}",
                preview="{}",
            )
            db.add(v)
            db.flush()
            self.vid = v.id
            m = MappingVersion(
                id=str(uuid4()), dataset_version_id=v.id, revision=1, config="{}", validation="{}"
            )
            db.add(m)
            db.flush()
            self.mid = m.id
            policy = CleaningPolicy(
                id=str(uuid4()),
                dataset_version_id=v.id,
                mapping_version_id=m.id,
                number=1,
                config="{}",
                config_sha256="b" * 64,
            )
            db.add(policy)
            db.commit()
            self.policy = policy.id
        self.app = SimpleNamespace(
            state=SimpleNamespace(
                sessions=self.sessions, storage=self.storage, import_lock=asyncio.Lock()
            )
        )
        self.runner = None

    async def asyncTearDown(self):
        if self.runner:
            await self.runner.stop()
        self.engine.dispose()
        self.tmp.cleanup()

    def seed(self, status="queued", cancelled=0, memory=8192):
        with self.sessions() as db:
            run = AnalysisRun(
                id=str(uuid4()),
                project_id=self.pid,
                dataset_version_id=self.vid,
                mapping_version_id=self.mid,
                policy_id=self.policy,
                kind="quality",
                idempotency_key=str(uuid4()),
                request_sha256="c" * 64,
                parameters=json.dumps({"scope": {}, "timeout_seconds": 600, "memory_mb": memory}),
                status=status,
                cancel_requested=cancelled,
            )
            db.add(run)
            db.commit()
            return run.id

    def get(self, rid):
        with self.sessions() as db:
            return db.get(AnalysisRun, rid)

    def make_runner(self, body, timeout=None):
        self.runner = TaskRunner(
            self.app,
            self.root / "test.sqlite3",
            worker_command=[sys.executable, "-B", "-c", body],
            timeout_override=timeout,
        )
        return self.runner

    async def test_timeout_child_terminated_unpublished(self):
        rid = self.seed()
        runner = self.make_runner("import time;time.sleep(10)", 0.1)
        await runner.execute(rid)
        run = self.get(rid)
        self.assertEqual((run.status, run.error_code), ("resource_limited", "timeout"))
        self.assertIsNone(run.result)
        self.assertFalse((self.storage / "runs" / self.pid / rid).exists())

    async def test_cancel_running_child(self):
        rid = self.seed()
        runner = self.make_runner("import time;time.sleep(10)")
        task = asyncio.create_task(runner.execute(rid))
        while self.get(rid).status != "running":
            await asyncio.sleep(0.02)
        with self.sessions() as db:
            db.get(AnalysisRun, rid).cancel_requested = 1
            db.commit()
        await task
        self.assertEqual(self.get(rid).status, "cancelled")
        self.assertFalse(list((self.storage / "runs" / self.pid).glob(".working-*")))

    async def test_memory_bound_child_terminated(self):
        rid = self.seed(memory=32)
        runner = self.make_runner("import time;x=bytearray(96*1024*1024);time.sleep(10)")
        await runner.execute(rid)
        run = self.get(rid)
        self.assertEqual((run.status, run.error_code), ("resource_limited", "memory_limit"))
        self.assertGreater(run.peak_rss_bytes, 32 * 1024**2)

    async def test_incomplete_artifacts_never_published(self):
        rid = self.seed()
        runner = self.make_runner("pass")
        await runner.execute(rid)
        self.assertEqual(self.get(rid).error_code, "incomplete_artifacts")
        self.assertIsNone(self.get(rid).result)

    async def test_recovery_preserves_queued_and_old_data(self):
        running = self.seed(status="running")
        queued = self.seed()
        runner = self.make_runner("pass")
        runner.recovery()
        self.assertEqual(self.get(running).status, "interrupted")
        self.assertEqual(self.get(running).error_code, "service_restarted")
        self.assertEqual(self.get(queued).status, "queued")
        with self.sessions() as db:
            self.assertEqual(db.get(DatasetVersion, self.vid).sha256, "a" * 64)

    async def test_single_consumer_fifo_and_cancel_queued(self):
        first = self.seed(cancelled=1)
        second = self.seed()
        runner = self.make_runner("pass")
        runner.start()
        for _ in range(150):
            if self.get(second).status == "failed":
                break
            await asyncio.sleep(0.05)
        self.assertEqual(self.get(first).status, "cancelled")
        self.assertEqual(self.get(second).error_code, "incomplete_artifacts")

    async def test_service_stop_interrupts_child(self):
        rid = self.seed()
        runner = self.make_runner("import time;time.sleep(10)")
        runner.start()
        while self.get(rid).status != "running":
            await asyncio.sleep(0.02)
        await runner.stop()
        self.assertEqual(
            (self.get(rid).status, self.get(rid).error_code), ("interrupted", "service_stopped")
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
