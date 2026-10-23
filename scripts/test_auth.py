"""Real HTTP authentication and tenant boundary tests on disposable SQLite."""

import re
import sqlite3
import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth import COOKIE, password_matches, token_hash
from app.database import create_database
from app.main import create_app
from app.models import Account, AccountSession, Project, ProjectOwner

HEADERS = {"X-Requested-With": "RetailEvidence"}
PASSWORD = "test-only-long-password-2026"


@pytest.fixture
def client(tmp_path):
    app = create_app(database_path=tmp_path / "db.sqlite3", storage_root=tmp_path / "storage")
    with TestClient(app, headers=HEADERS) as client:
        yield client


def register(client, username):
    response = client.post("/api/auth/register", json={"username": username, "password": PASSWORD})
    assert response.status_code == 201, response.text
    return response.json()["user"]


def test_sessions_passwords_and_revocation(client):
    assert client.get("/api/projects").status_code == 401
    user = register(client, "Alice")
    assert user["username"] == "alice"
    token = client.cookies[COOKIE]
    assert client.get("/api/auth/me").json()["user"] == user
    with client.app.state.sessions() as db:
        account = db.get(Account, user["id"])
        assert account.password_hash != PASSWORD and PASSWORD not in account.password_hash
        assert password_matches(PASSWORD, account.password_hash)
        assert db.get(AccountSession, token) is None
        assert db.get(AccountSession, token_hash(token)).account_id == user["id"]
    assert client.post("/api/auth/logout").status_code == 200
    client.cookies.set(COOKIE, token)
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.clear()
    response = client.post("/api/auth/login", json={"username": "ALICE", "password": PASSWORD})
    assert response.status_code == 200
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=strict" in response.headers["set-cookie"]
    assert client.cookies[COOKIE] != token
    new_token = client.cookies[COOKIE]
    with client.app.state.sessions() as db:
        db.get(AccountSession, token_hash(new_token)).expires_at = int(time.time()) - 1
        db.commit()
    assert client.get("/api/projects").status_code == 401


def test_project_name_search_update_and_tenant_scope(client):
    alice = register(client, "alice")
    a_token = client.cookies[COOKIE]
    a = client.post("/api/projects", json={"name": "青禾 Store", "description": "一店"}).json()
    assert a.get("id"), a
    assert client.post("/api/projects", json={"name": "青禾 store"}).status_code == 409
    client.cookies.clear()
    register(client, "bob")
    assert client.get("/api/projects").json()["total"] == 0
    b = client.post("/api/projects", json={"name": "青禾 Store"}).json()
    assert b["id"] != a["id"]
    assert client.get(f"/api/projects/{a['id']}").status_code == 404
    assert (
        client.patch(f"/api/projects/{a['id']}", json={"name": "stolen", "revision": 1}).status_code
        == 404
    )
    assert client.get("/api/projects?q=青禾").json()["total"] == 1
    client.cookies.clear()
    client.cookies.set(COOKIE, a_token)
    assert client.get("/api/auth/me").json()["user"] == alice
    assert client.get("/api/projects?q=STORE").json()["items"][0]["id"] == a["id"]
    assert (
        client.patch(f"/api/projects/{a['id']}", json={"name": "新店", "revision": 1}).status_code
        == 200
    )
    assert (
        client.patch(f"/api/projects/{a['id']}", json={"name": "冲突", "revision": 1}).status_code
        == 409
    )


def test_every_nested_project_route_denies_other_account_before_payload_or_file_access(client):
    register(client, "alice")
    project = client.post("/api/projects", json={"name": "Private"}).json()
    client.cookies.clear()
    register(client, "bob")
    checked = []
    for route_path, operations in client.app.openapi()["paths"].items():
        if "{project_id}" not in route_path:
            continue
        path = route_path.replace("{project_id}", project["id"])
        path = re.sub(r"\{[^}]+\}", str(uuid4()), path)
        for method in operations:
            response = client.request(method, path, json={})
            assert response.status_code == 404, (method, path, response.text)
            checked.append((method, route_path))
    assert len(checked) >= 30
    assert any("/files/" in p for _, p in checked)
    assert any("/ask" in p for _, p in checked)
    assert any("/imports" in p for _, p in checked)
    assert any("/cluster" in p for _, p in checked)
    # A forged project ID with an owned child ID still cannot escape scoped().
    own = client.post("/api/projects", json={"name": "Own"}).json()
    response = client.get(f"/api/projects/{own['id']}/runs/{uuid4()}")
    assert response.status_code == 404


