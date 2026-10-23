import csv
import io
import json
from copy import deepcopy
from uuid import uuid4
from sqlalchemy import event

from app.models import AnalysisRun
from test_sales_loading import SalesLoadingTests
from test_sales_recommendations import inputs, customers, pair, quality


class RecommendationApiTests(SalesLoadingTests):
    def prepare(self):
        data = inputs()
        data['context'] = {'project_id': self.pid, 'run_id': self.rid}
        data['sources'][0]['version_id'] = self.vid
        data['sources'][0]['filename'] = 'test.csv'
        data['summary'].update(products=3, attention_total=3, unit='件', amount_label='销售额')
        for p in data['products']:
            p['reason'] = '原始商品说明'
        self.report.update(context=data['context'], month=data['month'], parameters=data['parameters'],
                           sources=data['sources'], summary=data['summary'], products=data['products'],
                           highlights=['A'], actions=[{'id': 'old', 'title': '旧建议'}])
        self.report['notices'] = []
        self.report['change_drivers'] = {'items': []}
        self.report['chart'] = []
        self.qid = str(uuid4())
        q = quality(); q['context'].update(project_id=self.pid, data_version_id=self.vid, run_id=self.qid)
        with self.app.state.sessions() as s:
            s.get(AnalysisRun, self.rid).result = json.dumps(self.report)
            s.add(self.row(self.qid, 'quality', q))
            s.commit()

    def row(self, rid, kind, report, **kwargs):
        return AnalysisRun(id=rid, project_id=self.pid, dataset_version_id=self.vid,
                           mapping_version_id=self.mid, policy_id=self.policy,
                           quality_run_id=kwargs.get('quality_run_id'), kind=kind,
                           idempotency_key=str(uuid4()), request_sha256='e'*64, parameters='{}',
                           status='succeeded', result=json.dumps(report), finished_at='2026-10-19')

    def add_analysis(self, fixture, future=False):
        rid = str(uuid4()); report = deepcopy(fixture['report'])
        report['context'].update(project_id=self.pid, data_version_id=self.vid,
                                 run_id=rid, quality_run_id=self.qid)
        if future:
            report['analysis']['reference_time'] = '2026-12-10'
        with self.app.state.sessions() as s:
            s.add(self.row(rid, fixture['kind'], report, quality_run_id=self.qid)); s.commit()
        return rid

    def test_new_analysis_refreshes_cache_and_customers_download_is_scoped(self):
        self.prepare()
        first = self.client.get(self.url+'/workspace').json()['result']
        self.assertEqual(len(first['actions']), 2)
        cluster_id = self.add_analysis(customers())
        directory = self.app.state.storage/'runs'/self.pid/cluster_id
        directory.mkdir(parents=True)
        (directory/'customer_opportunities.json').write_text(json.dumps(customers()['report']['customer_opportunities']))
        (directory/'customer_followup.csv').write_text('customer_id,purchase_days,usual_gap_days,last_purchase,days_since_purchase,threshold_days\nkept,5,10,2026-10-10,22,17\n=unsafe,6,10,2026-10-10,22,17\n',encoding='utf-8')

        second = self.client.get(self.url+'/workspace').json()['result']
        action = next(a for a in second['actions'] if a.get('target',{}).get('kind') == 'customer')
        response = self.client.get(self.url+'/action-customers', params={'action_id':action['id']})
        self.assertEqual(response.status_code,200)
        rows = list(csv.reader(io.StringIO(response.content.decode('utf-8-sig'))))
        self.assertEqual([r[0] for r in rows[1:]], ['kept', "'=unsafe"])
        self.assertEqual(self.client.get(self.url.replace(self.pid,self.other)+'/action-customers',params={'action_id':action['id']}).status_code,404)
        self.assertEqual(self.client.get(self.url+'/action-customers',params={'action_id':'unknown'}).status_code,404)
        self.assertEqual(self.client.put(self.url+'/actions/'+action['id'],json={'status':'done','note':'客户建议备注','expected_revision':0}).status_code,200)
        strong_pair = pair()
        strong_pair['report']['top_rules'][0].update(n_ab=240, n_b=300, confidence_lower=.5, lift=2)
        self.add_analysis(strong_pair)
        third = self.client.get(self.url+'/workspace').json()['result']
        self.assertTrue(any(a.get('target',{}).get('kind')=='pairing' for a in third['actions']))
        self.assertEqual(len(third['actions']),3)
        self.assertEqual(third['summary'],self.report['summary'])
        for a in third['actions']:
            self.assertTrue(a['title'] in self.client.get(self.url+'/report').text)
        self.assertIn('action:'+action['id'],self.client.get(self.url+'/records').json()['items'])
        statements=[]
        with self.app.state.sessions() as s: engine=s.get_bind()
        def record(conn,cursor,statement,params,context,many): statements.append(statement)
        event.listen(engine,'before_cursor_execute',record)
        try: self.assertEqual(self.client.get(self.url+'/workspace').status_code,200)
        finally: event.remove(engine,'before_cursor_execute',record)
        self.assertFalse(any('analysis_runs.result' in sql.lower().split('from')[0] for sql in statements))
        with self.app.state.sessions() as s:
            self.assertEqual(json.loads(s.get(AnalysisRun,self.rid).result),self.report)

    def test_future_customer_analysis_is_not_used(self):
        self.prepare(); self.add_analysis(customers(), future=True)
        report = self.client.get(self.url+'/workspace').json()['result']
        self.assertFalse(any(a.get('category')=='客户回访' for a in report['actions']))
