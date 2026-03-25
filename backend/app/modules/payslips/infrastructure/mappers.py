"""
Mappers payslips : conversion dict/BDD <-> détail bulletin, listes.

Pas de FastAPI ; logique de construction des réponses côté infrastructure.
"""

from __future__ import annotations

from typing import Any


def build_payslip_detail(
    row: dict[str, Any],
    signed_url: str,
    cumuls: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Construit le dict détail bulletin à partir de la ligne BDD, URL signée et cumuls.
    Comportement identique au legacy (champs url, cumuls ajoutés).
    """
    out = dict(row)
    out["url"] = signed_url
    out["cumuls"] = cumuls
    return out


def row_to_payslip_detail(row: dict[str, Any]) -> dict[str, Any]:
    """Ligne BDD -> dict détail (copie simple, sans enrichissement)."""
    return dict(row)
