"""Operator changes use only temporary databases and keep historical report rows."""

import sqlite3
import sys

import account_admin
import pytest
from fastapi.testclient import TestClient

from app.auth import COOKIE, password_matches
from app.main import create_app
from app.models import Account, Project


def test_assignment_dry_run_and_password_recovery(tmp_path, monkeypatch):
    path = tmp_path / "database.sqlite3"
    with TestClient(
        create_app(database_path=path), headers={"X-Requested-With": "RetailEvidence"}
    ) as client:
        result = client.post(
            "/api/auth/register", json={"username": "owner", "password": "temporary-test-password"}
        )
        assert result.status_code == 201
        uid = result.json()["user"]["id"]
        cookie = client.cookies[COOKIE]
        with client.app.state.sessions() as db:
            project = Project(name="Preserved history", name_key="preserved history")
            db.add(project)
            db.commit()
            pid, revision = project.id, project.revision
        args = [
            "account_admin",
            "--database",
            str(path),
            "--username",
            "owner",
            "--assign-project",
            pid,
        ]
        monkeypatch.setattr(sys, "argv", args)
        account_admin.main()
        assert client.get(f"/api/projects/{pid}").status_code == 404
        monkeypatch.setattr(sys, "argv", args + ["--apply"])
        account_admin.main()
        project = client.get(f"/api/projects/{pid}").json()
        assert project["name"] == "Preserved history" and project["revision"] == revision
        assert client.get("/api/projects?q=HISTORY").json()["total"] == 1
        with pytest.raises(SystemExit):
            account_admin.main()  # No silent transfer of assigned projects.
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "account_admin",
                "--database",
                str(path),
                "--username",
                "owner",
                "--reset-password",
                "--apply",
            ],
        )
        monkeypatch.setattr(account_admin.getpass, "getpass", lambda _: "new-recovery-password")
        account_admin.main()
        assert client.get("/api/auth/me").status_code == 401
        with client.app.state.sessions() as db:
            assert password_matches("new-recovery-password", db.get(Account, uid).password_hash)
        client.cookies.clear()
        response = client.post(
            "/api/auth/login", json={"username": "owner", "password": "new-recovery-password"}
        )
        assert response.status_code == 200 and client.cookies[COOKIE] != cookie
    backups = list((tmp_path / "account-backups").glob("*/before.sqlite3"))
    assert len(backups) == 2
    for backup in backups:
        with sqlite3.connect(backup) as db:
            assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert db.execute("PRAGMA foreign_key_check").fetchall() == []
