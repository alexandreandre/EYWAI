"""
Commandes du module saisies_avances.

Chaque commande délègue au service. Le router (lors de la migration) appellera
ces fonctions et convertira les exceptions applicatives en HTTPException.
"""

from typing import Any

from . import service
from .dto import UserContext


def create_salary_seizure(seizure_data: Any, created_by_id: Any) -> Any:
    """Crée une saisie sur salaire."""
    return service.create_salary_seizure(seizure_data, created_by_id)


def update_salary_seizure(seizure_id: str, update_data: Any) -> Any:
    """Met à jour une saisie."""
    return service.update_salary_seizure(seizure_id, update_data)


def delete_salary_seizure(seizure_id: str) -> None:
    """Supprime une saisie."""
    return service.delete_salary_seizure(seizure_id)


def create_salary_advance(advance_data: Any, ctx: UserContext) -> Any:
    """Crée une demande d'avance (employé ou RH)."""
    return service.create_salary_advance(advance_data, ctx)


def approve_salary_advance(advance_id: str, approved_by_id: Any) -> Any:
    """Approuve une avance."""
    return service.approve_salary_advance(advance_id, approved_by_id)


def reject_salary_advance(advance_id: str, rejection_reason: str) -> Any:
    """Rejette une avance."""
    return service.reject_salary_advance(advance_id, rejection_reason)


def get_payment_upload_url(filename: str, user_id: Any) -> Any:
    """Génère une URL signée pour upload de preuve de paiement."""
    return service.get_payment_upload_url(filename, user_id)


def create_advance_payment(payment_data: Any, created_by_id: Any) -> Any:
    """Crée un paiement d'avance (versement avec preuve)."""
    return service.create_advance_payment(payment_data, created_by_id)


def delete_advance_payment(payment_id: str) -> Any:
    """Supprime un paiement d'avance."""
    return service.delete_advance_payment(payment_id)
