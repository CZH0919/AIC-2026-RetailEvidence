"""Fresh HTTP regression cases for the system-polish correctness fixes.

All accounts and records are synthetic in pytest's disposable directory. The
worker is disabled only here: these tests exercise API contracts with frozen
published results; full real-worker/browser flows are tested separately.
"""

import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import create_app
from app.models import AnalysisRun, CleaningPolicy, DatasetVersion, MappingVersion, SalesRecord
from app.task_runner import TaskRunner

HEADERS = {"X-Requested-With": "RetailEvidence"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(TaskRunner, "start", lambda self: None)
    app = create_app(database_path=tmp_path / "db.sqlite3", storage_root=tmp_path / "storage")
    with TestClient(app, headers=HEADERS, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/auth/register",
            json={"username": "polish_review", "password": "disposable-test-password-2026"},
        )
        assert response.status_code == 201, response.text
        yield client


def seed_run(client, project_id, kind, result):
    """Seed immutable published input; never fabricate an algorithm test pass."""
    with client.app.state.sessions() as db:
        number = len(list(db.scalars(select(DatasetVersion)))) + 1
        version = DatasetVersion(
            id=str(uuid4()), project_id=project_id, number=number, filename="fixture.csv",
            suffix=".csv", sha256="a" * 64, bytes=1, row_count=1, options="{}", preview="{}",
        )
        db.add(version)
        db.flush()
        mapping = MappingVersion(
            id=str(uuid4()), dataset_version_id=version.id, revision=1,
            config="{}", validation="{}",
        )
        db.add(mapping)
        db.flush()
        policy = CleaningPolicy(
            id=str(uuid4()), dataset_version_id=version.id, mapping_version_id=mapping.id,
            number=1, config="{}", config_sha256="b" * 64,
        )
        db.add(policy)
        db.flush()
        run = AnalysisRun(
            id=str(uuid4()), project_id=project_id, dataset_version_id=version.id,
            mapping_version_id=mapping.id, policy_id=policy.id, kind=kind,
            idempotency_key=str(uuid4()), request_sha256="c" * 64, parameters="{}",
            status="succeeded", result=json.dumps(result),
        )
        db.add(run)
        db.commit()
        return run.id


def quality_result():
    return {
        "capabilities": {kind: {"allowed": True} for kind in ["rf", "rfm", "association"]},
        "summary": {"rf_customers": 20, "rfm_customers": 20},
        "context": {"fixture": "frozen-contract-only"},
    }


def create_project(client):
    response = client.post("/api/projects", json={"name": "回归店铺"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_project_search_uses_name_and_description_not_account_namespace(client):
    uid = client.get("/api/auth/me").json()["user"]["id"]
    first = client.post("/api/projects", json={"name": "青禾 ＡＢＣ"}).json()
    second = client.post(
        "/api/projects", json={"name": "溪边蔬果", "description": "客厅 100% 专供"}
    ).json()
    for query in [uid, uid[:8], "_"]:
        result = client.get("/api/projects", params={"q": query}).json()
        assert result["total"] == 0 and result["items"] == [], (query, result)
    for query in ["abc", "ＡＢＣ", "ABC", "青禾"]:
        result = client.get("/api/projects", params={"q": query}).json()
        assert result["total"] == 1
        assert [row["id"] for row in result["items"]] == [first["id"]]
    for query in ["%", "100%", "客厅"]:
        result = client.get("/api/projects", params={"q": query}).json()
        assert result["total"] == 1
        assert result["items"][0]["id"] == second["id"]
    assert client.get("/api/projects").json()["total"] == 2


@pytest.mark.parametrize("kind", ["sales", "clustering", "association"])
def test_eligibility_rejects_non_quality_results_without_server_error(client, kind):
    pid = create_project(client)
    rid = seed_run(client, pid, kind, {"summary": {}})
    response = client.post(
        f"/api/projects/{pid}/runs/{rid}/eligibility", json={"kind": "rf"}
    )
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "quality_not_ready"
    quality = seed_run(client, pid, "quality", quality_result())
    valid = client.post(
        f"/api/projects/{pid}/runs/{quality}/eligibility", json={"kind": "rf"}
    )
    assert valid.status_code == 200 and valid.json()["allowed"] is True


@pytest.mark.parametrize("endpoint,kind", [("cluster", "rf"), ("association", "association")])
def test_analysis_idempotency_cannot_reuse_different_quality_input(client, endpoint, kind):
    pid = create_project(client)
    first_quality = seed_run(client, pid, "quality", quality_result())
    second_quality = seed_run(client, pid, "quality", quality_result())
    payload = {"parameters": {"kind": kind}, "idempotency_key": "same-request-key"}
    first_url = f"/api/projects/{pid}/runs/{first_quality}/{endpoint}"
    second_url = f"/api/projects/{pid}/runs/{second_quality}/{endpoint}"
    first = client.post(first_url, json=payload)
    assert first.status_code == 202, first.text
    same = client.post(first_url, json=payload)
    assert same.status_code == 202 and same.json()["id"] == first.json()["id"]
    conflict = client.post(second_url, json=payload)
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["error"]["code"] == "idempotency_conflict"
    fresh = client.post(second_url, json={**payload, "idempotency_key": "new-request-key"})
    assert fresh.status_code == 202, fresh.text
    assert fresh.json()["id"] != first.json()["id"]
    assert fresh.json()["quality_run_id"] == second_quality
    with client.app.state.sessions() as db:
        first_run = db.get(AnalysisRun, first.json()["id"])
        assert first_run.quality_run_id == first_quality


@pytest.mark.parametrize(
    "forecast,available,incoming,reserve,pack,expected",
    [
        (177, 175.6, 0, 0, 1.4, 1.4),
        (10, 5.8, 0, 0, 1.4, 4.2),
        (177, 10, 7, 3, 6, 168),
        (177, 175.59, 0, 0, 1.4, 2.8),
        (177, 180, 0, 0, 6, 0),
    ],
)
def test_inventory_package_rounding_uses_entered_decimal_units(
    client, forecast, available, incoming, reserve, pack, expected
):
    pid = create_project(client)
    report = {"products": [{
        "id": "P001", "record_kind": "physical_product", "classification_confirmed": True,
        "forecast": {"quantity": forecast, "start": "2026-10-01", "end": "2026-10-07"},
    }]}
    rid = seed_run(client, pid, "sales", report)
    response = client.post(f"/api/projects/{pid}/sales/runs/{rid}/inventory", json={
        "item_id": "P001", "snapshot_date": "2026-10-01", "available": available,
        "incoming": incoming, "arrival_date": "2026-10-02" if incoming else None,
        "reserve": reserve, "pack_size": pack, "confirmed": True,
    })
    assert response.status_code == 200, response.text
    assert response.json()["value"]["suggested_quantity"] == expected
    with client.app.state.sessions() as db:
        stored = db.scalar(select(SalesRecord).where(SalesRecord.run_id == rid))
        assert json.loads(stored.value)["suggested_quantity"] == expected
        assert json.loads(db.get(AnalysisRun, rid).result) == report
