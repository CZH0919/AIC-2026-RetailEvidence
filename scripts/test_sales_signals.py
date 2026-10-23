import copy
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from datetime import date, timedelta

from app.sales_signals import signal_view, unexplained_gaps, comparison
from app.sales_mining_v3 import anomaly_series


def fixture():
    daily = [{'date': f'2026-10-{i:02d}', 'quantity': 2, 'recorded': True} for i in range(1, 32)]
    p = dict(id='a', name='商品A', quantity=62, amount=620, change=0, flags=[], reason='', daily=daily, anomalies=[])
    return dict(month='2026-10', products=[p], summary={'complete_month': True},
                parameters={'complete_coverage': True, 'closed_dates': []},
                highlights=['a'], actions=[], anomaly={'status': 'evaluated'}, chart=[])


class SignalTests(unittest.TestCase):
    def test_new_report_engine_preserves_unknowns_and_explicit_daily_zeros(self):
        from app.retail_engine import process_retail
        for explicit_zeros in [False, True]:
            rows=[dict(day=f'2026-10-{i:02d}', item_id='a', item_name='商品A', quantity=str(2 if i<25 else 0),
                       record_status='forward', source_row_id=str(i), currency=None)
                  for i in range(1, 32 if explicit_zeros else 25)]
            with tempfile.TemporaryDirectory() as tmp:
                source=dict(number=1,version_id='v',filename='daily.csv',mapping_revision=1,canonical_sha256='hash',path=tmp+'/source',
                            mapping={'record_kind':'daily_summary','quantity_unit':'件','amount_mode':'none','timezone':'Asia/Shanghai'})
                params=dict(month='2026-10',sources=[{'version_id':'v','mapping_revision':1}],complete_coverage=True,
                            coverage_start='2026-10-01',coverage_end='2026-10-31',closed_dates=[],merge_mode='append',duplicates='keep')
                job=dict(output=tmp,parameters=params,sources=[source],context={'run_id':'test'})
                forecast={'status':'unavailable','reason':'短历史','predictions':{},'metrics':[]}
                with patch('app.retail_engine.source_rows',return_value=rows), patch('app.retail_engine.digest',return_value='hash'), patch('app.retail_engine.forecast_series',return_value=forecast):
                    report=process_retail(job,lambda *args: None)
                p=report['products'][0]
                self.assertEqual(p['quantity'],48)
                self.assertEqual(p['comparison']['status'],'available' if explicit_zeros else 'missing_records')
                self.assertEqual(p['change'],-1 if explicit_zeros else None)
                self.assertTrue(Path(tmp,'sales_report.json').is_file())

    def test_store_gap_blocks_comparison_without_changing_totals_or_input(self):
        r=fixture()
        for d in r['products'][0]['daily'][-7:]: d.update(quantity=0, recorded=False)
        r['products'][0].update(change=-1, flags=['decline'])
        original=copy.deepcopy(r)
        view=signal_view(r); p=view['products'][0]
        self.assertEqual(r, original)
        self.assertEqual(p['quantity'], 62)
        self.assertIsNone(p['change'])
        self.assertNotIn('decline', p['flags'])
        self.assertEqual(p['comparison']['status'], 'missing_records')
        self.assertTrue(all(d['quantity'] is None for d in p['daily'][-7:]))
        self.assertEqual(signal_view(view), view)

    def test_single_product_zero_with_other_store_sales_is_valid(self):
        r=fixture(); other=copy.deepcopy(r['products'][0]); other['id']='b'
        r['products'].append(other)
        for d in r['products'][0]['daily'][-7:]: d.update(quantity=0, recorded=False)
        p=signal_view(r)['products'][0]
        self.assertEqual(p['change'], -1)
        self.assertEqual(p['comparison']['current_quantity'], 0)
        self.assertEqual(p['comparison']['previous_quantity'], 14)
        self.assertEqual(p['comparison']['current_start'], '2026-10-25')

    def test_known_zero_records_are_not_missing(self):
        r=fixture()
        for d in r['products'][0]['daily'][-7:]: d['quantity']=0
        self.assertEqual(signal_view(r)['products'][0]['change'], -1)

    def test_closed_dates_do_not_become_decline_or_unknown_gaps(self):
        r=fixture()
        for d in r['products'][0]['daily'][-7:]: d.update(quantity=0, recorded=False)
        r['parameters']['closed_dates']=[d['date'] for d in r['products'][0]['daily'][-7:]]
        v=signal_view(r)
        self.assertEqual(v['coverage']['unexplained_dates'], [])
        self.assertEqual(v['products'][0]['comparison']['status'], 'closed')

    def test_monthly_4_vs_1030_and_month_boundary(self):
        r=fixture(); p=r['products'][0]
        p.update(daily=[], quantity=4, change=(4-1030)/1030)
        v=signal_view(r)['products'][0]
        self.assertAlmostEqual(v['comparison']['previous_quantity'], 1030)
        self.assertEqual(v['anomaly_check']['status'], 'monthly_summary')
        self.assertEqual(comparison('2024-03', 1, 2)['previous_end'], '2024-02-29')

    def test_zero_baseline_is_not_percentage(self):
        r=fixture()
        for d in r['products'][0]['daily'][-14:-7]: d['quantity']=0
        p=signal_view(r)['products'][0]
        self.assertIsNone(p['change'])
        self.assertEqual(p['comparison']['status'], 'no_baseline')

    def test_legacy_not_checked_is_not_clear(self):
        r=fixture()
        self.assertEqual(signal_view(r)['products'][0]['anomaly_check']['status'], 'legacy_unknown')
        r['anomaly']['status']='unavailable'
        self.assertEqual(signal_view(r)['products'][0]['anomaly_check']['status'], 'insufficient')

    def test_partial_check_is_explicit(self):
        r=fixture(); p=r['products'][0]
        p['anomaly_check']={'status':'clear','message':'','tested_dates':['2026-10-30','2026-10-31']}
        out=signal_view(r)['products'][0]['anomaly_check']
        self.assertEqual(out['status'], 'clear')
        self.assertEqual(len(out['tested_dates']), 2)

    def test_model_tracks_eligible_products_not_only_flags(self):
        dates=[date(2026,1,1)+timedelta(days=i) for i in range(90)]
        series={str(i): [10+(d.weekday()%2) for d in dates] for i in range(15)}
        series['new']=[float('nan')]*85+[1]*5
        result=anomaly_series(series,dates,'2026-03')
        self.assertEqual(result['status'],'evaluated')
        self.assertEqual(result['checks']['0']['status'],'clear')
        self.assertEqual(len(result['checks']['0']['tested_dates']),31)
        self.assertEqual(result['checks']['new']['status'],'insufficient')
        self.assertEqual(result['checks']['new']['tested_dates'],[])

    def test_short_history_does_not_claim_clear(self):
        dates=[date(2026,10,1)+timedelta(days=i) for i in range(31)]
        r=anomaly_series({'a':[10]*31}, dates, '2026-10')
        self.assertEqual(r['checks']['a']['status'],'insufficient')

    def test_gaps_require_consecutive_store_absence(self):
        self.assertEqual(unexplained_gaps(['2026-10-01','2026-10-04'],'2026-10-01','2026-10-04'),[])
        self.assertEqual(unexplained_gaps(['2026-10-01'],'2026-10-01','2026-10-04'),['2026-10-02','2026-10-03','2026-10-04'])


if __name__ == '__main__': unittest.main()
