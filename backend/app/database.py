from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from .models import Base


def create_database(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{path.as_posix()}", connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def configure_sqlite(connection, _):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA journal_mode=WAL")
        version = connection.exec_driver_sql("PRAGMA user_version").scalar()
        if version not in (0, 1, 2):
            raise RuntimeError("Unsupported database schema; migration required")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        # Additive v1 -> v2 migration: create import/version tables, preserve projects.
        connection.exec_driver_sql("PRAGMA user_version=2")
    return engine, sessionmaker(engine, expire_on_commit=False)
