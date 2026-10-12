"""Exercise deletion on an isolated database and storage directory only."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from app.main import create_app
from app.models import AnalysisRun, CleaningPolicy, DatasetVersion, ImportDraft, MappingVersion, Project, RunEvent, SalesRecord
from app.task_runner import TaskRunner
import app.project_deletion as deletion


class DeleteProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.start = patch.object(TaskRunner, 'start'); self.start.start()
        self.stop = patch.object(TaskRunner, 'stop', new=AsyncMock()); self.stop.start()
        self.app = create_app(database_path=self.root / 'test.sqlite3', storage_root=self.root / 'storage')
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.client.__enter__()
        self.project = self.client.post('/api/projects', json={'name':'删除测试', 'description':'', 'color':'teal'}).json()
        self.other = self.client.post('/api/projects', json={'name':'必须保留', 'description':'', 'color':'blue'}).json()
        self.pid = self.project['id']
        self.version, self.mapping, self.policy, self.run, self.draft = [str(uuid4()) for _ in range(5)]
        with self.app.state.sessions() as session:
            session.add(DatasetVersion(id=self.version, project_id=self.pid, number=1, filename='test.csv', suffix='.csv', sha256='a'*64, bytes=4, row_count=1, options='{}', preview='{}')); session.flush()
            session.add(MappingVersion(id=self.mapping, dataset_version_id=self.version, revision=1, config='{}', validation='{}')); session.flush()
            session.add(CleaningPolicy(id=self.policy, dataset_version_id=self.version, mapping_version_id=self.mapping, number=1, config='{}', config_sha256='b'*64)); session.flush()
            session.add(AnalysisRun(id=self.run, project_id=self.pid, dataset_version_id=self.version, mapping_version_id=self.mapping, policy_id=self.policy, kind='sales', idempotency_key=str(uuid4()), request_sha256='c'*64, parameters='{}', status='succeeded', result='{}')); session.flush()
            session.add(RunEvent(run_id=self.run, status='succeeded', message='done'))
            session.add(SalesRecord(run_id=self.run, entry_key='test', value='{}'))
            session.add(ImportDraft(id=self.draft, project_id=self.pid, filename='test.csv', suffix='.csv', sha256='a'*64, bytes=4, inspection='{}', finalized_version_id=self.version))
            session.commit()
        self.files = [self.root / 'storage' / 'datasets' / 'projects' / self.pid / self.version / 'source.csv',
                      self.root / 'storage' / 'runs' / self.pid / self.run / 'sales_report.json',
                      self.root / 'storage' / 'imports' / self.draft / 'source.csv',
                      self.root / 'storage' / 'run_logs' / (self.run+'.log')]
        for file in self.files:
            file.parent.mkdir(parents=True, exist_ok=True); file.write_text('fixture')
        self.other_file = self.root / 'storage' / 'datasets' / 'projects' / self.other['id'] / 'keep.txt'
        self.other_file.parent.mkdir(parents=True); self.other_file.write_text('keep')

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.start.stop(); self.stop.stop(); self.temp.cleanup()

    def remove(self, revision=1):
        return self.client.delete(f'/api/projects/{self.pid}?revision={revision}')

    def assert_intact(self):
        self.assertEqual(self.client.get(f'/api/projects/{self.pid}').json()['revision'], 1)
        self.assertTrue(all(file.read_text() == 'fixture' for file in self.files))
        self.assertEqual(self.other_file.read_text(), 'keep')

    def test_owned_records_files_and_other_project(self):
        self.assertEqual(self.remove().status_code, 200)
        self.assertEqual(self.client.get(f'/api/projects/{self.pid}').status_code, 404)
        self.assertEqual(self.client.get('/api/projects').json()['total'], 1)
        self.assertEqual(self.client.get(f'/api/projects/{self.other["id"]}').status_code, 200)
        self.assertEqual(self.other_file.read_text(), 'keep')
        with self.app.state.sessions() as session:
            for model in [DatasetVersion, ImportDraft, MappingVersion, CleaningPolicy, AnalysisRun, RunEvent, SalesRecord]:
                self.assertEqual(session.scalar(select(func.count()).select_from(model)), 0)
        self.assertTrue(all(not file.exists() for file in self.files))
        recovery = next((self.root/'storage'/'deleted_projects').glob('*/records.json'))
        self.assertEqual(json.loads(recovery.read_text())['projects'][0]['revision'], 1)
        self.assertEqual(len(list((recovery.parent/'files').rglob('*.*'))), 4)

    def test_outdated_confirmation_and_missing_project(self):
        self.assertEqual(self.remove(99).status_code, 409)
        self.assertEqual(self.client.delete(f'/api/projects/{uuid4()}?revision=1').status_code, 404)
        self.assertEqual(self.client.delete('/api/projects/not-a-uuid?revision=1').status_code, 422)
        self.assert_intact()

    def test_active_task_is_not_deleted(self):
        with self.app.state.sessions() as session:
            session.get(AnalysisRun, self.run).status = 'queued'; session.commit()
        response = self.remove()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['error']['code'], 'project_busy')
        self.assert_intact()

    def test_file_failure_restores_database_and_moved_files(self):
        original = deletion.shutil.move
        count = 0
        def fail_second_move(*args):
            nonlocal count
            count += 1
            if count == 2: raise OSError('simulated file failure')
            return original(*args)
        with patch.object(deletion.shutil, 'move', side_effect=fail_second_move):
            self.assertEqual(self.remove().status_code, 500)
        self.assert_intact()

    def test_cross_site_delete_rejected(self):
        response = self.client.delete(f'/api/projects/{self.pid}?revision=1', headers={'origin':'https://example.invalid'})
        self.assertEqual(response.status_code, 403)
        self.assert_intact()


if __name__ == '__main__': unittest.main(verbosity=2)
