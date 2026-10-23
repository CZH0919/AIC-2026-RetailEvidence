"""Mock transport contract checks; distinct from live CPU inference acceptance."""

import io
import json
import unittest
from unittest.mock import patch
from uuid import uuid4

import test_sales_v2 as sales_fixture
import test_task_safety as task_fixture
from fastapi.testclient import TestClient

from app.main import create_app
from app.models import AnalysisRun


class AIContractTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.seed = task_fixture.TaskSafetyTests()
        await self.seed.asyncSetUp()
        self.rid = self.seed.seed(status="succeeded")
        fixture = sales_fixture.SalesTests()
        fixture.setUp()
        try:
            source = fixture.source(
                [{"item_id": "A", "quantity": "3", "line_amount": "12", "event_time": "2026-09-02"}]
            )
            report, _ = fixture.run_report([source])
        finally:
            fixture.tearDown()
        report["context"]["run_id"] = self.rid
        self.sha = report["classification"]["sha256"]
        self.frozen = json.dumps(report, sort_keys=True)
        with self.seed.sessions() as db:
            run = db.get(AnalysisRun, self.rid)
            run.kind = "sales"
            run.result = self.frozen
            db.commit()
        self.client = TestClient(
            create_app(
                database_path=self.seed.root / "test.sqlite3", storage_root=self.seed.storage
            )
        )
        self.client.__enter__()
        from app.models import ProjectOwner

        self.client.headers["X-Requested-With"] = "RetailEvidence"
        registered = self.client.post(
            "/api/auth/register",
            json={"username": "contract_user", "password": "contract-test-password-2026"},
        )
        assert registered.status_code == 201
        with self.client.app.state.sessions() as session:
            session.add(
                ProjectOwner(project_id=self.seed.pid, account_id=registered.json()["user"]["id"])
            )
            session.commit()
        self.path = f"/api/projects/{self.seed.pid}/sales/runs/{self.rid}/ask"

    async def asyncTearDown(self):
        self.client.__exit__(None, None, None)
        with self.seed.sessions() as db:
            self.assertEqual(db.get(AnalysisRun, self.rid).result, self.frozen)
        await self.seed.asyncTearDown()

    def ask(self, question="解释本月销售", **kwargs):
        return self.client.post(self.path, json={"question": question, **kwargs})

    def response(self, answer, references):
        body = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {"answer": answer, "references": references}, ensure_ascii=False
                        )
                    }
                }
            ]
        }
        return io.BytesIO(json.dumps(body).encode())

    async def test_real_numbers_only_program_bound(self):
        with patch(
            "app.retail_api.urllib.request.urlopen",
            return_value=self.response(
                "本月销量为{{销量}}，销售额为{{销售额}}。进货前先核对记录。", ["summary"]
            ),
        ):
            data = self.ask().json()
        self.assertTrue(data["ai_used"])
        self.assertEqual(data["mode"], "model_inference")
        self.assertIn("12", data["answer"])
        self.assertIn("3", data["answer"])
        self.assertEqual(data["evidence_id"], self.rid + ":" + self.sha)

    async def test_unbound_number_rejected(self):
        with patch(
            "app.retail_api.urllib.request.urlopen",
            return_value=self.response("本月销售额为999元，可以直接大量进货。", ["summary"]),
        ):
            data = self.ask().json()
        self.assertFalse(data["ai_used"])
        self.assertEqual(data["mode"], "rejected_model_output")

    async def test_wrong_reference_rejected(self):
        with patch(
            "app.retail_api.urllib.request.urlopen",
            return_value=self.response("销售需要核对记录，谨慎判断下一步。", ["foreign_run"]),
        ):
            data = self.ask().json()
        self.assertEqual(data["mode"], "rejected_model_output")

    async def test_timeout_and_unavailable_modes(self):
        for exception, mode in [
            (TimeoutError("test timeout"), "inference_timeout"),
            (OSError("test unavailable"), "inference_unavailable"),
        ]:
            with patch("app.retail_api.urllib.request.urlopen", side_effect=exception):
                data = self.ask().json()
            self.assertFalse(data["ai_used"])
            self.assertEqual(data["mode"], mode)

    async def test_clarification_and_missing_cost_data(self):
        with patch("app.retail_api.urllib.request.urlopen") as transport:
            self.assertEqual(self.ask("这件商品怎么样？").json()["mode"], "clarification")
            for question in ["利润多少", "是否缺货", "进货多少"]:
                self.assertEqual(self.ask(question).json()["mode"], "data_limit")
            transport.assert_not_called()

    async def test_cross_run_and_unknown_product_rejected(self):
        self.assertEqual(self.ask(item_id="OTHER").status_code, 422)
        self.assertEqual(
            self.client.post(
                self.path.replace(self.rid, str(uuid4())), json={"question": "解释销售"}
            ).status_code,
            404,
        )

    async def test_cause_and_unknown_placeholder_rejected(self):
        for answer in [
            "这说明缺货，所以应该调整经营。",
            "核对记录，以确保进货数量准确。",
            "销售为{{不存在}}，进货前核对记录。",
        ]:
            with patch(
                "app.retail_api.urllib.request.urlopen",
                return_value=self.response(answer, ["summary"]),
            ):
                data = self.ask().json()
            self.assertFalse(data["ai_used"])
            self.assertEqual(data["mode"], "rejected_model_output")


if __name__ == "__main__":
    unittest.main(verbosity=2)
