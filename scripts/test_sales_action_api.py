"""Save new actions alongside old notes without rewriting historical reports."""
import json
from copy import deepcopy

from app.models import AnalysisRun
from test_sales_loading import SalesLoadingTests
from test_sales_actions import PARAMS, SUMMARY, product


class SalesActionApiTests(SalesLoadingTests):
    def test_new_and_legacy_notes_remain_separate_and_report_is_immutable(self):
        report = deepcopy(self.report)
        report.update(month="2026-10", parameters=PARAMS, summary={**SUMMARY, "products": 1},
                      products=[product("new-winner")], highlights=[],
                      actions=[{"id": "review:physical:growth", "title": "以前的整组建议"}])
        with self.app.state.sessions() as s:
            s.get(AnalysisRun, self.rid).result = json.dumps(report)
            s.commit()
        payload = {"status": "done", "note": "旧备注", "expected_revision": 0}
        old_url = self.url + "/actions/review:physical:growth"
        self.assertEqual(self.client.put(old_url, json=payload).status_code, 200)
        view = self.client.get(self.url + "/workspace").json()["result"]
        new_id = view["actions"][0]["id"]
        self.assertEqual(view["products"][0]["id"], "new-winner")
        self.assertEqual(view["previous_actions"], report["actions"])
        new_url = self.url + "/actions/" + new_id
        self.assertEqual(self.client.put(new_url, json={**payload, "note": "新备注"}).status_code, 200)
        records = self.client.get(self.url + "/records").json()["items"]
        self.assertEqual(records["action:review:physical:growth"]["value"]["note"], "旧备注")
        self.assertEqual(records["action:" + new_id]["value"]["note"], "新备注")
        self.assertEqual(self.client.put(new_url, json=payload).status_code, 409)
        self.assertEqual(self.client.put(new_url.replace(self.pid, self.other), json=payload).status_code, 404)
        self.assertEqual(self.client.put(self.url + "/actions/missing", json=payload).status_code, 404)
        with self.app.state.sessions() as s:
            self.assertEqual(json.loads(s.get(AnalysisRun, self.rid).result), report)
