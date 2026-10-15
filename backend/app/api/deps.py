from dataclasses import dataclass
from typing import Literal
from fastapi import Query


@dataclass
class Pagination:
    page: int = Query(default=1, ge=1)
    page_size: int = Query(default=20, ge=1, le=100)
    search: str = Query(default="", max_length=200)
    sort: Literal["name", "title", "created_at"] = "created_at"
    direction: Literal["asc", "desc"] = "desc"

    def apply(self, query, model, search_column=None):
        if self.search and search_column is not None:
            query = query.where(search_column.ilike("%" + self.search.replace("%", "\\%").replace("_", "\\_") + "%", escape="\\"))
        column = getattr(model, self.sort, model.created_at)
        return query.order_by(column.asc() if self.direction == "asc" else column.desc(), model.id)
