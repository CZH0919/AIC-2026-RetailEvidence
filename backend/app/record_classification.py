"""Frozen, source-scoped business classifications. Never infer accounting semantics."""

import hashlib
import json
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .import_formats import DataIssue

RecordKind = Literal[
    "physical_product", "shipping_service", "manual_adjustment", "other", "pending"
]
AmountTreatment = Literal["include", "exclude", "pending"]
LABELS = {
    "physical_product": "实物商品",
    "shipping_service": "运费/服务",
    "manual_adjustment": "人工调整",
    "other": "其他",
    "pending": "待确认",
}


class ClassificationRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    match_by: Literal["item_id", "source_row_id", "category"] = "item_id"
    value: str = Field(min_length=1, max_length=200)
    kind: RecordKind = "pending"
    amount_treatment: AmountTreatment = "pending"
    basis: str = Field(default="用户确认", min_length=1, max_length=300)


class SourceClassification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version_id: UUID
    mapping_revision: int = Field(ge=1)
    default_kind: RecordKind = "pending"
    default_amount_treatment: AmountTreatment = "pending"
    confirmed: bool = False
    rules: list[ClassificationRule] = Field(default_factory=list, max_length=5000)

    @model_validator(mode="after")
    def unique_rules(self):
        keys = [(r.match_by, r.value) for r in self.rules]
        if len(set(keys)) != len(keys):
            raise ValueError("同一范围的分类规则不能重复")
        return self


def classification_hash(policies):
    return hashlib.sha256(
        json.dumps(policies, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def compile_policies(sources, parameters):
    policies = parameters.get("classifications", [])
    known = {(s["version_id"], s["mapping_revision"]) for s in sources}
    result = {}
    for policy in policies:
        key = (policy["version_id"], policy["mapping_revision"])
        if key not in known or key in result:
            raise DataIssue("分类配置不属于选中的数据和字段版本。", "classification_scope")
        parsed = SourceClassification.model_validate(policy).model_dump(mode="json")
        result[key] = {**parsed, "index": {(r["match_by"], r["value"]): r for r in parsed["rules"]}}
    return result


def classify(row, source, compiled):
    policy = compiled.get((source["version_id"], source["mapping_revision"]))
    if not policy or not policy["confirmed"]:
        return {
            "kind": "pending",
            "amount_treatment": "pending",
            "basis": "业务分类尚未确认",
            "scope": "unconfirmed",
        }
    for field in ["source_row_id", "item_id", "category"]:
        rule = policy["index"].get((field, str(row.get(field) or "")))
        if rule:
            return {
                "kind": rule["kind"],
                "amount_treatment": rule["amount_treatment"],
                "basis": rule["basis"],
                "scope": field + ":" + rule["value"],
            }
    return {
        "kind": policy["default_kind"],
        "amount_treatment": policy["default_amount_treatment"],
        "basis": "用户确认的其余记录口径",
        "scope": "default",
    }


def csv_text(value):
    text = "" if value is None else str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else text


def csv_untext(value):
    return (
        value[1:]
        if value.startswith("'") and value[1:].lstrip().startswith(("=", "+", "-", "@", "\t", "\r"))
        else value
    )
