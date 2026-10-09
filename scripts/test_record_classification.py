"""Classification boundaries on hand-computable fixtures, never claimed merchant evidence."""

import csv
import unittest
from uuid import uuid4

import test_sales_v2 as fixture
from pydantic import ValidationError

from app.data_api import digest
from app.import_formats import DataIssue
from app.retail_schemas import RetailInput


class ClassificationTests(fixture.SalesTests):
    def sample(self, **changes):
        return {
            "item_id": "POSTER",
            "item_name": "POSTCARD SET",
            "quantity": "3",
            "event_time": "2026-09-02",
            "line_amount": "12",
            **changes,
        }

    def policy(self, source, rules=None, **changes):
        return {
            "version_id": source["version_id"],
            "mapping_revision": 1,
            "default_kind": "physical_product",
            "default_amount_treatment": "include",
            "confirmed": True,
            "rules": rules or [],
            **changes,
        }

    def rule(self, item, kind, treatment="include"):
        return {
            "match_by": "item_id",
            "value": item,
            "kind": kind,
            "amount_treatment": treatment,
            "basis": "测试已确认口径",
        }

    def test_shipping_excluded_from_products_not_revenue(self):
        s = self.source(
            [
                self.sample(),
                self.sample(item_id="POST", item_name="POSTAGE", quantity="20", line_amount="5"),
            ]
        )
        r, out = self.run_report(
            [s], classifications=[self.policy(s, [self.rule("POST", "shipping_service")])]
        )
        self.assertEqual([p["id"] for p in r["products"]], ["POSTER"])
        self.assertEqual(r["summary"]["quantity"], 3)
        self.assertEqual(r["summary"]["amount"], 17)
        self.assertNotIn("POST", [a["item_id"] for a in r["actions"]])
        self.assertNotIn("POST", [p["id"] for p in r["products"] if p["forecast"]])
        self.assertEqual(sum(x["amount"] for x in r["classification"]["financial_breakdown"]), 17)
        with (out / "sales_row_audit.csv").open(encoding="utf-8-sig") as stream:
            self.assertEqual(len(list(csv.DictReader(stream))), 2)

    def test_post_in_normal_product_name_survives(self):
        s = self.source([self.sample(item_name="POSTAGE STAMP ALBUM")])
        r, _ = self.run_report([s])
        self.assertEqual(r["products"][0]["id"], "POSTER")

    def test_manual_unknown_semantics_not_guessed(self):
        s = self.source(
            [self.sample(), self.sample(item_id="M", item_name="Manual", line_amount="7")]
        )
        r, _ = self.run_report(
            [s], classifications=[self.policy(s, [self.rule("M", "manual_adjustment", "pending")])]
        )
        self.assertIsNone(r["summary"]["amount"])
        self.assertEqual(r["summary"]["quantity"], 3)
        self.assertEqual(
            r["classification"]["financial_breakdown"][0]["amount_treatment"], "pending"
        )

    def test_explicit_fee_exclusion_reconciles(self):
        s = self.source([self.sample(), self.sample(item_id="POST", line_amount="5")])
        r, _ = self.run_report(
            [s],
            classifications=[self.policy(s, [self.rule("POST", "shipping_service", "exclude")])],
        )
        rows = r["classification"]["financial_breakdown"]
        self.assertEqual(r["summary"]["amount"], 12)
        self.assertEqual(sum(x["amount"] for x in rows), 17)

    def test_no_confirmation_no_restock(self):
        s = self.source([self.sample()])
        r, _ = self.run_report([s], classifications=[])
        self.assertEqual(r["summary"]["products"], 0)
        self.assertEqual(r["actions"], [])
        self.assertEqual(r["classification"]["pending_product_rows"], 1)
        self.assertIsNone(r["summary"]["amount"])

    def test_refund_and_cancel_not_positive_revenue(self):
        m = {
            **self.mapping,
            "status_rule": "status_column",
            "status_values": {"S": "forward", "R": "return", "C": "cancelled"},
        }
        s = self.source(
            [
                self.sample(record_status="S"),
                self.sample(record_status="R", quantity="-2", line_amount="-8"),
                self.sample(record_status="C", line_amount="50"),
            ],
            m,
        )
        r, _ = self.run_report([s])
        self.assertEqual(r["summary"]["amount"], 12)
        self.assertEqual(r["summary"]["refund_amount"], 8)
        self.assertEqual(r["quality"]["excluded_rows"], 2)

    def test_mixed_order_total_never_allocated_or_duplicated(self):
        m = {
            **self.mapping,
            "record_kind": "transactions",
            "order_boundary": "order_id",
            "amount_mode": "order_amount",
        }
        s = self.source(
            [
                self.sample(order_id="X", order_amount="17"),
                self.sample(item_id="POST", order_id="X", order_amount="17"),
            ],
            m,
        )
        r, _ = self.run_report(
            [s], classifications=[self.policy(s, [self.rule("POST", "shipping_service")])]
        )
        self.assertEqual(r["summary"]["amount"], 17)
        self.assertEqual(r["summary"]["quantity"], 3)
        r, _ = self.run_report(
            [s],
            classifications=[self.policy(s, [self.rule("POST", "shipping_service", "exclude")])],
        )
        self.assertIsNone(r["summary"]["amount"])
        self.assertTrue(
            all(x["amount"] is None for x in r["classification"]["financial_breakdown"])
        )

    def test_version_scope_rejects_other_source(self):
        s = self.source([self.sample()])
        wrong = self.policy(s)
        wrong["version_id"] = str(uuid4())
        with self.assertRaises(DataIssue):
            self.run_report([s], classifications=[wrong])
        with self.assertRaises(ValidationError):
            RetailInput(
                sources=[{"version_id": s["version_id"], "mapping_revision": 1}],
                classifications=[wrong],
                month="2026-09",
                idempotency_key="boundary-test",
            )
        wrong = self.policy(s)
        wrong["mapping_revision"] = 2
        with self.assertRaises(DataIssue):
            self.run_report([s], classifications=[wrong])

    def test_changed_policy_new_output_old_report_immutable(self):
        s = self.source([self.sample(item_id="POST")])
        policy = self.policy(s)
        first, out = self.run_report([s], classifications=[policy])
        before = digest(out / "sales_report.json")
        second, _ = self.run_report(
            [s], classifications=[self.policy(s, [self.rule("POST", "shipping_service")])]
        )
        self.assertEqual(digest(out / "sales_report.json"), before)
        self.assertNotEqual(first["classification"]["sha256"], second["classification"]["sha256"])
        self.assertEqual(second["summary"]["products"], 0)
        self.assertEqual(policy["rules"], [])

    def test_audit_csv_formula_protection_preserves_identity(self):
        s = self.source([self.sample(item_id="=CMD()", source_row_id="@row")])
        _, out = self.run_report([s])
        with (out / "sales_row_audit.csv").open(encoding="utf-8-sig") as stream:
            row = next(csv.DictReader(stream))
        self.assertEqual(row["item_id"], "'=CMD()")
        self.assertEqual(row["source_row_id"], "'@row")

    def test_duplicate_rule_rejected(self):
        s = self.source([self.sample()])
        r = self.rule("POSTER", "physical_product")
        with self.assertRaises(ValidationError):
            RetailInput(
                sources=[{"version_id": s["version_id"], "mapping_revision": 1}],
                classifications=[self.policy(s, [r, r])],
                month="2026-09",
                idempotency_key="boundary-test",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
