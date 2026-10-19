import unittest
from copy import deepcopy
from types import SimpleNamespace

from app.sales_actions import build_actions
from app.sales_recommendations import combine, compatible
from test_sales_actions import PARAMS, SUMMARY, product


def inputs():
    products = [product('A', 100, 200, kind='unknown'), product('B', 100, 180, kind='unknown'),
                product('C', 200, 100, kind='unknown')]
    summary = {**SUMMARY, 'amount': sum(p['amount'] for p in products), 'quantity': sum(p['quantity'] for p in products)}
    return {'context': {'project_id': 'shop'}, 'month': '2026-10',
            'sources': [{'version_id': 'data', 'mapping_revision': 1}],
            'parameters': {**PARAMS, 'duplicates': 'keep'}, 'summary': summary, 'products': products,
            'candidates': build_actions(products, parameters=PARAMS, summary=summary, month='2026-10', limit=None)}


def pair():
    return {'id': 'pair', 'kind': 'association', 'report': {
        'context': {'project_id': 'shop', 'data_version_id': 'data', 'mapping_revision': 1},
        'summary': {'publishable': True}, 'analysis': {'min_count': 20},
        'top_rules': [{'antecedents': 'A', 'consequents': 'B', 'denominator': 1000,
                       'n_a': 400, 'n_b': 200, 'n_ab': 140, 'confidence_lower': .30, 'lift': 1.75,
                       'validation_denominator': 200, 'validation_n_a': 80, 'validation_n_b': 60,
                       'validation_n_ab': 50, 'validation_lift': 2.08}]}}


def customers():
    return {'id': 'cluster', 'kind': 'clustering', 'report': {
        'context': {'project_id': 'shop', 'data_version_id': 'data', 'mapping_revision': 1},
        'analysis': {'kind': 'rfm', 'reference_time': '2026-11-01T00:00:00+00:00'},
        'summary': {'publishable': True, 'customers': 100},
        'customer_opportunities': {'version': 'customer-followup-v1', 'customers_analyzed': 100, 'history_start':'2026-09-01', 'through_date':'2026-10-31', 'rule':'individual gaps', 'opportunities':[{'key':'customer-followup-v1','customers':40,'purchase_days_median':5,'usual_gap_median':10,'elapsed_median':22}]},
        'clusters': [{'cluster': 0, 'customers': 60, 'frequency_median': 1, 'recency_median': 80},
                     {'cluster': 1, 'customers': 40, 'frequency_median': 5, 'recency_median': 7}]}}


def quality():
    return {'context': {'project_id': 'shop', 'data_version_id': 'data', 'mapping_revision': 1, 'run_id': 'quality'},
            'scope': {'date_start': '2026-09-01', 'date_end': '2026-10-31'},
            'policy': {'duplicates': 'keep'}, 'summary': {'latest_valid_order_time': '2026-10-31T10:00:00+00:00'}}


class RecommendationRulesTests(unittest.TestCase):
    def test_same_strategy_is_not_repeated_and_valuable_sales_are_retained(self):
        value = inputs(); before = deepcopy(value)
        result = combine(value, [])
        self.assertEqual({a['item_id'] for a in result['actions']}, {'A', 'C'})
        self.assertEqual(value, before)
        self.assertEqual(result, combine(value, []))

    def test_customer_and_pairing_compete_without_forcing_three_categories(self):
        result = combine(inputs(), [pair(), customers()])
        self.assertEqual(len(result['actions']), 3)
        self.assertEqual(len({a['strategy'] for a in result['actions']}), 3)
        self.assertTrue(any(a.get('source_run_id') for a in result['actions']))
        self.assertEqual(combine(inputs(), [pair(), customers()]), combine(inputs(), [customers(), pair()]))
        data = inputs(); data['candidates'] = []
        result = combine(data, [pair(), customers()])
        self.assertEqual({a['category'] for a in result['actions']}, {'客户回访', '商品搭配'})

    def test_pairing_requires_repeated_validation_and_popularity_adjustment(self):
        data = inputs(); data['candidates'] = []
        for key, value in [('validation_n_ab', 2), ('validation_lift', 1), ('confidence_lower', .1), ('lift', 1)]:
            analysis = pair(); analysis['report']['top_rules'][0][key] = value
            self.assertEqual(combine(data, [analysis])['actions'], [])
        analysis = pair(); analysis['report']['top_rules'][0]['antecedents'] = 'different-file-item'
        self.assertEqual(combine(data, [analysis])['actions'], [])

    def test_pairing_reciprocal_rules_yield_one_arrangement(self):
        analysis = pair(); rule = deepcopy(analysis['report']['top_rules'][0])
        rule.update(antecedents='B', consequents='A', n_a=200, n_b=400,
                    confidence_lower=.6, validation_n_a=60, validation_n_b=80)
        analysis['report']['top_rules'].append(rule)
        data = inputs(); data['candidates'] = []
        result = combine(data, [analysis])
        self.assertEqual(len(result['actions']), 1)
        analysis['report']['top_rules'].reverse()
        self.assertEqual(result, combine(data, [analysis]))

    def test_weak_customer_distinction_does_not_produce_generic_marketing(self):
        analysis = customers(); analysis['report'].pop('customer_opportunities')
        data = inputs(); data['candidates'] = []
        self.assertEqual(combine(data, [analysis])['actions'], [])
        result = combine(data, [customers()])['actions'][0]
        self.assertEqual(result['target']['opportunity'], 'customer-followup-v1')
        self.assertNotIn('新品', result['text'])

    def test_compatible_rejects_other_sources_future_dates_and_different_scopes(self):
        data, report, q = inputs(), customers()['report'], quality()
        row = SimpleNamespace(quality_run_id='quality')
        self.assertTrue(compatible(data, row, report, q))
        for key, value in [('data_version_id', 'other'), ('mapping_revision', 2), ('project_id', 'other')]:
            changed = deepcopy(report); changed['context'][key] = value
            self.assertFalse(compatible(data, row, changed, q))
        for key, value in [('date_end', '2026-12-01'), ('date_start', '2026-08-01'), ('countries', ['UK']), ('item_ids', ['A'])]:
            changed = deepcopy(q); changed['scope'][key] = value
            self.assertFalse(compatible(data, row, report, changed))
        changed = deepcopy(report); changed['analysis']['reference_time'] = '2026-12-10'
        self.assertFalse(compatible(data, row, changed, q))
        changed = deepcopy(q); changed['summary']['latest_valid_order_time'] = '2026-11-03'
        self.assertFalse(compatible(data, row, report, changed))
        changed = deepcopy(q); changed['policy']['duplicates'] = 'drop_exact'
        self.assertFalse(compatible(data, row, report, changed))
        changed = deepcopy(report); changed['summary']['publishable'] = False
        self.assertFalse(compatible(data, row, changed, q))

    def test_no_supplementary_results_means_no_fabricated_categories_or_uplift(self):
        data = inputs(); data['candidates'] = []
        self.assertEqual(combine(data, [])['actions'], [])
        for action in combine(inputs(), [pair(), customers()])['actions']:
            self.assertNotIn('增幅', action['reason'])
            self.assertNotIn('预计增加', action['text'])


if __name__ == '__main__':
    unittest.main()
