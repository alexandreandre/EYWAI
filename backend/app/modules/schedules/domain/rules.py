"""
Règles métier pures du module schedules (forfait jour, normalisation calendrier).

Cible de migration : logique actuellement dans api/routers/schedules.py
(is_forfait_jour, normalize_planned_calendar_for_forfait_jour,
normalize_actual_hours_for_forfait_jour). Aucune I/O, pas de dépendance FastAPI/DB.
"""
from typing import Any, Dict, List


def is_forfait_jour(statut: str | None) -> bool:
    """Détecte si un employé est en forfait jour selon son statut."""
    if not statut:
        return False
    return "forfait jour" in statut.lower()


def normalize_planned_calendar_for_forfait_jour(
    calendrier_prevu: List[Dict[str, Any]], employee_statut: str | None
) -> List[Dict[str, Any]]:
    """
    Normalise les valeurs heures_prevues pour les employés en forfait jour.
    Convertit les valeurs > 0 en 1, et les valeurs 0 ou null en 0.
    """
    if not is_forfait_jour(employee_statut):
        return calendrier_prevu

    normalized = []
    for entry in calendrier_prevu:
        normalized_entry = entry.copy()
        heures_prevues = entry.get("heures_prevues")

        if heures_prevues is None:
            normalized_entry["heures_prevues"] = 0
        elif isinstance(heures_prevues, (int, float)):
            normalized_entry["heures_prevues"] = 1 if heures_prevues > 0 else 0
        else:
            normalized_entry["heures_prevues"] = 0

        normalized.append(normalized_entry)

    return normalized


def normalize_actual_hours_for_forfait_jour(
    calendrier_reel: List[Dict[str, Any]], employee_statut: str | None
) -> List[Dict[str, Any]]:
    """
    Normalise les valeurs heures_faites pour les employés en forfait jour.
    Convertit les valeurs > 0 en 1, et les valeurs 0 ou null en 0.
    """
    if not is_forfait_jour(employee_statut):
        return calendrier_reel

    normalized = []
    for entry in calendrier_reel:
        normalized_entry = entry.copy()
        heures_faites = entry.get("heures_faites")

        if heures_faites is None:
            normalized_entry["heures_faites"] = 0
        elif isinstance(heures_faites, (int, float)):
            normalized_entry["heures_faites"] = 1 if heures_faites > 0 else 0
        else:
            normalized_entry["heures_faites"] = 0

        normalized.append(normalized_entry)

    return normalized
