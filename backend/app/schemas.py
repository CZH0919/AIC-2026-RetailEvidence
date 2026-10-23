import unicodedata
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ProjectColor = Literal["teal", "blue", "amber", "plum"]


def name_key(name: str) -> str:
    return unicodedata.normalize("NFKC", name).casefold()


class ProjectInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=64)
    description: str = Field(default="", max_length=500)
    color: ProjectColor = "teal"

    @field_validator("name", "description", mode="before")
    @classmethod
    def clean_text(cls, value):
        if not isinstance(value, str):
            raise ValueError("请输入文字")
        value = value.strip()
        if any(unicodedata.category(c) == "Cc" and c not in "\n\t" for c in value):
            raise ValueError("请移除不可见的控制字符")
        return value

    @field_validator("name")
    @classmethod
    def single_line_name(cls, value: str) -> str:
        if "\n" in value or "\t" in value or not name_key(value).strip():
            raise ValueError("项目名称应为一行非空文字")
        return value


class ProjectUpdate(ProjectInput):
    revision: int = Field(ge=1)


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    color: ProjectColor
    created_at: str
    updated_at: str
    revision: int


class ProjectList(BaseModel):
    items: list[ProjectRead]
    total: int
    limit: int
    offset: int
