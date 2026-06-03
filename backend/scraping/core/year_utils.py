"""Année courante et templates d'URL."""

from __future__ import annotations

from datetime import datetime


def current_year() -> int:
    return datetime.now().year


def legisocial_url(template: str, year: int | None = None) -> str:
    """template doit contenir {year}."""
    y = year if year is not None else current_year()
    return template.format(year=y)


def fetch_years_fallback() -> list[int]:
    """Année courante puis N-1 (pages LegiSocial pas encore publiées)."""
    y = current_year()
    return [y, y - 1]
