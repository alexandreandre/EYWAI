"""
Mappers et helpers pour collective_agreements.

Sérialisation des dates pour la DB, pas de dépendance à FastAPI.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict


def serialize_dates(data: Dict[str, Any]) -> Dict[str, Any]:
    """Convertit les objets date/datetime en strings ISO pour la sérialisation JSON/DB."""
    result: Dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, (date, datetime)):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result


def add_signed_url_to_agreement(
    agreement: dict[str, Any], signed_url: str | None, path_key: str = "rules_pdf_path"
) -> None:
    """Ajoute rules_pdf_url à un dict agreement (modification in-place)."""
    if not signed_url:
        return
    if agreement.get(path_key):
        agreement["rules_pdf_url"] = signed_url
