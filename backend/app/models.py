from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(64))
    name_key: Mapped[str] = mapped_column(String(128), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    color: Mapped[str] = mapped_column(String(16), default="teal")
    created_at: Mapped[str] = mapped_column(String(40), default=timestamp)
    updated_at: Mapped[str] = mapped_column(String(40), default=timestamp, index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)


class ImportDraft(Base):
    __tablename__ = "import_drafts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    filename: Mapped[str] = mapped_column(String(200))
    suffix: Mapped[str] = mapped_column(String(8))
    sha256: Mapped[str] = mapped_column(String(64))
    bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(String(40), default=timestamp)
    source_dataset: Mapped[str | None] = mapped_column(String(40), nullable=True)
    inspection: Mapped[str] = mapped_column(Text)
    options: Mapped[str | None] = mapped_column(Text, nullable=True)
    preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    preview_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    mapping_draft: Mapped[str | None] = mapped_column(Text, nullable=True)
    finalized_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"
    __table_args__ = (UniqueConstraint("project_id", "number"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    filename: Mapped[str] = mapped_column(String(200))
    suffix: Mapped[str] = mapped_column(String(8))
    sha256: Mapped[str] = mapped_column(String(64))
    bytes: Mapped[int] = mapped_column(Integer)
    row_count: Mapped[int] = mapped_column(Integer)
    options: Mapped[str] = mapped_column(Text)
    preview: Mapped[str] = mapped_column(Text)
    source_dataset: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), default=timestamp)


class MappingVersion(Base):
    __tablename__ = "mapping_versions"
    __table_args__ = (UniqueConstraint("dataset_version_id", "revision"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    dataset_version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    config: Mapped[str] = mapped_column(Text)
    validation: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40), default=timestamp)


class CleaningPolicy(Base):
    __tablename__ = "cleaning_policies"
    __table_args__ = (
        UniqueConstraint("dataset_version_id", "number"),
        UniqueConstraint("mapping_version_id", "config_sha256"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    dataset_version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"), index=True)
    mapping_version_id: Mapped[str] = mapped_column(ForeignKey("mapping_versions.id"))
    number: Mapped[int] = mapped_column(Integer)
    config: Mapped[str] = mapped_column(Text)
    config_sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[str] = mapped_column(String(40), default=timestamp)


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (UniqueConstraint("project_id", "idempotency_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    dataset_version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"))
    mapping_version_id: Mapped[str] = mapped_column(ForeignKey("mapping_versions.id"))
    policy_id: Mapped[str] = mapped_column(ForeignKey("cleaning_policies.id"))
    kind: Mapped[str] = mapped_column(String(32), default="quality")
    idempotency_key: Mapped[str] = mapped_column(String(80))
    request_sha256: Mapped[str] = mapped_column(String(64))
    parameters: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="queued", index=True)
    phase: Mapped[str] = mapped_column(String(40), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(Text, default="已加入处理队列。")
    cancel_requested: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String(40), default=timestamp)
    started_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    finished_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    peak_rss_bytes: Mapped[int] = mapped_column(Integer, default=0)


class RunEvent(Base):
    __tablename__ = "run_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id"), index=True)
    status: Mapped[str] = mapped_column(String(40))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40), default=timestamp)
