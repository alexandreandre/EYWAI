"""
Règles métier du domaine scraping.

Logique pure sans dépendance à l'infrastructure ni à FastAPI.
"""
from __future__ import annotations

from typing import Any, Dict, Optional


def can_execute_source(source_data: dict) -> bool:
    """
    Une source peut être exécutée si elle est active.
    À enrichir selon les règles métier (dépendances, etc.).
    """
    return bool(source_data.get("is_active"))


def require_source_for_execution(source_data: Optional[Dict[str, Any]]) -> None:
    """
    Lève ValueError si la source est absente ou désactivée (exécution interdite).
    À appeler après get_source_by_key ; messages identiques au legacy.
    """
    if source_data is None:
        raise ValueError("Source non trouvée")
    if not can_execute_source(source_data):
        raise ValueError("Cette source est désactivée")


def validate_schedule_create(
    schedule_type: str,
    cron_expression: Optional[str],
    interval_days: Optional[int],
) -> None:
    """
    Valide les champs requis pour la création d'une planification.
    Lève ValueError avec le message legacy si invalide.
    """
    if schedule_type == "cron" and not cron_expression:
        raise ValueError("Expression cron requise")
    if schedule_type == "interval" and not interval_days:
        raise ValueError("Intervalle en jours requis")


def validate_schedule_update(update_data: Dict[str, Any]) -> None:
    """
    Valide qu'il y a au moins un champ à mettre à jour.
    Lève ValueError si update_data est vide.
    """
    if not update_data:
        raise ValueError("Aucune donnée à mettre à jour")
