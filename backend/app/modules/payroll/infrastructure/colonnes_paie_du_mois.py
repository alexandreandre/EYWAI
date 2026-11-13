"""Écriture des colonnes de paie (cumuls, événements) sur la ligne du mois d'un salarié.

Ces colonnes vivent dans `employee_schedules`, que le trigger `guard_calendar_edit`
protège tout entière pendant qu'une RH enregistre le calendrier du mois (PT409).
Elles ne sont pas des données du calendrier : rejouer la même écriture n'écrase
aucune saisie. On attend donc la fin de l'enregistrement (20 s au plus) plutôt que
de laisser un bulletin en base sans ses cumuls.
"""
from __future__ import annotations

from typing import Any

from app.core.calendar_write_context import relancer_si_calendrier_reserve

#: Seules colonnes que la paie écrit sur la ligne du mois. Jamais le calendrier lui-même.
COLONNES_PAIE = frozenset({"cumuls", "payroll_events", "updated_at"})


def ecrire_colonnes_paie_du_mois(
    supabase: Any, employee_id: str, year: int, month: int, valeurs: dict[str, Any]
) -> None:
    hors_paie = set(valeurs) - COLONNES_PAIE
    if hors_paie:
        raise ValueError(f"Colonnes hors paie refusées : {sorted(hors_paie)}")
    filtre = {"employee_id": employee_id, "year": year, "month": month}
    relancer_si_calendrier_reserve(
        lambda: supabase.table("employee_schedules").update(valeurs).match(filtre).execute()
    )
