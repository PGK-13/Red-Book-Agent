from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class BaseResponse(BaseModel, Generic[T]):
    """统一响应格式。"""

    code: int = 0
    message: str = "success"
    data: T | None = None


class ErrorResponse(BaseModel):
    code: int
    message: str
    data: None = None


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应（cursor 分页）。"""

    code: int = 0
    message: str = "success"
    data: "PaginatedData[T]"


class PaginatedData(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = None
    has_more: bool = False
