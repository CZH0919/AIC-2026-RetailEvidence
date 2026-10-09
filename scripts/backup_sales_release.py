"""Explicit, non-overwriting SQLite online backup; no default production path."""

import argparse
import hashlib
import json
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def inspect_database(path):
    with closing(
        sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
    ) as conn:
        integrity = [row[0] for row in conn.execute("PRAGMA integrity_check")]
        foreign_key_errors = len(conn.execute("PRAGMA foreign_key_check").fetchall())
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        counts = {
            table: conn.execute(
                'SELECT COUNT(*) FROM "' + table.replace('"', '""') + '"'
            ).fetchone()[0]
            for table in tables
        }
        schema = conn.execute("PRAGMA user_version").fetchone()[0]
    return dict(
        integrity=integrity,
        foreign_key_errors=foreign_key_errors,
        user_version=schema,
        table_counts=counts,
    )


def backup_database(database, destination, max_seconds=60):
    database, destination = Path(database).resolve(), Path(destination).resolve()
    if str(destination).lower().startswith("c:"):
        raise ValueError("C drive destination rejected")
    if not database.is_file():
        raise FileNotFoundError("Source database is not a file")
    if not 1 <= max_seconds <= 300:
        raise ValueError("max_seconds must be between 1 and 300")
    # Never reuse/replace an existing backup directory or live database.
    destination.mkdir(parents=False, exist_ok=False)
    partial = destination / "database.partial.sqlite3"
    result = {
        "status": "INCOMPLETE",
        "method": "sqlite3.Connection.backup",
        "source": str(database),
        "created_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        "max_seconds": max_seconds,
    }
    start = time.monotonic()

    def progress(status, remaining, total):
        if time.monotonic() - start > max_seconds:
            raise TimeoutError("Online backup time budget exceeded")

    try:
        with closing(
            sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=5)
        ) as source:
            with closing(sqlite3.connect(partial, timeout=5)) as target:
                source.backup(target, pages=256, progress=progress, sleep=0.1)
        inspected = inspect_database(partial)
        if inspected["integrity"] != ["ok"] or inspected["foreign_key_errors"]:
            raise ValueError("Backup integrity or foreign key check failed")
        final_path = destination / "database.sqlite3"
        partial.rename(final_path)
        result.update(
            status="PASS",
            database=str(final_path),
            sha256=digest(final_path),
            elapsed_seconds=round(time.monotonic() - start, 3),
            verification=inspected,
            limits=(
                "Integrity and counts checked; external source and run references "
                "require separate application checks."
            ),
        )
    except Exception as error:
        result.update(
            status="FAIL",
            error_type=type(error).__name__,
            error=str(error),
            elapsed_seconds=round(time.monotonic() - start, 3),
        )
        (destination / "backup_manifest.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        raise
    (destination / "backup_manifest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--max-seconds", type=int, default=60)
    args = parser.parse_args()
    print(
        json.dumps(
            backup_database(args.database, args.destination, args.max_seconds),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
