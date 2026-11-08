"""Les lignes d'un bulletin et ce qui s'y corrige, pour la carte « Corriger une ligne »."""

from __future__ import annotations

from typing import Any

from app.core.database import supabase
from app.shared.cle_du_bulletin import du_contrat
from app.modules.payroll.engine.corrections_du_bulletin import (
    corrections_du_bulletin,
    blocs_a_la_source,
    corrections_en_attente_du_bulletin,
    lignes_corrigeables,
)
from app.modules.payroll.engine.corrections_manuelles import regularisations_du_bulletin
from app.modules.payslips.application.dto import PayslipNotFoundError

_CHAMPS_EN_ATTENTE = ("saisie_id", "ligne", "libelle", "motif", "raison")


RAISON_SAISIE_REFUSEE = (
    "Enregistrée, mais le dernier recalcul l'a refusée : elle n'est pas sur le "
    "bulletin. Retirez-la ou corrigez son montant pour le débloquer."
)


def _saisies_de_correction(bulletin: dict[str, Any]) -> list[dict[str, Any]]:
    """Les corrections et régularisations enregistrées pour ce bulletin, sur ses variables."""
    if not bulletin.get("employee_id"):
        return []
    requete = (
        supabase.table("monthly_inputs")
        .select("id, correction_ligne")
        .match(
            {
                "employee_id": str(bulletin["employee_id"]),
                "year": int(bulletin["year"]),
                "month": int(bulletin["month"]),
            }
        )
    )
    reponse = du_contrat(requete, bulletin.get("contract_period_id")).execute()
    lignes = reponse.data if reponse and isinstance(reponse.data, list) else []
    return [l for l in lignes if isinstance(l.get("correction_ligne"), dict)]


def _non_portees(bulletin: dict[str, Any], donnees: dict[str, Any], deja: set[str]) -> list[dict[str, Any]]:
    """Les saisies que le bulletin ne porte pas : un recalcul refusé les a laissées.

    Le bulletin n'étant pas recalculé, seule la table des variables les connaît.
    Sans cette lecture, personne ne pourrait les retirer.
    """
    portees = set(corrections_du_bulletin(donnees)) | set(regularisations_du_bulletin(donnees)) | deja
    sortie = []
    for saisie in _saisies_de_correction(bulletin):
        identifiant = str(saisie.get("id") or "")
        if not identifiant or identifiant in portees:
            continue
        correction = saisie["correction_ligne"]
        sortie.append(
            {
                "saisie_id": identifiant,
                "ligne": str(correction.get("ligne") or correction.get("coti_id") or ""),
                "libelle": str(correction.get("libelle") or ""),
                "motif": str(correction.get("motif") or ""),
                "raison": RAISON_SAISIE_REFUSEE,
            }
        )
    return sortie


def lire_lignes_corrigeables(payslip_id: str) -> dict[str, Any]:
    reponse = (
        supabase.table("payslips")
        .select("payslip_data, employee_id, year, month, contract_period_id")
        .eq("id", payslip_id)
        .maybe_single()
        .execute()
    )
    if not reponse or not reponse.data:
        raise PayslipNotFoundError("Bulletin non trouvé")
    donnees = reponse.data.get("payslip_data") or {}
    en_attente = [
        {cle: entree.get(cle) for cle in _CHAMPS_EN_ATTENTE}
        for entree in corrections_en_attente_du_bulletin(donnees)
    ]
    connues = {str(e.get("saisie_id")) for e in en_attente if e.get("saisie_id")}
    return {
        "lignes": [ligne.en_dict() for ligne in lignes_corrigeables(donnees)],
        "en_attente": en_attente + _non_portees(reponse.data, donnees, connues),
        "a_la_source": blocs_a_la_source(donnees),
    }
