import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import create_app
from app.models import AnalysisRun, CleaningPolicy, DatasetVersion, MappingVersion
from app.sales_automation import advance, initial_state
from app.sales_recommendations import compatible
from app.task_runner import TaskRunner


class AutomationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.start=patch.object(TaskRunner,'start');self.start.start()
        self.stop=patch.object(TaskRunner,'stop',new=AsyncMock());self.stop.start()
        self.app=create_app(database_path=self.root/'db.sqlite3')
        self.client=TestClient(self.app);self.client.__enter__()
        self.pid=self.client.post('/api/projects',json={'name':'自动分析测试','description':'','color':'teal'}).json()['id']
        self.vid,self.mid,self.policy,self.rid=[str(uuid4()) for _ in range(4)]
        self.sales={'sources':[{'version_id':self.vid,'mapping_revision':1}],'month':'2026-10','duplicates':'keep','coverage_start':'2026-09-01','coverage_end':'2026-11-30','source_hashes':{self.vid:'b'*64}}
        self.mapping={'columns':{'order_id':'c0','item_id':'c1','customer_id':'c2','event_time':'c3'},'order_boundary':'order_id','record_kind':'transactions'}
        with self.app.state.sessions() as s:
            s.add(DatasetVersion(id=self.vid,project_id=self.pid,number=1,filename='orders.csv',suffix='.csv',sha256='a'*64,bytes=1,row_count=1000,options='{}',preview='{}'));s.flush()
            s.add(MappingVersion(id=self.mid,dataset_version_id=self.vid,revision=1,config=json.dumps(self.mapping),validation='{}'));s.flush()
            s.add(CleaningPolicy(id=self.policy,dataset_version_id=self.vid,mapping_version_id=self.mid,number=1,config=json.dumps({'duplicates':'keep'}),config_sha256='b'*64));s.flush()
            s.add(AnalysisRun(id=self.rid,project_id=self.pid,dataset_version_id=self.vid,mapping_version_id=self.mid,policy_id=self.policy,kind='sales',idempotency_key='parent',request_sha256='c'*64,status='succeeded',parameters=json.dumps({'sales':self.sales,'auto_analysis':initial_state()}),result='{}'));s.commit()
        self.url=f'/api/projects/{self.pid}/sales/runs/{self.rid}/automatic'

    def tearDown(self):
        self.client.__exit__(None,None,None);self.start.stop();self.stop.stop();self.temp.cleanup()

    def state(self):return self.client.get(self.url).json()
    def children(self):
        with self.app.state.sessions() as s:
            return list(s.scalars(select(AnalysisRun).where(AnalysisRun.kind!='sales')))
    def advance(self):advance(self.app.state.sessions)
    def quality_ready(self, rfm=True, rf=True, association=True):
        for row in self.children():
            if row.kind!='quality':continue
            p=json.loads(row.parameters)
            result={'context':{'project_id':self.pid,'data_version_id':self.vid,'mapping_revision':1,'run_id':row.id},'scope':p['scope'],'policy':{'duplicates':'keep'},'automatic_parent':p['automatic_parent'],
                    'capabilities':{k:{'allowed':v,'state':'available'} for k,v in [('rfm',rfm),('rf',rf),('association',association)]},
                    'summary':{'rf_customers':80 if rf else 0,'complete_baskets':400 if association else 0}}
            with self.app.state.sessions() as s:
                q=s.get(AnalysisRun,row.id);q.status='succeeded';q.result=json.dumps(result);s.commit()

    def test_repeated_enrollment_and_scheduler_are_idempotent(self):
        self.assertEqual(self.client.post(self.url).status_code,200)
        self.client.post(self.url);self.advance();self.advance()
        self.assertEqual(len(self.children()),2)
        self.assertTrue(all(c.kind=='quality' for c in self.children()))
        # New scheduler invocation after restart reuses the persisted dependency IDs.
        advance(self.app.state.sessions)
        self.assertEqual(len(self.children()),2)

    def test_no_order_data_skips_both_without_heavy_tasks(self):
        with self.app.state.sessions() as s:
            m=s.get(MappingVersion,self.mid);mapping=json.loads(m.config);mapping['order_boundary']='unavailable';m.config=json.dumps(mapping);s.commit()
        self.advance()
        self.assertEqual(self.state()['status'],'complete')
        self.assertTrue(all(step['status']=='skipped' for step in self.state()['steps'].values()))
        self.assertEqual(self.children(),[])

    def test_no_customer_id_still_runs_pairing(self):
        with self.app.state.sessions() as s:
            m=s.get(MappingVersion,self.mid);mapping=json.loads(m.config);mapping['columns']['customer_id']=None;m.config=json.dumps(mapping);s.commit()
        self.advance();state=self.state()
        self.assertEqual(state['steps']['customers']['status'],'skipped')
        self.assertEqual(state['steps']['association']['status'],'preparing')
        self.assertEqual(len(self.children()),1)

    def test_monthly_pairings_and_historical_customers_have_distinct_scopes(self):
        self.advance();state=self.state()
        for kind,start in [('association','2026-10-01'),('customers','2026-09-01')]:
            row=next(r for r in self.children() if r.id==state['steps'][kind]['quality_run_id'])
            scope=json.loads(row.parameters)['scope']
            self.assertEqual(scope['date_start'],start)
            self.assertEqual(scope['date_end'],'2026-10-31')

    def test_prefers_rfm_and_falls_back_to_rf_without_amounts(self):
        self.advance();self.quality_ready(rfm=False);self.advance()
        analysis=[r for r in self.children() if r.kind=='clustering']
        self.assertEqual(len(analysis),1)
        self.assertEqual(json.loads(analysis[0].parameters)['analysis']['kind'],'rf')
        self.advance();self.assertEqual(len(self.children()),4)

    def test_insufficient_customers_does_not_block_pairings(self):
        self.advance();self.quality_ready(rfm=False,rf=False);self.advance()
        self.assertEqual(self.state()['steps']['customers']['status'],'skipped')
        self.assertEqual(self.state()['steps']['association']['status'],'running')

    def test_finished_models_update_status_and_do_not_repeat(self):
        self.advance();self.quality_ready();self.advance()
        with self.app.state.sessions() as s:
            for row in s.scalars(select(AnalysisRun).where(AnalysisRun.kind.in_(['association','clustering']))):
                row.status='succeeded';row.result=json.dumps({'summary':{'publishable':True},'top_rules':[{'lift':2}],'clusters':[{'cluster':0,'customers':50}],'analysis':{'mode':'RFM'}})
            s.commit()
        self.advance();self.advance()
        self.assertEqual(self.state()['status'],'complete')
        self.assertTrue(all(step['status']=='ready' for step in self.state()['steps'].values()))
        self.assertEqual(len(self.state()['customer_groups']),1)
        self.assertEqual(len(self.children()),4)

    def test_no_pattern_is_distinct_from_failure(self):
        self.advance();self.quality_ready();self.advance()
        with self.app.state.sessions() as s:
            for row in s.scalars(select(AnalysisRun).where(AnalysisRun.kind.in_(['association','clustering']))):
                row.status='completed_with_warnings';row.result=json.dumps({'summary':{'publishable':False}})
            s.commit()
        self.advance()
        self.assertTrue(all(step['status']=='no_result' for step in self.state()['steps'].values()))

    def test_failed_step_retries_without_repeating_successful_step(self):
        self.advance();self.quality_ready();self.advance()
        with self.app.state.sessions() as s:
            for row in s.scalars(select(AnalysisRun).where(AnalysisRun.kind.in_(['association','clustering']))):
                row.status='failed' if row.kind=='association' else 'succeeded'
                row.result=json.dumps({'summary':{'publishable':True},'clusters':[]})
            s.commit()
        self.advance();old=self.state()['steps']['customers']['run_id']
        self.client.post(self.url+'?retry=true');self.advance()
        self.assertEqual(self.state()['steps']['customers']['run_id'],old)
        self.assertEqual(self.state()['steps']['association']['status'],'preparing')

    def test_project_scoping(self):
        other=self.client.post('/api/projects',json={'name':'其他店铺','description':'','color':'teal'}).json()['id']
        self.assertEqual(self.client.post(self.url.replace(self.pid,other)).status_code,404)
        self.assertEqual(self.client.get(self.url.replace(self.pid,other)).status_code,404)

    def test_automatic_suggestions_only_use_the_exact_parent_and_sources(self):
        self.advance();self.quality_ready();self.advance()
        with self.app.state.sessions() as s:
            child=s.scalar(select(AnalysisRun).where(AnalysisRun.kind=='clustering'))
            q=json.loads(s.get(AnalysisRun,child.quality_run_id).result)
            report={'context':{'project_id':self.pid,'data_version_id':self.vid,'mapping_revision':1},
                    'summary':{'publishable':True},'analysis':{'reference_time':'2026-11-01'}}
            inputs={'context':{'project_id':self.pid,'run_id':self.rid},'month':'2026-10',
                    'sources':self.sales['sources'],'parameters':self.sales}
            self.assertTrue(compatible(inputs,child,report,q))
            inputs['context']['run_id']='another-report'
            self.assertFalse(compatible(inputs,child,report,q))
            inputs['context']['run_id']=self.rid
            inputs['parameters']={**self.sales,'sources':[{'version_id':self.vid,'mapping_revision':2}]}
            self.assertFalse(compatible(inputs,child,report,q))


if __name__=='__main__':unittest.main()
