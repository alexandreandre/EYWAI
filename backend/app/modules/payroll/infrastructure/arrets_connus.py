"""Les arrêts d'un salarié, lus aux calendriers : ce qu'une demande peut prolonger.

Chaque jour d'arrêt porte les bornes de sa demande (`date_debut_arret_reel`,
`date_fin_arret_reel`). Le bulletin et l'aperçu « Maintien & subrogation »
lisent les mêmes, pour dire la même chose d'une prolongation : l'année du
bulletin jusqu'à son mois, et l'année d'avant (un arrêt de décembre prolongé
en janvier).
"""

from __future__ import annotations

from typing import Any


def arrets_connus_du_salarie(employee_id: str, annee: int, mois: int) -> list[dict[str, str]]:
    """[{debut, fin, type}] des arrêts lus aux calendriers, de l'année d'avant au mois."""
    from app.core.database import supabase

    lignes = (
        supabase.table("employee_schedules")
        .select("year, month, planned_calendar")
        .eq("employee_id", employee_id)
        .gte("year", annee - 1)
        .lte("year", annee)
        .execute()
        .data
    ) or []
    arrets: dict[tuple[str, str], str] = {}
    for ligne in lignes:
        if int(ligne.get("year") or 0) == annee and int(ligne.get("month") or 0) > mois:
            continue
        calendrier: Any = (ligne.get("planned_calendar") or {}).get("calendrier_prevu") or []
        for jour in calendrier if isinstance(calendrier, list) else []:
            debut = (jour or {}).get("date_debut_arret_reel")
            if not debut:
                continue
            fin = jour.get("date_fin_arret_reel") or debut
            arrets.setdefault(
                (str(debut)[:10], str(fin)[:10]), str(jour.get("arret_type") or "maladie")
            )
    return [
        {"debut": debut, "fin": fin, "type": type_arret}
        for (debut, fin), type_arret in sorted(arrets.items())
    ]


__all__ = ["arrets_connus_du_salarie"]
