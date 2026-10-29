from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class Page(BaseModel, Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total: int
    total_pages: int


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="ignore")

    code: str
    message: str
    details: Any = None
    request_id: str | None = None


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    detail: str
    error: ErrorDetail


class MessageResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    ok: bool = Field(default=True)
    message: str = ""
