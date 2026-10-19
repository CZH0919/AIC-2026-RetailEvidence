import json
import unittest
from copy import deepcopy
from uuid import uuid4
from sqlalchemy import event
from app.models import AnalysisRun
from app.report_navigation import matches_month, month_scope
import test_sales_loading


class NavigationTests(unittest.TestCase):
    def setUp(self):
        self.base = test_sales_loading.SalesLoadingTests()
        self.base.setUp()

    def tearDown(self): self.base.tearDown()

    def add(self, session, kind='sales', status='succeeded', result='{}', **kwargs):
        b=self.base
        row=AnalysisRun(id=str(uuid4()), project_id=b.pid, dataset_version_id=b.vid,
            mapping_version_id=b.mid, policy_id=b.policy, kind=kind,
            idempotency_key=str(uuid4()), request_sha256='c'*64,
            parameters=json.dumps({'sales': {'month':'2026-09', 'sources':[], 'check_only':False}}),
            status=status, result=result, finished_at='2026-10-19', **kwargs)
        session.add(row);session.flush();return row

    def test_catalog_includes_older_month_beyond_100_without_large_results(self):
        b=self.base
        with b.app.state.sessions() as s:
            for _ in range(103): self.add(s)
            check=self.add(s);check.parameters=json.dumps({'sales':{'month':'2026-10','check_only':True}})
            running=self.add(s,status='running');missing=self.add(s,result=None)
            ids=running.id,missing.id;s.commit();engine=s.get_bind()
        queries=[]
        def capture(conn,cursor,statement,parameters,context,many): queries.append(statement)
        event.listen(engine,'before_cursor_execute',capture)
        try: response=b.client.get(f'/api/projects/{b.pid}/sales/reports')
        finally: event.remove(engine,'before_cursor_execute',capture)
        self.assertEqual(response.status_code,200,response.text)
        rows=response.json()['items'];self.assertEqual(len(rows),106)
        self.assertTrue(any(r['id']==b.rid for r in rows))
        self.assertTrue(all('result' not in r for r in rows))
        self.assertTrue(all(not r['has_result'] for r in rows if r['id'] in ids))
        self.assertFalse(any('analysis_runs.result,' in q.lower().split('from')[0] for q in queries))
        self.assertEqual(b.client.get(f'/api/projects/{uuid4()}/sales/reports').status_code,404)

    def test_month_pairing_rejects_foreign_preference_and_other_period(self):
        b=self.base
        sales={'month':'2026-10','duplicates':'keep','sources':[{'version_id':b.vid,'mapping_revision':1}]}
        with b.app.state.sessions() as s:
            s.get(AnalysisRun,b.rid).parameters=json.dumps({'sales':sales})
            q=self.add(s,kind='quality')
            qc={'project_id':b.pid,'data_version_id':b.vid,'mapping_revision':1,'run_id':q.id}
            quality={'context':qc,'scope':month_scope('2026-10'),'policy':{'duplicates':'keep'}}
            q.result=json.dumps(quality)
            a=self.add(s,kind='association',quality_run_id=q.id)
            a.result=json.dumps({'context':{**qc,'run_id':a.id,'quality_run_id':q.id},'summary':{'publishable':True}})
            good=a.id
            old=self.add(s,kind='quality');old.result=json.dumps({**quality,'context':{**qc,'run_id':old.id},'scope':month_scope('2026-09')})
            bad=self.add(s,kind='association',quality_run_id=old.id);bad.result=json.dumps({'context':{**qc,'run_id':bad.id,'quality_run_id':old.id}})
            bad_id=bad.id;s.commit()
        response=b.client.get(b.url+'/pairings',params={'version_id':b.vid,'preferred':bad_id})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['current']['id'],good)
        self.assertEqual(b.client.get(b.url+'/pairings',params={'version_id':str(uuid4())}).json()['current'],None)
        self.assertEqual(b.client.get(b.url.replace(b.pid,b.other)+'/pairings',params={'version_id':b.vid}).status_code,404)


class ScopeTests(unittest.TestCase):
    def test_date_mapping_policy_and_scope_all_must_match(self):
        sales={'month':'2024-02','duplicates':'keep','sources':[{'version_id':'v','mapping_revision':2}]}
        q={'context':{'project_id':'p','data_version_id':'v','mapping_revision':2},'policy':{'duplicates':'keep'},'scope':month_scope('2024-02')}
        self.assertEqual(q['scope']['date_end'],'2024-02-29')
        self.assertTrue(matches_month(q,sales,'v','p'))
        for key,value in [('date_start',None),('date_end','2024-03-01'),('countries',['CN']),('item_ids',['A']),('currency','USD')]:
            changed=deepcopy(q);changed['scope'][key]=value
            self.assertFalse(matches_month(changed,sales,'v','p'))
        changed=deepcopy(q);changed['context']['mapping_revision']=3
        self.assertFalse(matches_month(changed,sales,'v','p'))
        changed=deepcopy(q);changed['policy']['duplicates']='drop_exact'
        self.assertFalse(matches_month(changed,sales,'v','p'))

if __name__ == '__main__': unittest.main()
