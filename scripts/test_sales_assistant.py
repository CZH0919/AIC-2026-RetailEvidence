import copy
import json
import unittest
from unittest.mock import patch

from app.sales_assistant import prepare_answer, compose, infer_answer


def fixture():
    p = {'id': 'A01', 'name': '帆布袋', 'quantity': 100, 'amount': 1000,
         'category': None, 'change': .25, 'flags': ['growth'], 'daily': [], 'anomalies': [],
         'forecast': None, 'reason': '本月售出 100 件，上月为 80 件。',
         'contribution': {'previous_quantity': 80, 'current_quantity': 100, 'period': 'both'},
         'item_type': {'kind': 'physical'}}
    return {'month': '2026-09', 'summary': {'quantity': 100, 'unit': '件', 'amount': 1000,
            'currency': 'CNY', 'previous': {'quantity': 80, 'amount': 800}, 'complete_month': True,
            'products': 1, 'attention_total': 1}, 'products': [p], 'actions': [],
            'highlights': ['A01'], 'attention_ids': ['A01'], 'chart': [],
            'forecast': {'status': 'unavailable'}, 'anomaly': {'status': 'unavailable', 'reason': '需要每日销售记录。'},
            'quality': {'input_rows': 10, 'included_rows': 9, 'excluded_rows': 1, 'reasons': []},
            'sources': [], 'context': {}, 'parameters': {'month': '2026-09', 'duplicates': 'keep'}}


class AnswerTests(unittest.TestCase):
    def answer(self, question, **kwargs):
        return compose(prepare_answer(self.report, question, **kwargs))['answer']

    def setUp(self): self.report = fixture()

    def test_overview_does_not_select_highlight(self):
        answer = self.answer('本月销量怎么样？')
        self.assertIn('100 件', answer); self.assertIn('25%', answer)
        self.assertNotIn('帆布袋', answer)

    def test_specific_product_no_overview(self):
        self.report['summary']['quantity'] = 9999
        answer = self.answer('帆布袋销量有什么变化？')
        self.assertIn('上月为 80', answer); self.assertNotIn('9,999', answer)

    def test_product_code_next_to_chinese_and_legacy_reason_no_repetition(self):
        self.assertIn('帆布袋', self.answer('A01销量有什么变化？'))
        self.report['products'][0].pop('contribution')
        answer=self.answer('A01销量有什么变化？')
        self.assertEqual(answer.count('100'),1)
        self.assertIn('80',answer)

    def test_decline_ranking_is_not_top_seller(self):
        self.report['products'].append({**self.report['products'][0], 'id':'B02','name':'马克杯','quantity':20,'change':-.5,'reason':'销量减少。'})
        answer=self.answer('哪些商品销量下降最多？')
        self.assertIn('马克杯',answer);self.assertNotIn('帆布袋',answer)

    def test_no_arbitrary_product_for_inventory(self):
        self.assertIn('哪个商品', self.answer('下次进货要多少？'))
        self.assertIn('名称或编号', self.answer('XYZ销量呢？', item_id='A01'))

    def test_named_product_overrides_context_case_insensitive(self):
        other = {**self.report['products'][0], 'id': 'B02', 'name': 'RABBIT NIGHT LIGHT'}
        self.report['products'].append(other)
        answer = self.answer('rabbit night light本月销量', item_id='A01')
        self.assertIn('RABBIT NIGHT LIGHT', answer);self.assertNotIn('帆布袋', answer)

    def test_ambiguous_names_ask_for_id(self):
        self.report['products'].append({**self.report['products'][0], 'id': 'B02'})
        self.assertIn('多个商品', self.answer('帆布袋卖得怎么样'))

    def test_inventory_never_equates_forecast_to_purchase(self):
        self.report['products'][0]['forecast'] = {'start': '2026-10-01', 'end': '2026-10-07', 'quantity': 35, 'validation_mae': 4}
        answer = self.answer('帆布袋能按预测备货吗？')
        self.assertIn('还缺已确认的库存', answer); self.assertIn('35 件', answer)
        self.assertNotIn('进货量是 35', answer)

    def test_monthly_missing_forecast_and_anomaly(self):
        self.assertIn('月汇总', self.answer('这件商品为什么没有销量预测？', item_id='A01'))
        answer = self.answer('帆布袋有异常吗？')
        self.assertIn('需要每天的销售记录', answer);self.assertIn('才能检查异常日期',answer)
        self.assertNotIn('没有发现',answer)

    def test_zero_baseline_and_missing_amount(self):
        self.report['summary']['previous']['quantity'] = 0
        self.assertNotIn('%', self.answer('本月销量怎么样'))
        self.report['summary']['amount'] = None
        self.assertIn('没有完整的销售金额', self.answer('本月销售额多少'))

    def test_driver_question_not_ranked_by_current_amount(self):
        self.report['change_drivers'] = {'items': [{'name': '马克杯', 'amount_change': -500}, {'name': '帆布袋', 'amount_change': 200}]}
        answer = self.answer('本月销售额变化主要来自哪些商品？')
        self.assertIn('马克杯减少 500', answer);self.assertNotIn('排序', answer)

    def test_no_unrelated_pairing(self):
        answer = self.answer('帆布袋适合和什么搭配？')
        self.assertIn('还没有可推荐', answer);self.assertNotIn('100', answer)

    def test_compact_answer_and_immutable_data(self):
        before = copy.deepcopy(self.report)
        prepared = prepare_answer(self.report, '帆布袋为什么上涨？')
        self.assertLessEqual(len(prepared['facts']), 4)
        self.assertEqual(before,self.report)
        self.assertNotIn('products', prepared['evidence'])

    def test_validator_rejects_changed_number_direction_and_new_advice(self):
        prepared = prepare_answer(self.report, '本月销量怎么样？')
        original = [f['variants'][0] for f in prepared['facts']]
        for changed in ['本月销量为 999 件。', '本月销量下降 25%。', '下个月多进 25%。']:
            with self.assertRaises(ValueError): compose(prepared, [changed] + original[1:], True)
        with self.assertRaises(ValueError): compose(prepared, original[::-1], True)

    def test_model_receives_only_selected_sentences(self):
        prepared = prepare_answer(self.report,'本月销量怎么样？')
        class Response:
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read(self):
                return json.dumps({'choices':[{'message':{'content':json.dumps({f['id']:f['variants'][-1] for f in prepared['facts']},ensure_ascii=False)}}]}).encode()
        with patch('app.sales_assistant.urllib.request.urlopen',return_value=Response()) as call:
            answer = infer_answer(prepared,'本月销量怎么样？','http://localhost/test')
        body = json.loads(call.call_args.args[0].data)
        self.assertLess(len(json.dumps(body,ensure_ascii=False)), 3000)
        self.assertNotIn('帆布袋',json.dumps(body,ensure_ascii=False))
        self.assertTrue(answer['ai_used'])


