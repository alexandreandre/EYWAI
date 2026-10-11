"""Bruts des trois bulletins qui précèdent un arrêt (salaire de base des IJ).

Le salaire journalier de base des IJ maladie est égal aux trois derniers
salaires bruts ÷ 91,25 (CSS R323-4) : ceux des trois mois civils qui précèdent
le mois du début de l'arrêt. Ils se lisent sur les bulletins enregistrés, ceux
de Martine comme ceux repris de l'ancien logiciel. Lecture seule.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Optional

logger = logging.getLogger(__name__)


def mois_de_reference(debut_arret: date) -> list[tuple[int, int]]:
    """Les trois mois (année, mois) qui précèdent le mois du début de l'arrêt."""
    mois = []
    annee, m = debut_arret.year, debut_arret.month
    for _ in range(3):
        annee, m = (annee, m - 1) if m > 1 else (annee - 1, 12)
        mois.append((annee, m))
    return list(reversed(mois))


def salaires_bruts_de_reference(
    employee_id: str, debut_arret: date, *, client: Any = None
) -> list[Optional[float]]:
    """Brut de chacun des trois mois de référence, None pour un mois sans bulletin."""
    if client is None:
        from app.core.database import supabase as client
    mois = mois_de_reference(debut_arret)
    lignes = (
        client.table("payslips")
        .select("year, month, salaire_brut:payslip_data->salaire_brut")
        .eq("employee_id", employee_id)
        .in_("year", sorted({a for a, _ in mois}))
        .execute()
        .data
    ) or []
    bruts: dict[tuple[int, int], float] = {}
    for ligne in lignes:
        try:
            cle = (int(ligne.get("year")), int(ligne.get("month")))
            bruts[cle] = float(ligne.get("salaire_brut"))
        except (TypeError, ValueError):
            continue
    return [bruts.get(cle) for cle in mois]


def poser_salaires_de_reference(arret_data: dict[str, Any], employee_id: Any) -> None:
    """Pose sur l'arrêt les bruts des trois mois qui précèdent son début.

    Si la lecture échoue, l'estimation des IJSS retombe sur le salaire de base
    du contrat, et le journal le dit.
    """
    if not employee_id or arret_data.get("salaires_bruts_reference") is not None:
        return
    try:
        debut = date.fromisoformat(str(arret_data.get("date_debut"))[:10])
    except ValueError:
        return
    try:
        arret_data["salaires_bruts_reference"] = salaires_bruts_de_reference(
            str(employee_id), debut
        )
    except Exception:
        logger.warning(
            "Bruts de référence des IJSS non lus (salarié %s) : estimation sur le salaire de base",
            employee_id,
            exc_info=True,
        )


__all__ = [
    "mois_de_reference",
    "poser_salaires_de_reference",
    "salaires_bruts_de_reference",
]
