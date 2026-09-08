"""
Fin de contrat à durée déterminée — solde de tout compte.

Particularité : l'indemnité de fin de contrat (précarité, art. L1243-8) est
VERSÉE SUR LE BULLETIN du dernier mois du CDD (moteur de brut) — elle figure
ici pour information, sans être ajoutée aux totaux du STC (sinon double
versement). L'ICCP, elle, est bien portée par le STC (arbitrage
maintien / 1/10e / L1243-8).
"""

from typing import Any, Dict

from app.modules.payroll.solde_de_tout_compte.common import pdf_helpers, socle_commun
from app.modules.payroll.solde_de_tout_compte.common.html_renderer import (
    amount_row,
    amounts_section,
    render_solde_tout_compte_html,
)


def generate_fin_cdd_solde(
    styles: Dict,
    employee_data: Dict[str, Any],
    company_data: Dict[str, Any],
    exit_data: Dict[str, Any],
    indemnities: Dict[str, Any],
    supabase_client=None,
) -> bytes:
    """Génère le PDF de solde de tout compte pour une fin de CDD."""
    # === Rémunérations acquises ===
    remun_section, total_brut_remun, total_cotisations_remun, total_net_remun = (
        socle_commun.compute_remunerations_section(
            employee_data,
            exit_data,
            employee_id=employee_data.get("id"),
            supabase_client=supabase_client,
        )
    )

    # === Indemnité de fin de contrat (précarité) — informative ===
    indemnite_precarite = indemnities.get("indemnite_precarite") or {}
    montant_precarite = pdf_helpers.safe_float(indemnite_precarite.get("montant", 0))
    precarite_section = amounts_section(
        "INDEMNITÉ DE FIN DE CONTRAT",
        [
            amount_row(
                "Indemnité de fin de contrat (art. L1243-8)",
                (
                    "10 % des rémunérations brutes du contrat — versée sur le "
                    "bulletin du dernier mois du CDD (rappel informatif, non "
                    "cumulée aux totaux ci-dessous)"
                ),
                montant_precarite if montant_precarite > 0 else None,
            ),
        ],
    )

    # === Congés payés (ICCP, portée par le STC) ===
    conges_section, montant_conges = socle_commun.compute_conges_section(indemnities)

    # === Sections génériques ===
    autres_section = socle_commun.compute_autres_regularisations_section()
    retenues_section = socle_commun.compute_retenues_section()

    # === Totaux — SANS la précarité (déjà au bulletin) ===
    total_brut_final = total_brut_remun + montant_conges
    total_cotisations_final = total_cotisations_remun
    total_net_final = total_net_remun + montant_conges

    return render_solde_tout_compte_html(
        employee_data,
        company_data,
        exit_data,
        motif_label="fin de contrat à durée déterminée",
        sections=[
            remun_section,
            precarite_section,
            conges_section,
            autres_section,
            retenues_section,
        ],
        total_brut=total_brut_final,
        total_cotisations=total_cotisations_final,
        total_net=total_net_final,
        specific_mention=(
            "Fin du contrat à durée déterminée à son terme (art. L1243-8 : "
            "l'indemnité de fin de contrat est versée avec le bulletin du "
            "dernier mois du contrat)."
        ),
    )
