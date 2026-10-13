"""
Repository repos_compensateur_credits.

Implémente l'accès persistance à la table repos_compensateur_credits.
Comportement identique à l'ancien code (upsert, lecture jours par employé/année).
"""

from __future__ import annotations
from app.core.logging import get_logger

from app.core.database import supabase
from app.modules.repos_compensateur.domain.entities import ReposCredit
from app.modules.repos_compensateur.infrastructure.mappers import credit_to_row


logger = get_logger("modules.repos_compensateur.infrastructure.repository")

def upsert_credit(credit: ReposCredit) -> bool:
    """
    Upsert une ligne dans repos_compensateur_credits.
    Retourne True si succès, False en cas d'erreur (log warning).
    """
    try:
        supabase.table("repos_compensateur_credits").upsert(
            credit_to_row(credit),
            on_conflict="employee_id,year,month,source",
        ).execute()
        return True
    except Exception as err:
        logger.warning(f'[WARNING] Upsert repos_credits failed for {credit.employee_id} {credit.year}-{credit.month}: {err}')
        return False


def upsert_credits(credits: list[ReposCredit]) -> bool:
    """Upsert de plusieurs lignes en une requête (les 12 mois d'un salarié, lot 43).

    Mêmes lignes et même clé de conflit que `upsert_credit`, ligne par ligne :
    un aller-retour vers la base au lieu de douze. True si l'écriture a réussi
    (rien à écrire compte pour une réussite), False sinon (log warning).
    """
    if not credits:
        return True
    try:
        supabase.table("repos_compensateur_credits").upsert(
            [credit_to_row(credit) for credit in credits],
            on_conflict="employee_id,year,month,source",
        ).execute()
        return True
    except Exception as err:
        premier = credits[0]
        logger.warning(
            f"[WARNING] Upsert repos_credits failed for {premier.employee_id} {premier.year} "
            f"({len(credits)} mois): {err}"
        )
        return False


def get_jours_by_employee_year(employee_ids: list[str], year: int) -> dict[str, float]:
    """
    Somme des jours repos_compensateur_credits par employee_id pour l'année.
    Comportement identique à l'ancienne query (soldes absences).
    """
    if not employee_ids:
        return {}
    credits_resp = (
        supabase.table("repos_compensateur_credits")
        .select("employee_id", "jours")
        .in_("employee_id", employee_ids)
        .eq("year", year)
        .execute()
    )
    result: dict[str, float] = {}
    for c in credits_resp.data or []:
        eid = c.get("employee_id")
        result[eid] = result.get(eid, 0.0) + float(c.get("jours", 0) or 0)
    return result
