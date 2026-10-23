"""Isolated HTTP and SQL regression tests for lightweight sales report reads."""
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy import event
from app.main import create_app
from app.models import AnalysisRun, CleaningPolicy, DatasetVersion, MappingVersion
from app.task_runner import TaskRunner
from app.sales_views import VIEW_DIR, product_bytes, write_views
from app.sales_actions import action_view

class SalesLoadingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
        self.start=patch.object(TaskRunner,'start');self.start.start()
        self.stop=patch.object(TaskRunner,'stop',new=AsyncMock());self.stop.start()
        self.app=create_app(database_path=self.root/'test.sqlite3',storage_root=self.root/'storage')
        self.client=TestClient(self.app);self.client.__enter__()
        self.pid=self.client.post('/api/projects',json={'name':'性能测试','description':'','color':'teal'}).json()['id']
        self.other=self.client.post('/api/projects',json={'name':'其他店铺','description':'','color':'teal'}).json()['id']
        self.rid,self.vid,self.mid,self.policy=[str(uuid4()) for _ in range(4)]
        self.products=[{'id':str(i)+'/中文','name':'商品'+str(i),'quantity':i,'amount':None if i==2 else i*10,'change':None,'flags':['growth'] if i%2 else [],'daily':[{'date':'2026-10-01','quantity':i}]*100,'anomalies':[{'date':'2026-10-01','actual':i,'reference':1}] if i%2 else [],'forecast':{'quantity':5} if i%3 else None,'profile':{'labels':['稳定']},'reason':'原始说明','item_type':{'kind':'unknown'}} for i in range(1,9)]
        self.report={'context':{'run_id':self.rid},'month':'2026-10','products':self.products,'highlights':[self.products[i]['id'] for i in [5,1,0]],'summary':{'products':8,'quantity':36,'unit':'原始商品单位'},'chart':[{'date':'2026-10-01','quantity':36}],'actions':[{'id':'a','related_items':[p['id'] for p in self.products]}],'attention_ids':[p['id'] for p in self.products if p['flags']],'change_drivers':{'comparable':True,'items':[{'item_id':p['id'],'amount_change':p['amount']} for p in self.products]},'parameters':{'month':'2026-10'},'quality':{'input_rows':8},'forecast':{'status':'ok'},'anomaly':{'status':'ok'}}
        with self.app.state.sessions() as s:
            s.add(DatasetVersion(id=self.vid,project_id=self.pid,number=1,filename='a.csv',suffix='.csv',sha256='a'*64,bytes=1,row_count=8,options='{}',preview='{}'));s.flush()
            s.add(MappingVersion(id=self.mid,dataset_version_id=self.vid,revision=1,config='{}',validation='{}'));s.flush()
            s.add(CleaningPolicy(id=self.policy,dataset_version_id=self.vid,mapping_version_id=self.mid,number=1,config='{}',config_sha256='b'*64));s.flush()
            s.add(AnalysisRun(id=self.rid,project_id=self.pid,dataset_version_id=self.vid,mapping_version_id=self.mid,policy_id=self.policy,kind='sales',idempotency_key=str(uuid4()),request_sha256='c'*64,parameters=json.dumps({'sales':{'month':'2026-10','check_only':False}}),status='succeeded',result=json.dumps(self.report),finished_at='2026-10-16'));s.commit()
        self.url=f'/api/projects/{self.pid}/sales/runs/{self.rid}'
    def tearDown(self):
        self.client.__exit__(None,None,None);self.start.stop();self.stop.stop();self.temp.cleanup()
    def test_views_and_all_product_details_preserve_exact_values(self):
        overview=self.client.get(self.url+'/workspace').json()['result']
        normalized=action_view(self.report);expected=deepcopy(normalized);expected['products']=[p for p in normalized['products'] if p['id'] in normalized['highlights']];expected['change_drivers']['items']=expected['change_drivers']['items'][:5]
        self.assertEqual(overview.pop('recommendation_version'), 'recommendations-v1')
        counts=overview.pop('workspace_counts');self.assertEqual(overview,expected)
        self.assertEqual(counts,{'forecast':6,'anomaly':4,'has_daily':True})
        result=self.client.get(self.url+'/workspace?view=products').json()['result']
        for old,new in zip(normalized['products'],result['products']):
            self.assertTrue(new.pop('has_daily'));self.assertEqual(new.pop('daily'),[])
            self.assertEqual(new,{k:v for k,v in old.items() if k!='daily'})
            self.assertEqual(self.client.get(self.url+'/product',params={'item_id':old['id']}).json(),old)
        with self.app.state.sessions() as s:self.assertEqual(json.loads(s.get(AnalysisRun,self.rid).result),self.report)
    def test_cached_reads_and_list_do_not_select_large_result(self):
        self.client.get(self.url+'/workspace')
        statements=[]
        with self.app.state.sessions() as s: engine=s.get_bind()
        def record(conn,cursor,statement,params,context,many):statements.append(statement)
        event.listen(engine,'before_cursor_execute',record)
        try:
            self.assertEqual(self.client.get(self.url+'/workspace').status_code,200)
            self.assertEqual(self.client.get(self.url+'/records').json(),{'items':{}})
            listing=self.client.get(f'/api/projects/{self.pid}/runs?kind=sales&limit=100').json()
            self.assertEqual(listing['items'][0]['parameters']['sales']['month'],'2026-10')
        finally:event.remove(engine,'before_cursor_execute',record)
        self.assertFalse(any('analysis_runs.result' in q.lower().split('from')[0] for q in statements),statements)
    def test_scoping_and_unknown_item(self):
        self.client.get(self.url+'/workspace')
        other=self.url.replace(self.pid,self.other)
        self.assertEqual(self.client.get(other+'/workspace').status_code,404)
        self.assertEqual(self.client.get(other+'/product',params={'item_id':self.products[0]['id']}).status_code,404)
        self.assertEqual(self.client.get(self.url+'/product',params={'item_id':'../../missing'}).status_code,404)
        self.assertEqual(self.client.get(self.url+'/workspace?view=bad').status_code,422)
    def test_running_and_failed_are_not_published_even_with_cache(self):
        self.client.get(self.url+'/workspace')
        for status in ['queued','running','failed','cancelled']:
            with self.app.state.sessions() as s:s.get(AnalysisRun,self.rid).status=status;s.commit()
            data=self.client.get(self.url+'/workspace').json();self.assertEqual(data['status'],status);self.assertIsNone(data['result'])
            self.assertEqual(self.client.get(self.url+'/product',params={'item_id':self.products[0]['id']}).status_code,409)
    def test_worker_projection_and_empty_monthly_history(self):
        report=deepcopy(self.report);report['products']=[];report['highlights']=[];report.pop('change_drivers');report['chart']=[]
        directory=write_views(self.root/'worker',report)
        self.assertEqual(json.loads((directory/'products.json').read_bytes())['products'],[])
        self.assertEqual(json.loads((directory/'overview.json').read_bytes())['workspace_counts'],{'forecast':0,'anomaly':0,'has_daily':False})
        self.assertFalse(list((self.root/'worker').glob('.sales-views-building-*')))

if __name__=='__main__':unittest.main()
