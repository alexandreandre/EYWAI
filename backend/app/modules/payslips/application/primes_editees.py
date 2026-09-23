"""Écrire dans les variables du mois les primes éditées sur un bulletin.

Le calcul de ce qui a changé est pur (`domain.primes_editees`) ; ce module fait
les écritures dans `monthly_inputs`. La vérification d'appartenance est
séparée pour être faite **avant** d'enregistrer le bulletin : un identifiant
d'une autre fiche ne doit laisser aucune trace.
"""

from __future__ import annotations

import logging

from app.core.database import supabase
from app.modules.payslips.application.dto import PayslipBadRequestError
from app.modules.payslips.domain.primes_editees import DiffPrimes

logger = logging.getLogger(__name__)

MESSAGE_SAISIE_INCONNUE = (
    "Cette prime ne correspond à aucune variable du mois de ce bulletin : "
    "rechargez le bulletin avant de la modifier."
)


def verifier_appartenance(
    ids: set[str], *, employee_id: str, company_id: str, year: int, month: int
) -> None:
    """Chaque id doit être une saisie de ce salarié, de cette société, de ce mois."""
    if not ids:
        return
    r = (
        supabase.table("monthly_inputs")
        .select("id")
        .in_("id", sorted(ids))
        .match(
            {
                "employee_id": employee_id,
                "company_id": str(company_id),
                "year": year,
                "month": month,
            }
        )
        .execute()
    )
    connus = {str(row["id"]) for row in r.data or []}
    if ids - connus:
        raise PayslipBadRequestError(MESSAGE_SAISIE_INCONNUE)


def appliquer_primes_editees(
    diff: DiffPrimes, *, employee_id: str, company_id: str, year: int, month: int
) -> None:
    """Insère les primes ajoutées, corrige les montants, retire les primes supprimées."""
    base = {
        "employee_id": employee_id,
        "company_id": str(company_id),
        "year": year,
        "month": month,
    }
    if diff.ajoutees:
        supabase.table("monthly_inputs").insert([{**base, **p} for p in diff.ajoutees]).execute()
    for saisie_id, montant in diff.modifiees:
        supabase.table("monthly_inputs").update({"amount": montant}).eq("id", saisie_id).execute()
    for saisie_id in diff.retirees:
        supabase.table("monthly_inputs").delete().eq("id", saisie_id).execute()
    logger.info(
        "[edition] Primes du bulletin %s/%s de %s : %d ajoutée(s), %d corrigée(s), %d retirée(s).",
        month,
        year,
        employee_id,
        len(diff.ajoutees),
        len(diff.modifiees),
        len(diff.retirees),
    )
