"""Business regressions: material demand, complete evidence and stable identities."""
import unittest
from copy import deepcopy
from datetime import date, timedelta

from app.sales_actions import ACTION_VERSION, action_view, build_actions


PARAMS = {"complete_coverage": True, "coverage_start": "2026-09-01", "coverage_end": "2026-10-31"}
SUMMARY = {"complete_month": True, "currency": "CNY"}


def product(key, previous=100, current=200, price=10, kind="physical"):
    return {"id": key, "name": key, "quantity": current, "amount": current * price,
            "change": current / previous - 1 if previous else None, "flags": ["growth"],
            "daily": [], "anomalies": [], "item_type": {"kind": kind},
            "contribution": {"period": "common", "previous_quantity": previous,
                             "current_quantity": current, "previous_amount": previous * price}}


def daily_product(key, weeks):
    p = product(key, current=sum(weeks))
    start = date(2026, 10, 4)
    p["daily"] = [{"date": (start + timedelta(days=i)).isoformat(), "quantity": weeks[i // 7] / 7}
                  for i in range(28)]
    return p


def actions(products, **kwargs):
    return build_actions(products, parameters=kwargs.get("parameters", PARAMS),
                         summary=kwargs.get("summary", SUMMARY), month="2026-10")


class SalesActionRulesTests(unittest.TestCase):
    def test_material_products_win_over_tiny_percent_outlier(self):
        ps = [product("large", 1000, 1500), product("middle", 800, 1200),
              product("third", 600, 900), product("fourth", 500, 750),
              product("tiny-9900-percent", 1, 100, price=0.01)]
        result = actions(ps)
        self.assertEqual([a["item_id"] for a in result], ["large", "middle", "third"])
        self.assertEqual(result, actions(list(reversed(ps))))
        self.assertTrue(all(a["count"] == 1 and a["related_items"] == [a["item_id"]] for a in result))

    def test_non_merchandise_and_conflicting_types_never_occupy_actions(self):
        ps = [product("POSTAGE", 10, 10000, kind="unknown"),
              product("Manual", 10, 10000, kind="unknown"),
              product("fee", 10, 10000, kind="fee_service"),
              product("account", 10, 10000, kind="accounting"), product("goods")]
        conflict = product("conflict", 10, 10000, kind="unknown")
        conflict["item_type"]["source"] = "conflicting_types"
        self.assertEqual([a["item_id"] for a in actions(ps + [conflict])], ["goods"])

    def test_unknown_items_get_sales_actions_without_inventory_assumptions(self):
        result = actions([product("ordinary", kind="unknown")])[0]
        self.assertIn("展示", result["title"])
        self.assertNotIn("采购", result["text"])
        self.assertNotIn("确认类型", result["title"])
        self.assertIn("采购", actions([product("confirmed")])[0]["text"])

    def test_sustained_weekly_growth_has_four_actual_week_totals(self):
        result = actions([daily_product("steady", [70, 140, 210, 280])])
        self.assertEqual(result[0]["signal"], "growth")
        self.assertEqual(result[0]["selection"]["quantities"], [70, 140, 210, 280])

    def test_single_last_week_jump_cannot_be_called_sustained_growth(self):
        self.assertEqual(actions([daily_product("jump", [70, 70, 70, 700])]), [])

    def test_abnormal_days_cannot_manufacture_sustained_growth(self):
        p = daily_product("false-trend", [70, 70, 70, 70])
        for week, added in enumerate([0, 10, 20, 30]):
            day = p["daily"][week * 7]
            day["quantity"] += added
            if added:
                p["anomalies"].append({"date": day["date"], "actual": day["quantity"], "reference": 10})
        self.assertEqual(actions([p]), [])

    def test_isolated_large_order_is_separate_from_replenishment_growth(self):
        p = daily_product("one-order", [70, 70, 70, 270])
        p["daily"] = [{**d, "quantity": 10} for d in p["daily"]]
        p["daily"][-1]["quantity"] = 210
        p["anomalies"] = [{"date": p["daily"][-1]["date"], "actual": 210, "reference": 10}]
        result = actions([p])
        self.assertEqual(result[0]["signal"], "spike")
        self.assertIn("平时销量", result[0]["text"])

    def test_incomplete_missing_and_closed_dates_do_not_generate_trends(self):
        p = daily_product("steady", [70, 140, 210, 280])
        self.assertEqual(actions([p], summary={"complete_month": False}), [])
        self.assertEqual(actions([p], parameters={**PARAMS, "complete_coverage": False}), [])
        for key in ["missing_dates", "closed_dates"]:
            self.assertEqual(actions([p], parameters={**PARAMS, key: ["2026-10-15"]}), [])
        p["daily"][10]["quantity"] = None
        self.assertEqual(actions([p]), [])

    def test_price_only_change_and_new_products_are_not_demand_growth(self):
        p = product("price", 100, 100)
        p["amount"] = 10000
        p["contribution"]["previous_amount"] = 100
        self.assertEqual(actions([p]), [])
        p = product("new", previous=0)
        p["contribution"]["period"] = "only_current"
        self.assertEqual(actions([p]), [])

    def test_old_monthly_percent_and_no_money_are_supported(self):
        p = product("old", kind="unknown")
        p.pop("contribution")
        p["amount"] = None
        result = actions([p])[0]
        self.assertEqual(result["selection"]["quantities"], [100, 200])
        self.assertEqual(result["priority_basis"], "quantity")
        self.assertNotIn("销售额", result["reason"])

    def test_empty_is_better_than_filling_three_weak_actions(self):
        self.assertEqual(len(actions([product("one")])), 1)
        self.assertEqual(actions([product("weak", 100, 110)]), [])
        self.assertEqual(actions([product("one")], parameters={**PARAMS, "coverage_start": "2026-10-01"}), [])

    def test_old_action_ids_and_reports_are_not_mutated_or_reused(self):
        report = {"month": "2026-10", "summary": SUMMARY, "parameters": PARAMS,
                  "products": [product("one")], "actions": [{"id": "review:physical:growth"}]}
        before = deepcopy(report)
        view = action_view(report)
        self.assertEqual(report, before)
        self.assertEqual(view["previous_actions"], report["actions"])
        self.assertTrue(view["actions"][0]["id"].startswith(ACTION_VERSION + ":"))
        self.assertEqual(view["actions"], action_view(report)["actions"])
        self.assertIs(action_view(view), view)


if __name__ == "__main__":
    unittest.main()
