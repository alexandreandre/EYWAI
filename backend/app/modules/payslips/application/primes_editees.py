"""Écrire dans les variables du mois les primes éditées sur un bulletin.

Le calcul de ce qui a changé est pur (`domain.primes_editees`) ; ce module fait
les écritures dans `monthly_inputs`. La vérification d'appartenance est
séparée pour être faite **avant** d'enregistrer le bulletin : un identifiant
d'une autre fiche ne doit laisser aucune trace.
"""

from __future__ import annotations

import logging

from app.core.database import supabase
from app.modules.monthly_inputs.domain.rules import (
    RETRAIT_SAISIE_GENEREE,
    est_saisie_generee,
)
from app.modules.payslips.application.dto import PayslipBadRequestError
from app.modules.payslips.domain.primes_editees import DiffPrimes, prime_ajoutee_propre

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
    # `manual_override` : la génération automatique des variables ne repasse pas
    # derrière une prime posée ou corrigée depuis le bulletin.
    if diff.ajoutees:
        supabase.table("monthly_inputs").insert(
            [
                {**prime_ajoutee_propre(p), "amount": p["amount"], **base, "manual_override": True}
                for p in diff.ajoutees
            ]
        ).execute()
    for saisie_id, montant in diff.modifiees:
        supabase.table("monthly_inputs").update(
            {"amount": montant, "manual_override": True}
        ).eq("id", saisie_id).execute()
    # Une prime d'une règle automatique supprimée serait recréée par la
    # génération des variables, qui tourne avant chaque bulletin : elle passe
    # à 0, protégée, et le bulletin ne l'imprime plus.
    generees: set[str] = set()
    if diff.retirees:
        r = (
            supabase.table("monthly_inputs")
            .select("id, description")
            .in_("id", list(diff.retirees))
            .execute()
        )
        generees = {str(row["id"]) for row in r.data or [] if est_saisie_generee(row)}
    for saisie_id in diff.retirees:
        if saisie_id in generees:
            supabase.table("monthly_inputs").update(dict(RETRAIT_SAISIE_GENEREE)).eq(
                "id", saisie_id
            ).execute()
        else:
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
