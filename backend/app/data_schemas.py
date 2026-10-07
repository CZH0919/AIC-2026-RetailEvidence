from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator

FIELDS = {
    "order_id": "订单 / 购物篮标识",
    "item_id": "商品标识",
    "item_name": "商品名称",
    "customer_id": "客户标识",
    "event_time": "交易时间",
    "quantity": "数量",
    "unit_price": "单价",
    "line_amount": "行金额",
    "order_amount": "订单总额",
    "currency": "币种",
    "record_status": "交易状态",
    "country": "国家 / 地区",
    "category": "商品分类",
}
TIME_FORMATS = {
    "iso8601": "ISO 日期 / Excel 日期",
    "%Y-%m-%d": "年-月-日",
    "%Y/%m/%d": "年/月/日",
    "%Y-%m-%d %H:%M:%S": "年-月-日 时:分:秒",
    "%d/%m/%Y %H:%M": "日/月/年 时:分",
    "%m/%d/%Y %H:%M": "月/日/年 时:分",
    "%d/%m/%Y": "日/月/年",
    "%m/%d/%Y": "月/日/年",
}


class ParseOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    encoding: Literal["utf-8-sig", "gb18030", "cp1252"] = "utf-8-sig"
    delimiter: Literal[",", ";", "\t", "|"] = ","
    sheets: list[str] = Field(default_factory=list, max_length=20)
    shape: Literal["transactions", "basket_long", "basket_list"] = "transactions"
    basket_column: str | None = None
    item_separator: Literal["|", ";", ","] = "|"


class MappingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    columns: dict[str, str | None] = Field(default_factory=dict, max_length=13)
    order_boundary: Literal["order_id", "basket_id", "row_basket", "unavailable"]
    amount_mode: Literal["none", "line_amount", "quantity_unit_price", "order_amount"]
    currency_constant: str | None = Field(default=None, max_length=3)
    quantity_unit: str = Field(default="", max_length=64)
    time_format: str | None = None
    timezone: str | None = None
    status_rule: Literal["unspecified", "all_forward", "uci_cancel_prefix", "status_column"]
    status_values: dict[str, Literal["forward", "cancelled", "return", "unknown"]] = Field(
        default_factory=dict, max_length=20
    )
    confirmed: bool = False

    @field_validator("columns")
    @classmethod
    def known_fields(cls, value):
        if set(value) - FIELDS.keys():
            raise ValueError("存在未知语义字段")
        values = [v for v in value.values() if v]
        if len(values) != len(set(values)):
            raise ValueError("同一原始列不能映射为不同含义")
        return value

    @field_validator("currency_constant")
    @classmethod
    def valid_currency(cls, value):
        if value is None or value == "":
            return None
        if len(value) != 3 or not value.isascii() or not value.isalpha():
            raise ValueError("币种应为三个英文字母")
        return value.upper()

    @field_validator("time_format")
    @classmethod
    def valid_format(cls, value):
        if value is not None and value not in TIME_FORMATS:
            raise ValueError("请选择明确的时间格式")
        return value

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        if value:
            try:
                ZoneInfo(value)
            except (ValueError, ZoneInfoNotFoundError) as exc:
                raise ValueError("请选择有效时区") from exc
        return value


class ConfirmImport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preview_token: str
    mapping: MappingInput


class ReviseMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    mapping: MappingInput


class SaveDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preview_token: str
    mapping: MappingInput
