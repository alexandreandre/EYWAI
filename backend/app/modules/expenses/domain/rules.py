"""
Règles métier du domaine expenses.

Règles pures : pas de FastAPI, pas d'I/O, pas de dépendance infrastructure.
Comportement aligné sur l'ancien router (statut initial, transitions autorisées).
"""
from typing import Optional

# Statut initial d'une nouvelle note de frais (comportement legacy)
INITIAL_EXPENSE_STATUS = "pending"

# Transitions autorisées : pending -> validated | rejected (comportement legacy)
_ALLOWED_TRANSITIONS = {
    ("pending", "validated"),
    ("pending", "rejected"),
}


def get_initial_expense_status() -> str:
    """Retourne le statut initial pour une note de frais créée."""
    return INITIAL_EXPENSE_STATUS


def validate_expense_status_transition(
    current_status: str, new_status: str
) -> Optional[str]:
    """
    Retourne None si la transition est autorisée, sinon un message d'erreur.
    Transitions autorisées : pending -> validated, pending -> rejected.
    Pour comportement strictement identique au legacy : la couche application
    peut choisir d'appeler ou non cette règle avant update.
    """
    if (current_status, new_status) in _ALLOWED_TRANSITIONS:
        return None
    if current_status == new_status:
        return None
    return (
        f"Transition de statut non autorisée : {current_status} -> {new_status}. "
        "Autorisées : pending -> validated, pending -> rejected."
    )


def is_valid_status_for_update(status: str) -> bool:
    """Indique si le statut est autorisé pour une mise à jour (validation/refus RH)."""
    return status in ("validated", "rejected")
