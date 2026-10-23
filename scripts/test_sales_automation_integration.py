"""Actual CPU workers in temporary storage: upload submission through both follow-ups."""
import asyncio
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pyarrow as pa
import pyarrow.parquet as pq
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import create_app
from app.models import AnalysisRun, DatasetVersion, MappingVersion
from app.sales_automation import advance
from app.task_runner import TaskRunner, PUBLISHED
from app.data_schemas import FIELDS


class AutomationIntegration(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.start=patch.object(TaskRunner,'start');self.start.start()
        self.stop=patch.object(TaskRunner,'stop',new=AsyncMock());self.stop.start()
        self.app=create_app(database_path=self.root/'db.sqlite3');self.client=TestClient(self.app);self.client.__enter__()
        self.pid=self.client.post('/api/projects',json={'name':'真实队列集成验证','description':'','color':'teal'}).json()['id']

    def tearDown(self):
        self.client.__exit__(None,None,None);self.start.stop();self.stop.stop();self.temp.cleanup()

    def source(self, number, month, orders, customer=True, amounts=True, future=False):
        vid,mid=str(uuid4()),str(uuid4());rows=[]
        for i in range(orders+(50 if future else 0)):
            day=f'{month}-{1+i%28:02}' if i<orders else '2026-11-01'
            # A/B co-purchases plus single-item orders provide genuine rule variation.
            goods=['A','B'] if i%10<7 else ['A'] if i%10<9 else ['B']
            for item in goods:
                row={k:None for k in FIELDS}
                row.update(source_row_id=f'{number}:{len(rows)}',order_id=f'O{number}-{i}',item_id=item,item_name='商品'+item,
                           customer_id=f'C{i%80}' if customer else None,event_time=f'{day}T12:{i%60:02}:00+00:00',quantity='2',unit_price='5' if amounts else None)
                rows.append(row)
        schema=pa.schema([('source_row_id',pa.string())]+[(k,pa.string()) for k in FIELDS])
        folder=self.app.state.storage/'datasets/projects'/self.pid/vid/'mappings/1';folder.mkdir(parents=True)
        path=folder/'canonical.parquet';pq.write_table(pa.Table.from_pylist(rows,schema=schema),path)
        columns={k:k for k in ['order_id','item_id','item_name','event_time','quantity']}
        if customer:columns['customer_id']='customer_id'
        if amounts:columns['unit_price']='unit_price'
        mapping={'columns':columns,'order_boundary':'order_id','amount_mode':'quantity_unit_price' if amounts else 'none',
                 'currency_constant':'CNY' if amounts else None,'quantity_unit':'件','time_format':'iso8601','timezone':'UTC',
                 'status_rule':'all_forward','status_values':{},'record_kind':'transactions','confirmed':True}
        (folder/'mapping.json').write_text(json.dumps({'config':mapping}))
        with self.app.state.sessions() as s:
            s.add(DatasetVersion(id=vid,project_id=self.pid,number=number,filename=f'orders-{number}.csv',suffix='.csv',sha256=hashlib.sha256(vid.encode()).hexdigest(),bytes=100,row_count=len(rows),options='{}',preview='{}'));s.flush()
            s.add(MappingVersion(id=mid,dataset_version_id=vid,revision=1,config=json.dumps(mapping),validation='{}'));s.commit()
        return {'version_id':vid,'mapping_revision':1}

    def drain(self):
        for _ in range(10):
            advance(self.app.state.sessions)
            with self.app.state.sessions() as s:
                row=s.scalar(select(AnalysisRun).where(AnalysisRun.status=='queued').order_by(AnalysisRun.created_at,AnalysisRun.id))
                identity=row.id if row else None
            if not identity:return
            asyncio.run(self.app.state.task_runner.execute(identity))
            with self.app.state.sessions() as s:
                row=s.get(AnalysisRun,identity)
                self.assertIn(row.status,PUBLISHED,f'{row.kind}: {row.status}: {row.message}: {row.error_code}')
        self.fail('Automatic pipeline did not finish')

    def test_sales_submission_automatically_computes_both_over_merged_history(self):
        sources=[self.source(1,'2026-09',200),self.source(2,'2026-10',500,future=True)]
        body={'sources':sources,'month':'2026-10','idempotency_key':'automatic-integration-upload'}
        response=self.client.post(f'/api/projects/{self.pid}/sales/runs',json=body)
        self.assertEqual(response.status_code,202,response.text);rid=response.json()['id']
        self.assertEqual(self.client.post(f'/api/projects/{self.pid}/sales/runs',json=body).json()['id'],rid)
        # No calls to the customer/grouping endpoints or the automatic enrollment endpoint.
        self.drain()
        root=f'/api/projects/{self.pid}/sales/runs/{rid}'
        state=self.client.get(root+'/automatic').json();self.assertEqual(state['status'],'complete',state)
        self.assertIn(state['steps']['customers']['status'],{'ready','no_result'})
        self.assertIn(state['steps']['association']['status'],{'ready','no_result'})
        with self.app.state.sessions() as s:
            count=len(list(s.scalars(select(AnalysisRun))))
            cluster=s.get(AnalysisRun,state['steps']['customers']['run_id']);report=json.loads(cluster.result)
            self.assertEqual(report['analysis']['reference_time'][:10],'2026-11-01')
            quality=s.get(AnalysisRun,cluster.quality_run_id);q=json.loads(quality.result)
            self.assertEqual(q['summary']['rf_orders'],700)
            association=s.get(AnalysisRun,state['steps']['association']['run_id'])
            q=json.loads(s.get(AnalysisRun,association.quality_run_id).result)
            self.assertEqual(q['summary']['complete_baskets'],500)
            self.assertEqual(q['scope']['date_start'],'2026-10-01')
            self.assertLessEqual(q['summary']['latest_valid_order_time'][:10],'2026-10-31')
        frame=pq.read_table(self.app.state.storage/'runs'/self.pid/cluster.id/'customer_features.parquet').to_pandas()
        self.assertGreater(frame['frequency'].max(),7)
        paired=self.client.get(root+'/pairings',params={'version_id':sources[0]['version_id']}).json()
        self.assertEqual(paired['current']['id'],association.id)
        overview=self.client.get(root+'/workspace');self.assertEqual(overview.status_code,200,overview.text)
        self.client.post(root+'/automatic');self.drain()
        with self.app.state.sessions() as s:self.assertEqual(len(list(s.scalars(select(AnalysisRun)))),count)

    def test_no_amounts_or_customer_still_automatically_analyzes_baskets(self):
        source=self.source(1,'2026-10',250,customer=False,amounts=False)
        response=self.client.post(f'/api/projects/{self.pid}/sales/runs',json={'sources':[source],'month':'2026-10','idempotency_key':'automatic-no-customer'})
        self.assertEqual(response.status_code,202,response.text);rid=response.json()['id']
        self.drain()
        state=self.client.get(f'/api/projects/{self.pid}/sales/runs/{rid}/automatic').json()
        self.assertEqual(state['steps']['customers']['status'],'skipped')
        self.assertIn(state['steps']['association']['status'],{'ready','no_result'})
        with self.app.state.sessions() as s:self.assertFalse(list(s.scalars(select(AnalysisRun).where(AnalysisRun.kind=='clustering'))))


if __name__=='__main__':unittest.main()
