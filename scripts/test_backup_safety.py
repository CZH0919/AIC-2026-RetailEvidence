"""Synthetic offline utility checks only; never retail acceptance evidence."""

import json
import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from backup_sales_release import backup_database, digest, inspect_database

root = Path(
    os.environ.get("RETAIL_TEST_ROOT", Path(__file__).resolve().parents[1] / ".runtime")
).resolve()


def run():
    if str(root).lower().startswith("c:"):
        raise ValueError("C drive test workspace rejected")
    (root / "tmp").mkdir(parents=True, exist_ok=True)
    (root / "evidence").mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix="backup-test-", dir=root / "tmp")).resolve()
    assert temp.is_relative_to((root / "tmp").resolve())
    source = temp / "live.sqlite3"
    live = sqlite3.connect(source)
    live.execute("PRAGMA journal_mode=WAL")
    live.execute("PRAGMA wal_autocheckpoint=0")
    live.execute("PRAGMA foreign_keys=ON")
    live.executescript(
        "CREATE TABLE projects(id INTEGER PRIMARY KEY); "
        "CREATE TABLE runs(id INTEGER PRIMARY KEY, project_id INTEGER REFERENCES projects(id)); "
        "PRAGMA user_version=5;"
    )
    live.execute("INSERT INTO projects VALUES (1)")
    live.executemany("INSERT INTO runs VALUES (?,1)", [(i,) for i in range(1, 21)])
    live.commit()
    assert Path(str(source) + "-wal").exists(), "Fixture must contain live WAL"
    initial = list(live.execute("SELECT * FROM runs ORDER BY id"))
    result = backup_database(source, temp / "snapshot")
    frozen = Path(result["database"])
    assert result["verification"]["user_version"] == 5
    assert result["verification"]["table_counts"] == {"projects": 1, "runs": 20}
    assert list(live.execute("SELECT * FROM runs ORDER BY id")) == initial
    original_backup_hash = digest(frozen)
    try:
        backup_database(source, temp / "snapshot")
    except FileExistsError:
        pass
    else:
        raise AssertionError("Existing backup directory must be rejected")
    assert digest(frozen) == original_backup_hash
    live.execute("INSERT INTO runs VALUES (21,1)")
    live.commit()
    assert inspect_database(frozen)["table_counts"]["runs"] == 20
    assert live.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 21
    restore = temp / "restore.sqlite3"
    with closing(sqlite3.connect(frozen.resolve().as_uri() + "?mode=ro", uri=True)) as archived:
        with closing(sqlite3.connect(restore)) as fresh:
            archived.backup(fresh)
    assert inspect_database(restore) == result["verification"]
    assert digest(frozen) == original_backup_hash
    # Broken FK source must not be reported as a successful verified backup.
    broken = temp / "broken.sqlite3"
    with closing(sqlite3.connect(broken)) as bad:
        bad.executescript(
            "CREATE TABLE p(id INTEGER PRIMARY KEY); "
            "CREATE TABLE r(p_id INTEGER REFERENCES p(id)); "
            "INSERT INTO r VALUES(99);"
        )
    try:
        backup_database(broken, temp / "rejected")
    except ValueError:
        failed = json.loads((temp / "rejected" / "backup_manifest.json").read_text())
        assert failed["status"] == "FAIL"
        assert not (temp / "rejected" / "database.sqlite3").exists()
    else:
        raise AssertionError("Broken foreign keys must reject publication")
    live.close()
    evidence = {
        "scope": "synthetic offline backup utility only; no production database read or copied",
        "status": "PASS",
        "checks": [
            "committed WAL captured",
            "schema and table counts verified",
            "source rows unchanged",
            "existing destination rejected without overwrite",
            "snapshot frozen after later source mutation",
            "restore on independent database validated",
            "broken FK rejects successful backup publication",
        ],
        "backup_sha256": original_backup_hash,
        "production_backup_status": "NOT_RUN",
        "synthetic_fixture_directory": str(temp),
    }
    (root / "evidence" / "backup_utility_test.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(evidence, ensure_ascii=False))


if __name__ == "__main__":
    run()
