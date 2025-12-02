from math import ceil
from typing import Annotated, TypeVar, Generic, List

from pydantic import BaseModel, Field, computed_field

T = TypeVar("T", bound=BaseModel)


class PaginationParams(BaseModel):
    page: Annotated[int, Field(1, description="page number", ge=1)]
    page_size: Annotated[
        int, Field(30, description="Limit items per page", ge=1, le=100)
    ]

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


class PaginationResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int

    @computed_field
    @property
    def total_pages(self) -> int:
        return ceil(self.total / self.page_size) if self.page_size else 0

    @computed_field
    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @computed_field
    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @classmethod
    def create(
        cls, items: List[T], total: int, params: PaginationParams
    ) -> "PaginationResponse[T]":
        return PaginationResponse(
            items=items,
            total=total,
            page=params.page,
            page_size=params.page_size,
        )


class PaginationResults(Generic[T]):
    __slots__ = ("items", "total")

    def __init__(self, items: List[T], total: int) -> None:
        self.items = items
        self.total = total
