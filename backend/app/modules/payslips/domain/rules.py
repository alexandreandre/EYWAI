"""
Règles métier pures du domaine payslips.

Pas d'I/O, pas de dépendances infrastructure. Utilisées par l'application
pour autorisation (qui peut voir/éditer/restaurer) et validation.
"""

from __future__ import annotations

from typing import Any, Callable


from app.shared.domain.employment_rules import is_forfait_jour as is_forfait_jour


def can_view_payslip(
    payslip: dict[str, Any],
    user_id: str,
    is_platform_admin: bool,
    has_rh_access_in_company: Callable[[str], bool],
    active_company_id: str | None,
    resolved_employee_id: str | None = None,
) -> bool:
    """
    L'utilisateur peut consulter le bulletin s'il est l'employé concerné,
    ou RH/Admin de l'entreprise du bulletin, ou super admin.

    has_rh_access_in_company(company_id) -> bool.
    resolved_employee_id : fiche employees.id liée au compte (user_id sur employees).
    """
    employee_id = payslip.get("employee_id")
    if employee_id == user_id:
        return True
    if resolved_employee_id and employee_id == resolved_employee_id:
        return True
    if is_platform_admin:
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
    is_platform_admin: bool,
    has_rh_access_in_company: Callable[[str], bool],
    active_company_id: str | None,
) -> bool:
    """
    Édition / restauration : RH ou Admin de l'entreprise du bulletin, ou super admin.
    Même entreprise active (sauf super admin).
    """
    if is_platform_admin:
        return True
    company_id = payslip.get("company_id")
    if not company_id:
        return False
    if not has_rh_access_in_company(company_id):
        return False
    if active_company_id is not None and active_company_id != company_id:
        return False
    return True
