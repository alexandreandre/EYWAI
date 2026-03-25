"""
Utilitaires génériques pour les dates (ISO, parsing).

Sans logique métier ; wrappers évidents pour réutilisation.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional


def parse_iso_date(value: str | None) -> Optional[date]:
    """Parse une chaîne ISO (YYYY-MM-DD) en date ; retourne None si invalide."""
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value.strip()[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def format_iso_date(d: date | datetime | None) -> str | None:
    """Format une date/datetime en ISO YYYY-MM-DD."""
    if d is None:
        return None
    if isinstance(d, datetime):
        return d.date().isoformat()
    return d.isoformat()
