from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CleaningConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trim_identifiers: bool = True
    duplicates: Literal["keep", "drop_exact"] = "keep"
    monetary_subset: Literal["all_customers", "complete_customers"] = "all_customers"
    accept_selected_amount_source: bool = False


class PolicyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mapping_revision: int = Field(ge=1)
    config: CleaningConfig = Field(default_factory=CleaningConfig)


class DataScope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date_start: date | None = None
    date_end: date | None = None
    countries: list[str] = Field(default_factory=list, max_length=20)
    item_ids: list[str] = Field(default_factory=list, max_length=200)
    currency: str | None = Field(default=None, min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")

    @field_validator("countries", "item_ids")
    @classmethod
    def bounded_values(cls, values):
        if any(not value.strip() or len(value) > 200 for value in values):
            raise ValueError("筛选值应包含 1–200 个字符")
        return list(dict.fromkeys(values))

    @model_validator(mode="after")
    def ordered_dates(self):
        if self.date_start and self.date_end and self.date_start > self.date_end:
            raise ValueError("开始日期不能晚于结束日期")
        return self


class QualityRunInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_version_id: UUID
    policy_id: UUID
    scope: DataScope = Field(default_factory=DataScope)
    idempotency_key: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.:-]+$")
    timeout_seconds: Literal[600, 1200] = 600
    memory_mb: int = Field(default=8192, ge=64, le=8192)


class AnalysisParameters(BaseModel):
    """Shared entry contract for the next modules; validation does not run an algorithm."""

    model_config = ConfigDict(extra="forbid")
    kind: Literal["rf", "rfm", "association"]
    k_min: int = Field(default=2, ge=2, le=8)
    k_max: int = Field(default=8, ge=2, le=8)
    random_state: Literal[42] = 42
    n_init: Literal[10] = 10
    min_support: float = Field(default=0.005, gt=0, le=1, allow_inf_nan=False)
    min_count: int = Field(default=20, ge=1, le=100000)
    min_confidence: float = Field(default=0.2, gt=0, le=1, allow_inf_nan=False)
    max_length: int = Field(default=3, ge=2, le=3)

    @model_validator(mode="after")
    def ordered_clusters(self):
        if self.k_min > self.k_max:
            raise ValueError("最小分群数不能大于最大分群数")
        return self


class ClusteringRunInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    parameters: AnalysisParameters
    idempotency_key: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.:-]+$")
    timeout_seconds: Literal[600, 1200] = 600
    memory_mb: int = Field(default=8192, ge=64, le=8192)
