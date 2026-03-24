"""
DTOs applicatifs pour le module rates.

Types pour la lecture payroll_config : lignes brutes et sortie groupée.
"""
from __future__ import annotations

from typing import Any, TypedDict


class PayrollConfigRow(TypedDict, total=False):
    """Une ligne brute de la table payroll_config (champs lus)."""

    config_key: str
    config_data: Any
    version: int | None
    last_checked_at: str | None
    is_active: bool | None
    created_at: str | None
    comment: str | None
    source_links: list[str] | None


class RateCategoryOutput(TypedDict):
    """Une catégorie de taux formatée pour la réponse API (comportement legacy)."""

    config_data: Any
    version: Any
    last_checked_at: Any
    comment: Any
    source_links: Any
