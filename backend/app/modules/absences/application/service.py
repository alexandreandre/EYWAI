"""
Orchestration partagée du module absences.

Délégation vers la résolution employé canonique (multi-entreprise).
"""

from __future__ import annotations

from typing import Optional

from app.shared.employee_resolution import resolve_employee_id_for_user_account


def resolve_employee_id_for_user(
    user_id: str, company_id: str | None = None
) -> Optional[str]:
    """Résout employees.id pour un compte dans l'entreprise active."""
    if not company_id:
        return None
    return resolve_employee_id_for_user_account(str(user_id), str(company_id))
