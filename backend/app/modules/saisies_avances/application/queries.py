"""
Requêtes (lecture) du module saisies_avances.

Chaque requête délègue au service. Le router (lors de la migration) appellera
ces fonctions et convertira les exceptions applicatives en HTTPException.
"""
from decimal import Decimal
from typing import Any, List, Optional

from . import service


def get_salary_seizures(
    employee_id: Optional[str] = None,
    status: Optional[str] = None,
) -> List[Any]:
    """Liste des saisies avec filtres (enrichie employee_name)."""
    return service.get_salary_seizures(employee_id=employee_id, status=status)


def get_salary_seizure(seizure_id: str) -> Any:
    """Détail d'une saisie."""
    return service.get_salary_seizure(seizure_id)


def get_employee_salary_seizures(employee_id: str) -> List[Any]:
    """Saisies d'un employé."""
    return service.get_employee_salary_seizures(employee_id)


def get_my_salary_advances(employee_id: str) -> List[Any]:
    """Avances de l'employé connecté."""
    return service.get_my_salary_advances(employee_id)


def get_my_advance_available(employee_id: str) -> Any:
    """Montant disponible pour une avance (employé)."""
    return service.get_my_advance_available(employee_id)


def get_salary_advances(
    employee_id: Optional[str] = None,
    status: Optional[str] = None,
) -> List[Any]:
    """Liste des avances avec filtres (enrichie employee_name, remaining_to_pay)."""
    return service.get_salary_advances(employee_id=employee_id, status=status)


def get_salary_advance(advance_id: str) -> Any:
    """Détail d'une avance."""
    return service.get_salary_advance(advance_id)


def get_employee_salary_advances(employee_id: str) -> List[Any]:
    """Avances d'un employé (hors 'me')."""
    return service.get_employee_salary_advances(employee_id)


def get_payslip_deductions(payslip_id: str) -> List[Any]:
    """Prélèvements appliqués sur un bulletin."""
    return service.get_payslip_deductions(payslip_id)


def get_payslip_advance_repayments(payslip_id: str) -> List[Any]:
    """Remboursements d'avances appliqués sur un bulletin."""
    return service.get_payslip_advance_repayments(payslip_id)


def get_advance_payments(advance_id: str) -> List[Any]:
    """Paiements d'une avance."""
    return service.get_advance_payments(advance_id)


def get_payment_proof_url(payment_id: str) -> str:
    """URL signée pour télécharger la preuve de paiement."""
    return service.get_payment_proof_url(payment_id)


def calculate_seizable(
    net_salary: Decimal, dependents_count: int = 0
) -> Any:
    """Calcule la quotité saisissable pour un salaire donné."""
    return service.calculate_seizable(net_salary, dependents_count)
