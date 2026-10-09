"""Reproducible contract tests. Runs against the same modules as the application."""

import csv
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import ValidationError

from app.data_api import digest
from app.import_formats import DataIssue
from app.retail_engine import process_retail
from app.retail_export import render_report
from app.retail_schemas import InventoryInput, RetailInput
from app.sales_mining import anomaly_series, forecast_series

FIELDS = [
    "source_row_id",
    "order_id",
    "item_id",
    "item_name",
    "customer_id",
    "event_time",
    "quantity",
    "unit_price",
    "line_amount",
    "order_amount",
    "currency",
    "record_status",
    "country",
    "category",
]


class SalesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.mapping = {
            "columns": {"item_id": "c0", "quantity": "c1", "event_time": "c2"},
            "record_kind": "daily_summary",
            "quantity_unit": "件",
            "order_boundary": "unavailable",
            "amount_mode": "line_amount",
            "currency_constant": "CNY",
            "timezone": "Asia/Shanghai",
            "time_format": "%Y-%m-%d",
            "status_rule": "all_forward",
            "status_values": {},
        }

    def tearDown(self):
        self.tmp.cleanup()

    def source(self, rows, mapping=None, number=1):
        identity = str(uuid4())
        path = self.root / f"{identity}.parquet"
        normalized = [
            {
                **dict.fromkeys(FIELDS),
                "source_row_id": str(i),
                "currency": "CNY",
                "item_name": "测试商品",
                **row,
            }
            for i, row in enumerate(rows)
        ]
        pq.write_table(
            pa.Table.from_pylist(normalized, schema=pa.schema([(k, pa.string()) for k in FIELDS])),
            path,
        )
        return {
            "version_id": identity,
            "number": number,
            "filename": f"{number}.csv",
            "mapping_revision": 1,
            "mapping": mapping or self.mapping,
            "path": str(path),
            "canonical_sha256": digest(path),
        }

    def run_report(self, sources, **options):
        output = self.root / str(uuid4())
        output.mkdir()
        params = {
            "sources": [],
            "month": "2026-09",
            "merge_mode": "append",
            "duplicates": "keep",
            "complete_coverage": False,
            "coverage_start": None,
            "coverage_end": None,
            "closed_dates": [],
            **options,
        }
        report = process_retail(
            {
                "output": str(output),
                "parameters": params,
                "sources": sources,
                "context": {"run_id": str(uuid4())},
            },
            lambda *_: None,
        )
        return report, output

    def test_daily_without_orders_and_missing_dates(self):
        report, _ = self.run_report(
            [
                self.source(
                    [
                        {
                            "item_id": "A",
                            "event_time": "2026-09-02",
                            "quantity": "3",
                            "line_amount": "0.30",
                        }
                    ]
                )
            ]
        )
        self.assertEqual(report["summary"]["quantity"], 3)
        self.assertEqual(report["summary"]["amount"], 0.3)
        self.assertIsNone(report["summary"]["orders"])
        self.assertIsNone(report["chart"][0]["quantity"])
        self.assertEqual(report["forecast"]["status"], "unavailable")
        self.assertEqual(
            report["quality"]["input_rows"],
            report["quality"]["included_rows"] + report["quality"]["excluded_rows"],
        )

    def test_monthly_no_fake_daily_data(self):
        mapping = {**self.mapping, "record_kind": "monthly_summary", "summary_month": "2026-09"}
        report, _ = self.run_report(
            [self.source([{"item_id": "A", "quantity": "10", "line_amount": "5"}], mapping)]
        )
        self.assertEqual(report["chart"], [])
        self.assertEqual(report["products"][0]["daily"], [])
        self.assertIsNone(report["summary"]["average_order"])

    def test_missing_amount_is_not_zero(self):
        report, _ = self.run_report(
            [self.source([{"item_id": "A", "quantity": "3", "event_time": "2026-09-02"}])]
        )
        self.assertIsNone(report["summary"]["amount"])
        self.assertIsNone(report["products"][0]["amount"])

    def test_overlap_and_explicit_replacement(self):
        old = self.source([{"item_id": "A", "quantity": "3", "event_time": "2026-09-02"}])
        new = self.source([{"item_id": "A", "quantity": "4", "event_time": "2026-09-02"}], number=2)
        with self.assertRaises(DataIssue) as raised:
            self.run_report([old, new])
        self.assertEqual(raised.exception.code, "overlapping_sources")
        report, _ = self.run_report([old, new], merge_mode="replace_overlap")
        self.assertEqual(report["summary"]["quantity"], 4)
        self.assertEqual(report["quality"]["excluded_rows"], 1)

    def test_partial_order_and_missing_order_disable_totals(self):
        mapping = {
            **self.mapping,
            "record_kind": "transactions",
            "order_boundary": "order_id",
            "amount_mode": "order_amount",
        }
        rows = [
            {
                "item_id": "A",
                "quantity": "3",
                "event_time": "2026-09-02",
                "order_id": "X",
                "order_amount": "10",
            },
            {
                "item_id": "B",
                "quantity": "bad",
                "event_time": "2026-09-02",
                "order_id": "X",
                "order_amount": "10",
            },
        ]
        report, _ = self.run_report([self.source(rows, mapping)])
        self.assertIsNone(report["summary"]["amount"])
        self.assertIsNone(report["summary"]["orders"])
        rows[1].update(quantity="2", order_id=None)
        report, _ = self.run_report([self.source(rows, mapping)])
        self.assertIsNone(report["summary"]["amount"])
        self.assertIsNone(report["summary"]["orders"])

    def test_order_amount_once_and_currency_rejection(self):
        mapping = {
            **self.mapping,
            "record_kind": "transactions",
            "order_boundary": "order_id",
            "amount_mode": "order_amount",
        }
        rows = [
            {
                "item_id": key,
                "quantity": "3",
                "event_time": "2026-09-02",
                "order_id": "X",
                "order_amount": "10",
            }
            for key in ["A", "B"]
        ]
        report, _ = self.run_report([self.source(rows, mapping)])
        self.assertEqual(report["summary"]["amount"], 10)
        self.assertEqual(report["summary"]["orders"], 1)
        rows[1].update(currency="GBP", order_id="Y")
        with self.assertRaises(DataIssue):
            self.run_report([self.source(rows, mapping)])

    def test_full_attention_not_capped_and_csv_safe(self):
        rows = [
            {
                "item_id": f"A{i}",
                "item_name": "=unsafe",
                "event_time": f"2026-09-{day:02}",
                "quantity": "1" if day <= 23 else "3",
                "line_amount": "1",
            }
            for i in range(8)
            for day in range(17, 31)
        ]
        report, output = self.run_report(
            [self.source(rows)],
            complete_coverage=True,
            coverage_start="2026-09-01",
            coverage_end="2026-09-30",
        )
        self.assertEqual(len(report["attention_ids"]), 8)
        self.assertEqual(len(report["highlights"]), 5)
        self.assertLessEqual(len(report["actions"]), 3)
        self.assertEqual(len(report["actions"][0]["related_items"]), 8)
        with (output / "sales_products.csv").open(encoding="utf-8-sig") as stream:
            self.assertTrue(next(csv.DictReader(stream))["name"].startswith("'="))
        self.assertIn("全部待关注商品", render_report(report, "<店铺>", True))
        self.assertIn("&lt;店铺&gt;", render_report(report, "<店铺>"))

    def test_frozen_hash_and_closed_day(self):
        source = self.source([{"item_id": "A", "quantity": "3", "event_time": "2026-09-02"}])
        with self.assertRaises(DataIssue):
            self.run_report([source], source_hashes={source["version_id"]: "wrong"})
        with self.assertRaises(DataIssue):
            self.run_report([source], closed_dates=["2026-09-02"])

    def test_invalid_inventory_and_coverage(self):
        with self.assertRaises(ValidationError):
            InventoryInput(
                item_id="A",
                snapshot_date="2026-10-01",
                available=float("nan"),
                incoming=0,
                reserve=0,
            )
        with self.assertRaises(ValidationError):
            RetailInput(
                sources=[{"version_id": str(uuid4()), "mapping_revision": 1}],
                month="2026-09",
                complete_coverage=True,
                idempotency_key="test-test",
            )

    def test_forecast_time_boundaries(self):
        dates = [date(2026, 5, 1) + timedelta(days=i) for i in range(123)]
        series = {str(k): [float(5 + k % 3)] * 123 for k in range(10)}
        result = forecast_series(series, dates)
        self.assertTrue(result["backtests"])
        for row in result["backtests"]:
            self.assertLess(row["training_label_end"], row["origin"])
            self.assertLessEqual(row["target_end"], dates[-1].isoformat())
        self.assertEqual(set(result["cutoffs"]), {r["origin"] for r in result["backtests"]})

    def test_anomaly_injection_not_business_accuracy(self):
        dates = [date(2026, 6, 1) + timedelta(days=i) for i in range(122)]
        rng = np.random.default_rng(42)
        series = {str(k): np.maximum(1, rng.normal(10, 1, len(dates))).tolist() for k in range(12)}
        series["0"][110] = 150
        result = anomaly_series(series, dates, "2026-09")
        self.assertEqual(result["status"], "evaluated")
        self.assertTrue(
            any(r["date"] == dates[110].isoformat() for r in result["items"].get("0", []))
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
