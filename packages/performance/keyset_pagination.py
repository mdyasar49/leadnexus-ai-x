"""
LeadNexus AI X - Phase 31: Enterprise Performance Engineering
Keyset Pagination: Zero-offset cursor pagination for hyper-scale database tables.
"""

import base64
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Query


@dataclass
class CursorPage:
    items: List[Any]
    next_cursor: Optional[str]
    has_next_page: bool
    page_size: int


class KeysetPaginationEngine:
    """Provides high-throughput cursor pagination without expensive SQL OFFSET scans."""

    @classmethod
    def encode_cursor(cls, id_val: str, sort_val: Optional[Any] = None) -> str:
        data = {"id": str(id_val), "sort": sort_val}
        raw_json = json.dumps(data)
        return base64.urlsafe_b64encode(raw_json.encode("utf-8")).decode("utf-8")

    @classmethod
    def decode_cursor(cls, cursor_str: str) -> Tuple[Optional[str], Optional[Any]]:
        try:
            raw_json = base64.urlsafe_b64decode(cursor_str.encode("utf-8")).decode("utf-8")
            data = json.loads(raw_json)
            return data.get("id"), data.get("sort")
        except Exception:
            return None, None

    @classmethod
    def paginate(
        cls,
        query: Query,
        model_cls: Any,
        cursor: Optional[str] = None,
        limit: int = 50,
        sort_field_name: str = "id",
        ascending: bool = True,
    ) -> CursorPage:
        sort_col = getattr(model_cls, sort_field_name)
        id_col = getattr(model_cls, "id")

        if cursor:
            last_id, last_sort = cls.decode_cursor(cursor)
            if last_id is not None:
                if ascending:
                    if sort_field_name == "id":
                        query = query.filter(id_col > last_id)
                    else:
                        query = query.filter(
                            (sort_col > last_sort) | ((sort_col == last_sort) & (id_col > last_id))
                        )
                else:
                    if sort_field_name == "id":
                        query = query.filter(id_col < last_id)
                    else:
                        query = query.filter(
                            (sort_col < last_sort) | ((sort_col == last_sort) & (id_col < last_id))
                        )

        # Ordering
        if ascending:
            query = query.order_by(sort_col.asc(), id_col.asc())
        else:
            query = query.order_by(sort_col.desc(), id_col.desc())

        # Fetch limit + 1 to detect if next page exists
        results = query.limit(limit + 1).all()

        has_next_page = len(results) > limit
        items = results[:limit]

        next_cursor = None
        if has_next_page and items:
            last_item = items[-1]
            last_id_val = getattr(last_item, "id")
            last_sort_val = getattr(last_item, sort_field_name) if sort_field_name != "id" else None
            next_cursor = cls.encode_cursor(last_id_val, last_sort_val)

        return CursorPage(
            items=items,
            next_cursor=next_cursor,
            has_next_page=has_next_page,
            page_size=len(items),
        )

