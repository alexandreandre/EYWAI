"""
Queries (use cases en lecture) du module payslips.

Logique applicative : orchestration des lectures ; l'infrastructure exécute
les appels BDD et storage. Les routers n'ont plus la logique métier.
"""

from __future__ import annotations

from typing import Any

from app.modules.payslips.infrastructure.queries import (
    get_employee_payslips as _get_employee_payslips,
    get_my_payslips as _get_my_payslips,
    get_payslip_details as _get_payslip_details,
    get_payslip_history as _get_payslip_history,
)


def get_my_payslips(employee_id: str) -> list[dict[str, Any]]:
    """Liste des bulletins de l'employé connecté (avec net_a_payer, URLs signées)."""
    return _get_my_payslips(employee_id)


def get_employee_payslips(employee_id: str) -> list[dict[str, Any]]:
    """Liste des bulletins d'un employé (pour RH)."""
    return _get_employee_payslips(employee_id)


def get_payslip_details(payslip_id: str) -> dict[str, Any] | None:
    """Détail complet d'un bulletin (dont cumuls, edit_history, url signée)."""
    return _get_payslip_details(payslip_id)


def get_payslip_history(payslip_id: str) -> list[dict[str, Any]]:
    """Historique des modifications d'un bulletin."""
    return _get_payslip_history(payslip_id)
