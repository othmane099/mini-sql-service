from __future__ import annotations

import math

from pydantic import BaseModel


class PaginatedResponse[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int
    has_next: bool
    has_previous: bool

    @classmethod
    def build(
        cls, items: list[T], total: int, page: int, page_size: int
    ) -> PaginatedResponse[T]:
        pages = math.ceil(total / page_size) if page_size else 0
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
            has_next=page < pages,
            has_previous=page > 1,
        )