def test_unauthenticated_all_api_routes_default_closed(client):
    checked = 0
    for route_path, operations in client.app.openapi()["paths"].items():
        if not route_path.startswith("/api/") or route_path in {
            "/api/health",
            "/api/auth/register",
            "/api/auth/login",
        }:
            continue
        path = re.sub(r"\{[^}]+\}", str(uuid4()), route_path)
        for method in operations:
            assert client.request(method, path, json={}).status_code == 401, (method, path)
            checked += 1
    assert checked >= 35


def test_csrf_registration_validation_and_account_privacy(client):
    assert (
        client.post(
            "/api/auth/register",
            headers={"X-Requested-With": ""},
            json={"username": "alice", "password": PASSWORD},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/auth/register",
            headers={"Origin": "https://other.example"},
            json={"username": "alice", "password": PASSWORD},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/auth/register", json={"username": "alice", "password": "short"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/auth/register", json={"username": "../etc", "password": PASSWORD}
        ).status_code
        == 422
    )
    register(client, "alice")
    assert (
        client.post(
            "/api/auth/register", json={"username": "ALICE", "password": PASSWORD}
        ).status_code
        == 409
    )
    known = client.post(
        "/api/auth/login", json={"username": "alice", "password": "incorrect-password"}
    )
    unknown = client.post(
        "/api/auth/login", json={"username": "nobody", "password": "incorrect-password"}
    )
    assert known.status_code == unknown.status_code == 401
    assert known.json() == unknown.json()
    assert (
        client.post(
            "/api/projects", headers={"X-Requested-With": ""}, json={"name": "bad"}
        ).status_code
        == 403
    )


def test_password_change_revokes_other_sessions(client):
    register(client, "alice")
    token = client.cookies[COOKIE]
    client.cookies.clear()
    assert (
        client.post("/api/auth/login", json={"username": "alice", "password": PASSWORD}).status_code
        == 200
    )
    assert (
        client.post(
            "/api/auth/password",
            json={
                "current_password": "incorrect-password",
                "new_password": "new-test-password-123",
            },
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/auth/password",
            json={"current_password": PASSWORD, "new_password": "new-test-password-123"},
        ).status_code
        == 200
    )
    current = client.cookies[COOKIE]
    client.cookies.clear()
    client.cookies.set(COOKIE, token)
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.clear()
    client.cookies.set(COOKIE, current)
    assert client.get("/api/auth/me").status_code == 200
    assert (
        client.post("/api/auth/login", json={"username": "alice", "password": PASSWORD}).status_code
        == 401
    )


def test_login_rate_limit(client):
    register(client, "alice")
    for _ in range(15):
        assert (
            client.post(
                "/api/auth/login", json={"username": "alice", "password": "incorrect-password"}
            ).status_code
            == 401
        )
    assert (
        client.post("/api/auth/login", json={"username": "alice", "password": PASSWORD}).status_code
        == 429
    )


def test_legacy_projects_remain_unowned_and_additive_migration(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    engine, sessions = create_database(path)
    with sessions() as db:
        project = Project(name="Legacy", name_key="legacy", description="unchanged")
        db.add(project)
        db.commit()
        pid = project.id
    engine.dispose()
    with sqlite3.connect(path) as db:
        for table in ["project_owners", "account_sessions", "auth_throttle", "accounts"]:
            db.execute(f"DROP TABLE {table}")
        db.execute("PRAGMA user_version=5")
        before = db.execute("SELECT * FROM projects").fetchall()
    with TestClient(create_app(database_path=path), headers=HEADERS) as client:
        register(client, "first_user")
        assert client.get("/api/projects").json()["total"] == 0
        assert client.get(f"/api/projects/{pid}").status_code == 404
        with client.app.state.sessions() as session:
            assert session.scalar(select(ProjectOwner)) is None
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT * FROM projects").fetchall() == before
        assert db.execute("PRAGMA user_version").fetchone()[0] == 6
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
