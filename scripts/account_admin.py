"""Local operator utility. Never exposed as an HTTP endpoint.

Requires a pre-existing schema-6 database and an explicitly named account.
Creates an online backup before any mutation. Passwords are read by getpass.
"""

import argparse
import getpass
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.auth import password_hash, project_name_key
from app.schemas import name_key


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--apply", action="store_true", help="Otherwise only validate the request")
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--assign-project", help="Assign exactly one currently unowned project")
    actions.add_argument("--reset-password", action="store_true")
    args = parser.parse_args()
    path = args.database.resolve(strict=True)
    if str(path).lower().startswith("c:"):
        parser.error("C drive mutation is not supported by this task utility")
    with sqlite3.connect(path.as_uri() + "?mode=rw", uri=True) as db:
        db.execute("PRAGMA foreign_keys=ON")
        if db.execute("PRAGMA user_version").fetchone()[0] != 6:
            parser.error("Requires an already migrated schema-6 database")
        user = db.execute(
            "SELECT id FROM accounts WHERE username=? AND active=1",
            (args.username.strip().lower(),),
        ).fetchone()
        if not user:
            parser.error("Account not found")
        if args.assign_project:
            project = db.execute(
                "SELECT name FROM projects WHERE id=?", (args.assign_project,)
            ).fetchone()
            if (
                not project
                or db.execute(
                    "SELECT 1 FROM project_owners WHERE project_id=?", (args.assign_project,)
                ).fetchone()
            ):
                parser.error("Project is missing or already assigned; transfer is not supported")
        if not args.apply:
            print("Request validated only. Obtain ownership approval and repeat with --apply.")
            return
        encoded = None
        if args.reset_password:
            password = getpass.getpass("New password (not echoed): ")
            if not 12 <= len(password) <= 128 or password != getpass.getpass("Repeat password: "):
                parser.error("Password length or confirmation is invalid")
            encoded = password_hash(password)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        destination = path.parent / "account-backups" / stamp
        destination.mkdir(parents=True, exist_ok=False, mode=0o700)
        with sqlite3.connect(destination / "before.sqlite3") as backup:
            db.backup(backup)
            assert backup.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        db.execute("BEGIN IMMEDIATE")
        if args.assign_project:
            db.execute(
                "INSERT INTO project_owners(project_id,account_id) VALUES(?,?)",
                (args.assign_project, user[0]),
            )
            db.execute(
                "UPDATE projects SET name_key=? WHERE id=?",
                (project_name_key(user[0], name_key(project[0])), args.assign_project),
            )
        else:
            db.execute("UPDATE accounts SET password_hash=? WHERE id=?", (encoded, user[0]))
            db.execute("DELETE FROM account_sessions WHERE account_id=?", (user[0],))
        db.commit()
        receipt = {
            "time": stamp,
            "account_id": user[0],
            "project_id": args.assign_project,
            "action": "assign_unowned" if args.assign_project else "password_reset",
            "backup": str(destination / "before.sqlite3"),
        }
        (destination / "receipt.json").write_text(json.dumps(receipt, indent=2))
        print(json.dumps(receipt))


if __name__ == "__main__":
    main()
