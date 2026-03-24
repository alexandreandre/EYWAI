"""
Règles métier pures du domaine payslips.

Pas d'I/O, pas de dépendances infrastructure. Utilisées par l'application
pour autorisation (qui peut voir/éditer/restaurer) et validation.
"""
from __future__ import annotations

from typing import Any, Callable


def is_forfait_jour(statut: str | None) -> bool:
    """
    Détecte si un employé est en forfait jour selon son statut.
    Règle métier pure (pas d'I/O).
    """
    if not statut:
        return False
    return "forfait jour" in statut.lower()


def can_view_payslip(
    payslip: dict[str, Any],
    user_id: str,
    is_super_admin: bool,
    has_rh_access_in_company: Callable[[str], bool],
    active_company_id: str | None,
) -> bool:
    """
    L'utilisateur peut consulter le bulletin s'il est l'employé concerné,
    ou RH/Admin de l'entreprise du bulletin, ou super admin.

    has_rh_access_in_company(company_id) -> bool.
    """
    if payslip.get("employee_id") == user_id:
        return True
    if is_super_admin:
        return True
    company_id = payslip.get("company_id")
    if not company_id:
        return False
    if not has_rh_access_in_company(company_id):
        return False
    if active_company_id is not None and active_company_id != company_id:
        return False
    return True


def can_edit_or_restore_payslip(
    payslip: dict[str, Any],
    is_super_admin: bool,
    has_rh_access_in_company: Callable[[str], bool],
    active_company_id: str | None,
) -> bool:
    """
    Édition / restauration : RH ou Admin de l'entreprise du bulletin, ou super admin.
    Même entreprise active (sauf super admin).
    """
    if is_super_admin:
        return True
    company_id = payslip.get("company_id")
    if not company_id:
        return False
    if not has_rh_access_in_company(company_id):
        return False
    if active_company_id is not None and active_company_id != company_id:
        return False
    return True
