from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "projects.sqlite3")) as active:
        yield active


def create(client, name="华东门店", **extra):
    return client.post("/api/projects", json={"name": name, **extra})


def test_create_get_list_and_persist_across_app_restart(tmp_path):
    database = tmp_path / "persist.sqlite3"
    with TestClient(create_app(database)) as first:
        response = create(first, description="季度复盘")
        assert response.status_code == 201
        project = response.json()
    with TestClient(create_app(database)) as second:
        assert second.get(f"/api/projects/{project['id']}").json() == project
        assert second.get("/api/projects").json()["total"] == 1


@pytest.mark.parametrize("payload", [
    {"name": "   "}, {"name": "x" * 65}, {"name": "两\n行"},
    {"name": "测试", "description": "x" * 501}, {"name": "测试", "color": "invalid"},
    {"name": "测试", "unknown": True}, {"name": None},
])
def test_reject_invalid_input(client, payload):
    response = client.post("/api/projects", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert client.get("/api/projects").json()["total"] == 0


def test_name_normalization_and_atomic_uniqueness(client):
    assert create(client, "  ＡＢＣ  ").status_code == 201
    assert create(client, "abc").status_code == 409
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda _: create(client, "并发项目").status_code, range(2)))
    assert sorted(statuses) == [201, 409]


def test_update_isolated_and_stale_write_rejected(client):
    a, b = create(client, "项目一").json(), create(client, "项目二").json()
    endpoint = f"/api/projects/{a['id']}"
    response = client.patch(endpoint, json={"name": "更新项目", "revision": 1})
    assert response.status_code == 200
    assert response.json()["revision"] == 2
    assert client.patch(endpoint, json={"name": "旧数据", "revision": 1}).status_code == 409
    assert client.get(f"/api/projects/{b['id']}").json() == b
    assert client.get(endpoint).json()["name"] == "更新项目"


def test_search_pagination_and_literal_wildcards(client):
    create(client, "A_100%", description="季度复盘")
    create(client, "其他项目")
    assert client.get("/api/projects", params={"q": "%"}).json()["total"] == 1
    assert client.get("/api/projects", params={"q": "季度"}).json()["total"] == 1
    first = client.get("/api/projects", params={"limit": 1}).json()
    second = client.get("/api/projects", params={"limit": 1, "offset": 1}).json()
    assert first["total"] == 2 and first["items"][0]["id"] != second["items"][0]["id"]


def test_missing_project_and_cross_origin_write(client):
    response = client.get(f"/api/projects/{uuid4()}")
    assert response.status_code == 404 and response.json()["error"]["code"] == "not_found"
    assert create(client, "正常项目").status_code == 201
    bad = client.post("/api/projects", json={"name": "外站请求"}, headers={"Origin": "https://unrelated.test"})
    assert bad.status_code == 403
    assert client.get("/api/projects").json()["total"] == 1


def test_user_text_is_returned_as_data(client):
    text = '<img src=x onerror="alert(1)">'
    response = create(client, text)
    assert response.status_code == 201 and response.json()["name"] == text
    assert response.headers["x-content-type-options"] == "nosniff"
