import copy
import unittest
from datetime import date, timedelta

from app.sales_focus import focus_view, merchandise, select_focus


def product(key, amount=1000, quantity=100, **extra):
    return dict(id=key, name=key, amount=amount, quantity=quantity, daily=[], anomalies=[],
                item_type={'kind':'unknown'}, **extra)


def weekly(key, weeks):
    p=product(key, amount=sum(weeks)*10, quantity=sum(weeks))
    p['daily']=[{'date':(date(2026,10,4)+timedelta(days=i)).isoformat(), 'quantity': weeks[i//7]/7}
                for i in range(28)]
    return p


def report(products):
    return {'products':products, 'summary':{'unit':'件','complete_month':True},
            'parameters':{'complete_coverage':True},'highlights':['old']}


class FocusTests(unittest.TestCase):
    def test_huge_fees_cannot_displace_merchandise(self):
        goods=[product('商品'+str(i),10000-i*1000) for i in range(7)]
        for label in ['Manual','POSTAGE','BANK CHARGES','手续费']:
            goods.append(product(label,10**8))
        p=product('ordinary-id',10**9);p['item_type']={'kind':'accounting'};goods.append(p)
        v=focus_view(report(goods))
        self.assertEqual(len(v['highlights']),5)
        self.assertTrue(all(i.startswith('商品') for i in v['highlights']))
        self.assertEqual(len(v['products']),len(goods))
        first=next(p for p in v['products'] if p['id']==v['highlights'][0])
        self.assertEqual(first['focus']['evidence']['total'],sum(10000-i*1000 for i in range(7)))

    def test_exact_names_not_substrings_or_arbitrary_short_codes(self):
        self.assertTrue(merchandise(product('M',name_unused=True)))
        self.assertTrue(merchandise(product('POSTAGE STAMP SET')))
        self.assertTrue(merchandise(product('MANUAL COFFEE GRINDER')))

    def test_tiny_100_percent_gain_not_selected(self):
        tiny=product('tiny',2,2,comparison={'kind':'month','status':'available','previous_quantity':1,'current_quantity':2,'previous_start':'2026-09-01','current_end':'2026-10-31'})
        v=focus_view(report([product('main',10000),tiny]))
        self.assertEqual(v['highlights'],['main'])

    def test_does_not_force_five_or_categories(self):
        v=focus_view(report([product('one'),product('two',.01)]))
        self.assertEqual(v['highlights'],['one'])
        self.assertEqual(v['products'][0]['focus']['category'],'leader')

    def test_sustained_change_with_concrete_week_counts(self):
        falling=weekly('falling',[140,105,70,35])
        v=focus_view(report([product('main',20000),falling]))
        p=next(p for p in v['products'] if p['id']=='falling')
        self.assertEqual(p['focus']['category'],'decline')
        self.assertEqual(p['focus']['evidence']['quantities'],[140,105,70,35])
        self.assertIn('140 → 105 → 70 → 35',p['focus_reason'])

    def test_unknown_days_do_not_become_trend(self):
        p=weekly('incomplete',[140,105,70,35]);p['daily'][20]['quantity']=None
        _, selected=select_focus([product('main',20000),p],report([])['summary'],report([])['parameters'])
        self.assertNotEqual(selected.get('incomplete',{}).get('category'),'decline')

    def test_significant_anomaly_explains_date_and_month_share(self):
        p=product('spike',5000,500)
        p['anomalies']=[{'date':'2026-10-20','actual':300,'reference':40}]
        p['anomaly_check']={'reference_label':'此前相同星期的通常销量'}
        v=focus_view(report([product('main',20000),p]))
        selected=next(p for p in v['products'] if p['id']=='spike')
        self.assertEqual(selected['focus']['category'],'anomaly')
        self.assertIn('10-20 售出 300', selected['focus_reason'])
        self.assertIn('占本月销量 60.0%', selected['focus_reason'])
        self.assertNotIn('40', selected['focus_reason'])

    def test_clear_month_comparison_does_not_claim_continuous_trend(self):
        p=product('fall',1000,100,comparison={'status':'available','previous_quantity':300,'current_quantity':100,'previous_start':'2026-09-01','current_end':'2026-10-31'})
        v=focus_view(report([product('main',20000),p]))
        selected=next(p for p in v['products'] if p['id']=='fall')
        self.assertEqual(selected['focus']['label'],'本月销量下降')
        self.assertIn('少卖 200',selected['focus_reason'])

    def test_unknown_units_do_not_mix_quantities(self):
        a,b=product('kilograms',None,100000),product('boxes',None,10)
        r=report([a,b]);r['summary']['unit']='原始商品单位'
        self.assertEqual(focus_view(r)['highlights'],[])

    def test_same_explicit_unit_can_use_quantity(self):
        v=focus_view(report([product('one',None,20),product('two',None,10)]))
        self.assertEqual(v['highlights'][0],'one')
        self.assertIn('20 件',v['products'][0]['focus_reason'])

    def test_deterministic_unique_and_immutable(self):
        r=report([product(str(i),1000) for i in reversed(range(10))]);old=copy.deepcopy(r)
        v=focus_view(r)
        self.assertEqual(r,old)
        self.assertEqual(len(set(v['highlights'])),len(v['highlights']))
        self.assertEqual(v['highlights'],focus_view(report(list(reversed(r['products']))))['highlights'])
        self.assertEqual(focus_view(v),v)

    def test_steady_top_seller_without_flags_is_included(self):
        r=report([product('steady',100000),product('small',100)])
        v=focus_view(r)
        self.assertEqual(v['highlights'],['steady'])
        self.assertEqual(v['products'][0]['focus']['label'],'主要销售商品')


if __name__=='__main__': unittest.main()
