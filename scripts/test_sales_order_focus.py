import copy
import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pyarrow as pa
import pyarrow.parquet as pq
from app.sales_order_focus import order_focus


class OrderFocusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.output = self.root/'runs/project/run'
        self.output.mkdir(parents=True)
        self.folder = self.root/'datasets/projects/project/source/mappings/1'
        self.folder.mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def fixture(self, quantities, orders=None, excluded=(), boundary='order_id', actual=None):
        orders = orders or [str(i) for i in range(len(quantities))]
        rows = [dict(source_row_id=str(i), quantity=str(q), order_id=o) for i,(q,o) in enumerate(zip(quantities,orders))]
        pq.write_table(pa.Table.from_pylist(rows), self.folder/'canonical.parquet')
        (self.folder/'mapping.json').write_text(json.dumps({'config':{'record_kind':'transactions','order_boundary':boundary}}))
        with (self.output/'sales_row_audit.csv').open('w',newline='',encoding='utf-8-sig') as stream:
            writer=csv.DictWriter(stream,fieldnames=['version_id','source_row_id','item_id','date','reason'])
            writer.writeheader()
            for i in range(len(rows)):
                writer.writerow(dict(version_id='source',source_row_id=str(i),item_id='p',date='2026-10-20',reason='returned' if i in excluded else 'included'))
        actual = sum(q for i,q in enumerate(quantities) if i not in excluded) if actual is None else actual
        with (self.folder/'canonical.parquet').open('rb') as stream:
            digest=hashlib.file_digest(stream,'sha256').hexdigest()
        return {'products':[{'id':'p','quantity':actual,'focus_reason':'original','focus':{'category':'anomaly','label':'单日销量明显变化','reason':'original','evidence':{'date':'2026-10-20','actual':actual,'reference':1.5}}}],
                'sources':[{'version_id':'source','mapping_revision':1,'canonical_sha256':digest}]}

    def focus(self, report):
        return order_focus(report,self.output)['products'][0]['focus']

    def test_single_order_and_immutable_report(self):
        r=self.fixture([2400,100,147]);before=copy.deepcopy(r)
        f=self.focus(r)
        self.assertEqual(f['label'],'大批量订单带动')
        self.assertIn('其中一笔订单购买 2,400',f['reason'])
        self.assertNotIn('1.5',f['reason'])
        self.assertEqual(r,before)
        self.assertIn('其他日期',f['note'])

    def test_two_distinct_equal_orders(self):
        f=self.focus(self.fixture([720,720,6]))
        self.assertIn('两笔订单各购买 720',f['reason'])

    def test_order_is_aggregated_across_lines(self):
        f=self.focus(self.fixture([720,720,6],orders=['same','same','other']))
        self.assertIn('一笔订单购买 1,440',f['reason'])

    def test_excluded_rows_never_become_bulk_evidence(self):
        f=self.focus(self.fixture([2400,10,10,10],excluded=[0]))
        self.assertEqual(f['label'],'单日销量明显变化')

    def test_missing_order_or_unknown_boundary_does_not_claim_orders(self):
        for orders,boundary in [(['','two'],'order_id'),(['one','two'],'unavailable')]:
            with self.subTest(orders=orders,boundary=boundary):
                f=self.focus(self.fixture([2400,6],orders=orders,boundary=boundary))
                self.assertEqual(f['label'],'单日销量明显变化')
                (self.output/'.sales-focus-orders-v1.json').unlink()

    def test_unreconciled_daily_total_does_not_claim_orders(self):
        f=self.focus(self.fixture([720,720,6],actual=2000))
        self.assertEqual(f['label'],'单日销量明显变化')

    def test_ordinary_distributed_sales_not_bulk(self):
        f=self.focus(self.fixture([10,10,10,10]))
        self.assertEqual(f['label'],'单日销量明显变化')

    def test_cached_reads_do_not_reopen_canonical_data(self):
        r=self.fixture([2400,6]);first=order_focus(r,self.output)
        with patch('app.sales_order_focus._read_orders',side_effect=AssertionError('must use cache')):
            self.assertEqual(order_focus(r,self.output),first)

    def test_changed_source_does_not_create_bulk_claim(self):
        r=self.fixture([2400,6]);r['sources'][0]['canonical_sha256']='changed'
        self.assertEqual(self.focus(r)['label'],'单日销量明显变化')


if __name__=='__main__':unittest.main()
