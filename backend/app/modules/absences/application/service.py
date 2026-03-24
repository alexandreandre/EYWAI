"""
Orchestration partagée du module absences.

Délégation vers infrastructure et domain. Aucune logique DB ni FastAPI ici.
"""
from __future__ import annotations

from app.modules.absences.infrastructure.queries import resolve_employee_id_for_user as _resolve


def resolve_employee_id_for_user(user_id: str) -> str | None:
    """Résout l'ID employé à partir de l'ID utilisateur (délégation infrastructure)."""
    return _resolve(user_id)
