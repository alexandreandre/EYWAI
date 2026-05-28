"""Façade application pour le router absences (évite imports infrastructure)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.modules.absences.application.service import resolve_employee_id_for_user
from app.modules.absences.infrastructure.queries import get_employee_company_id
from app.modules.absences.infrastructure.repository import absence_repository


def get_absence_by_id(request_id: str) -> Optional[Dict[str, Any]]:
    return absence_repository.get_by_id(request_id)


def update_absence(request_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    return absence_repository.update(request_id, patch)


def get_team_manager_employee_id(employee_id: str) -> Optional[str]:
    return absence_repository.get_team_manager_employee_id_for_employee(employee_id)


def list_pending_manager_approval(company_id: str) -> List[Dict[str, Any]]:
    return absence_repository.get_pending_manager_approval(company_id)


def list_employee_ids_managed_by_manager(
    manager_employee_id: str, company_id: str
) -> List[str]:
    return absence_repository.get_employee_ids_managed_by_manager(
        manager_employee_id, company_id
    )


def approve_absence_by_manager(
    absence_id: str,
    manager_employee_id: str,
    company_id: str,
    *,
    comment: Optional[str] = None,
) -> Dict[str, Any]:
    return absence_repository.approve_by_manager(
        absence_id, manager_employee_id, company_id, comment=comment
    )


def employee_company_id(employee_id: str) -> Optional[str]:
    return get_employee_company_id(employee_id)


__all__ = [
    "resolve_employee_id_for_user",
    "get_absence_by_id",
    "update_absence",
    "get_team_manager_employee_id",
    "list_pending_manager_approval",
    "list_employee_ids_managed_by_manager",
    "approve_absence_by_manager",
    "employee_company_id",
]
