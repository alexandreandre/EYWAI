"""
Règles métier pures du module schedules (forfait jour, normalisation calendrier).

Cible de migration : logique actuellement dans api/routers/schedules.py
(is_forfait_jour, normalize_planned_calendar_for_forfait_jour,
normalize_actual_hours_for_forfait_jour). Aucune I/O, pas de dépendance FastAPI/DB.
"""

from typing import Any, Dict, List


from app.shared.domain.absence_calendar import (
    ABSENCE_CALENDAR_TYPES,
    SERVER_OWNED_ABSENCE_KEYS,
    strip_server_owned_keys,
)
from app.shared.domain.employment_rules import is_forfait_jour as is_forfait_jour


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


def merge_planned_entries(
    existing: List[Dict[str, Any]] | None,
    incoming: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Fusionne le calendrier entrant sur le calendrier stocké, jour par jour.

    Le payload d'un client ne porte souvent que ``jour``/``type``/
    ``heures_prevues`` : remplacer le mois effacerait les métadonnées
    d'absence (nature d'arrêt, subrogation, historique) posées par la
    validation d'absence. On part donc de l'entrée stockée et on superpose
    uniquement les champs fournis.

    Les clés de ``SERVER_OWNED_ABSENCE_KEYS`` ne sont **jamais** reprises du
    payload : elles ne viennent que de l'entrée stockée. En contrepartie, un
    jour dont le type résultant n'est plus un type d'absence les perd : sans
    cela il garderait ``origine="absence"`` et resterait gelé à vie contre les
    régénérations, sans aucun moyen de le débloquer depuis l'interface.
    """
    par_jour = {
        e["jour"]: dict(e) for e in (existing or []) if e.get("jour") is not None
    }
    fusionnes: List[Dict[str, Any]] = []
    for entree in incoming:
        jour = entree.get("jour")
        base = dict(par_jour.get(jour, {}))
        for cle, valeur in entree.items():
            if cle in SERVER_OWNED_ABSENCE_KEYS:
                continue
            if valeur is not None or cle in base:
                base[cle] = valeur
        if base.get("type") not in ABSENCE_CALENDAR_TYPES:
            strip_server_owned_keys(base)
        fusionnes.append(base)
    return fusionnes


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
