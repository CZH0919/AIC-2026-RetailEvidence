from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceInput(BaseModel):
    version_id: UUID
    mapping_revision: int = Field(ge=1)


class RetailInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sources: list[SourceInput] = Field(min_length=1, max_length=36)
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    merge_mode: Literal["append", "replace_overlap"] = "append"
    duplicates: Literal["keep", "drop_exact"] = "keep"
    coverage_start: date | None = None
    coverage_end: date | None = None
    complete_coverage: bool = False
    closed_dates: list[date] = Field(default_factory=list, max_length=366)
    idempotency_key: str = Field(min_length=8, max_length=80)
    budget_seconds: Literal[600, 1200] = 1200
    check_only: bool = False

    @model_validator(mode="after")
    def coverage(self):
        if len({s.version_id for s in self.sources}) != len(self.sources):
            raise ValueError("数据版本不能重复选择")
        if self.complete_coverage and (not self.coverage_start or not self.coverage_end):
            raise ValueError("请确认完整记录的起止日期")
        if self.coverage_start and self.coverage_end:
            if self.coverage_end < self.coverage_start:
                raise ValueError("日期范围无效")
            if (self.coverage_end - self.coverage_start).days > 1095:
                raise ValueError("最多处理三年日记录")
        date.fromisoformat(self.month + "-01")
        return self


class ActionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["pending", "done", "declined"]
    note: str = Field(default="", max_length=500)
    expected_revision: int = Field(default=0, ge=0)


class ItemNoteInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_id: str = Field(min_length=1, max_length=200)
    day: date | None = None
    reason: Literal["unknown", "closed", "stockout", "promotion", "entry_error", "other"]
    note: str = Field(default="", max_length=500)
    expected_revision: int = Field(default=0, ge=0)


class InventoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_id: str = Field(min_length=1, max_length=200)
    snapshot_date: date
    available: float = Field(ge=0, le=1e9, allow_inf_nan=False)
    incoming: float = Field(ge=0, le=1e9, allow_inf_nan=False)
    arrival_date: date | None = None
    reserve: float = Field(ge=0, le=1e9, allow_inf_nan=False)
    pack_size: float = Field(default=1, gt=0, le=1e6, allow_inf_nan=False)
    confirmed: bool = False


class QuestionInput(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    item_id: str | None = Field(default=None, max_length=200)