class AssistantApiTests(unittest.TestCase):
    def setUp(self):
        from test_sales_loading import SalesLoadingTests
        self.base = SalesLoadingTests(); self.base.setUp()
        from app.models import AnalysisRun
        self.report = fixture()
        self.report['context'] = {'run_id':self.base.rid, 'project_id':self.base.pid}
        with self.base.app.state.sessions() as session:
            session.get(AnalysisRun,self.base.rid).result = json.dumps(self.report)
            session.commit()

    def tearDown(self): self.base.tearDown()

    def test_service_failure_returns_specific_program_answer(self):
        with patch('app.sales_assistant.infer_answer',side_effect=TimeoutError):
            response = self.base.client.post(self.base.url+'/ask',json={'question':'本月销量怎么样？'})
        self.assertEqual(response.status_code,200,response.text)
        data=response.json()
        self.assertEqual(data['response_source'],'model_unavailable')
        self.assertFalse(data['ai_used']);self.assertIn('100 件',data['answer'])
        self.assertNotIn('帆布袋',data['answer'])

    def test_clarification_avoids_model_and_scope_is_enforced(self):
        with patch('app.sales_assistant.infer_answer') as model:
            response=self.base.client.post(self.base.url+'/ask',json={'question':'下周进多少？'})
            self.assertEqual(response.json()['response_source'],'computed')
            model.assert_not_called()
        response=self.base.client.post(self.base.url.replace(self.base.pid,self.base.other)+'/ask',json={'question':'销量多少'})
        self.assertEqual(response.status_code,404)


if __name__ == '__main__': unittest.main()
