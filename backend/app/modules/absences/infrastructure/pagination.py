"""Lecture paginée — PostgREST tronque silencieusement à 1 000 lignes."""

from __future__ import annotations

from typing import Any, Callable

DEFAULT_PAGE_SIZE = 1000


def fetch_all_rows(
    fetch_page: Callable[[int, int], list[dict[str, Any]]],
    *,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> list[dict[str, Any]]:
    """Enchaîne les pages jusqu'à en obtenir une incomplète."""
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = fetch_page(offset, page_size)
        rows.extend(page)
        if len(page) < page_size:
            return rows
        offset += page_size
