import csv
import tempfile
import unittest
from pathlib import Path
import pandas as pd
from app.customer_opportunities import build


class CustomerEvidenceTests(unittest.TestCase):
    def rows(self, customer, days):
        return [dict(customer_id=customer,order_id=f'{customer}-{i}',event_time='2026-10-'+str(d).zfill(2)+'T12:00:00Z') for i,d in enumerate(days)]

    def run_build(self, extra=(), publishable=True):
        rows=[]
        for i in range(20): rows += self.rows(str(i), [1,5,9,13])
        rows += list(extra)
        with tempfile.TemporaryDirectory() as tmp:
            result=build(pd.DataFrame(rows), {'analysis':{'reference_time':'2026-11-01T00:00:00Z'},'summary':{'publishable':publishable,'customers':100}},Path(tmp))
            with (Path(tmp)/'customer_followup.csv').open() as f: targets=list(csv.DictReader(f))
        return result,targets

    def test_actual_customer_history_not_cluster_averages(self):
        result,targets=self.run_build(self.rows('one-time',[1])+self.rows('recent',[15,19,23,27])+self.rows('irregular',[1,2,3,13]))
        self.assertEqual(result['opportunities'][0]['customers'],20)
        self.assertEqual(len(targets),20)
        self.assertEqual(targets[0]['usual_gap_days'],'4.0')
        self.assertEqual(targets[0]['days_since_purchase'],'19')
        self.assertTrue(all(float(r['days_since_purchase'])>float(r['threshold_days']) for r in targets))

    def test_same_day_orders_do_not_create_repeat_purchase_history(self):
        _,targets=self.run_build(self.rows('same-day',[1,1,1,1]))
        self.assertNotIn('same-day',{r['customer_id'] for r in targets})

    def test_future_purchases_do_not_change_historical_list(self):
        baseline=self.run_build()
        future=[dict(customer_id='0',order_id='future',event_time='2026-11-02T12:00:00Z')]
        self.assertEqual(baseline,self.run_build(future))

    def test_unreliable_clustering_never_generates_actions(self):
        result,targets=self.run_build(publishable=False)
        self.assertEqual(result['opportunities'],[])
        self.assertEqual(targets,[])

    def test_small_list_is_not_published(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=build(pd.DataFrame(self.rows('only',[1,5,9,13])),{'analysis':{'reference_time':'2026-11-01T00:00:00Z'},'summary':{'publishable':True,'customers':50}},Path(tmp))
            self.assertEqual(result['opportunities'],[])

if __name__=='__main__': unittest.main()
