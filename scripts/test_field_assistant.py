"""Preview-scoped mock transport contracts; live CPU/browser proof is separate."""

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.database import create_database
from app.main import create_app
from app.models import ImportDraft, Project


class FieldAssistantTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.engine, self.sessions = create_database(self.root / "test.sqlite3")
        self.did, self.token = str(uuid4()), str(uuid4())
        self.preview = {
            "columns": [
                {"key": "c0", "name": "item_id", "examples": ["SECRET_SAMPLE_NOT_SENT"]},
                {"key": "c1", "name": "quantity", "examples": ["987654321"]},
            ],
            "suggestions": {"columns": {"item_id": "c0", "quantity": "c1"}, "warnings": []},
        }
        with self.sessions() as db:
            project = Project(name="Field fixture", name_key="field fixture")
            db.add(project)
            db.flush()
            self.pid = project.id
            db.add(
                ImportDraft(
                    id=self.did,
                    project_id=self.pid,
                    filename="fixture.csv",
                    suffix=".csv",
                    sha256="a" * 64,
                    bytes=32,
                    inspection="{}",
                    preview=json.dumps(self.preview),
                    preview_token=self.token,
                )
            )
            db.commit()
        self.client = TestClient(
            create_app(database_path=self.root / "test.sqlite3", storage_root=self.root / "storage")
        )
        self.client.__enter__()
        self.path = f"/api/projects/{self.pid}/imports/{self.did}/explain-fields"

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.engine.dispose()
        self.tmp.cleanup()

    def response(self, **changes):
        parsed = {
            "answer": "商品标识用于区分商品，数量表示销售数量；单位和金额口径仍需人工确认。",
            "references": ["item_id", "quantity"],
            **changes,
        }
        return io.BytesIO(
            json.dumps(
                {"choices": [{"message": {"content": json.dumps(parsed, ensure_ascii=False)}}]}
            ).encode()
        )

    def ask(self, **changes):
        return self.client.post(
            self.path, json={"preview_token": self.token, "question": "解释字段含义", **changes}
        )

    def test_explains_without_saving_or_sending_examples(self):
        with patch(
            "app.field_assistant.urllib.request.urlopen", return_value=self.response()
        ) as model:
            result = self.ask().json()
        self.assertTrue(result["ai_used"])
        self.assertEqual(result["evidence_id"], self.did + ":" + self.token)
        self.assertEqual(result["proposal"]["columns"], self.preview["suggestions"]["columns"])
        sent = model.call_args.args[0].data.decode()
        self.assertNotIn("SECRET_SAMPLE_NOT_SENT", sent)
        self.assertNotIn("987654321", sent)
        with self.sessions() as db:
            draft = db.get(ImportDraft, self.did)
            self.assertEqual(json.loads(draft.preview), self.preview)
            self.assertIsNone(draft.mapping_draft)
            self.assertIsNone(draft.finalized_version_id)

    def test_scope_stale_preview_and_finalized_are_rejected_before_model(self):
        with patch("app.field_assistant.urllib.request.urlopen") as model:
            self.assertEqual(
                self.client.post(
                    self.path.replace(self.pid, str(uuid4())),
                    json={"preview_token": self.token, "question": "解释字段"},
                ).status_code,
                404,
            )
            self.assertEqual(self.ask(preview_token=str(uuid4())).status_code, 409)
            with self.sessions() as db:
                db.get(ImportDraft, self.did).finalized_version_id = str(uuid4())
                db.commit()
            self.assertEqual(self.ask().status_code, 409)
            model.assert_not_called()

    def test_unknown_reference_or_model_mapping_is_rejected(self):
        for changes in [{"references": ["outside"]}, {"columns": {"order_amount": "c99"}}]:
            with (
                self.subTest(changes=changes),
                patch(
                    "app.field_assistant.urllib.request.urlopen",
                    return_value=self.response(**changes),
                ),
            ):
                self.assertEqual(self.ask().json()["mode"], "rejected_model_output")

    def test_unbound_numbers_and_guarantees_are_rejected(self):
        for answer in [
            "销量为999，销售额可以直接决定进货数量。",
            "核对这些字段可以确保准确的进货需求。",
        ]:
            with (
                self.subTest(answer=answer),
                patch(
                    "app.field_assistant.urllib.request.urlopen",
                    return_value=self.response(answer=answer),
                ),
            ):
                self.assertFalse(self.ask().json()["ai_used"])

    def test_timeout_and_unavailable_have_distinct_modes(self):
        for exc, expected in [
            (TimeoutError(), "inference_timeout"),
            (OSError(), "inference_unavailable"),
        ]:
            with (
                self.subTest(mode=expected),
                patch("app.field_assistant.urllib.request.urlopen", side_effect=exc),
            ):
                self.assertEqual(self.ask().json()["mode"], expected)

    def test_missing_columns_do_not_create_semantics_or_amounts(self):
        with patch("app.field_assistant.urllib.request.urlopen", return_value=self.response()):
            data = self.ask().json()
        self.assertNotIn("line_amount", data["proposal"]["columns"])
        self.assertNotIn("currency_constant", data["proposal"])
        self.assertNotIn("confirmed", data["proposal"])

    def test_invalid_payload_is_not_sent_to_model(self):
        with patch("app.field_assistant.urllib.request.urlopen") as model:
            self.assertEqual(self.ask(question="").status_code, 422)
            self.assertEqual(self.ask(question="x" * 401).status_code, 422)
            model.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
