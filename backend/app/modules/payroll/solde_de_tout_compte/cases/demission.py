"""
Case 1: Démission - Solde de tout compte generation
"""

from typing import Dict, Any

from app.modules.payroll.solde_de_tout_compte.common import socle_commun
from app.modules.payroll.solde_de_tout_compte.common.html_renderer import (
    render_solde_tout_compte_html,
)


def generate_demission_solde(
    styles: Dict,
    employee_data: Dict[str, Any],
    company_data: Dict[str, Any],
    exit_data: Dict[str, Any],
    indemnities: Dict[str, Any],
    supabase_client=None,
) -> bytes:
    """Génère le PDF de solde de tout compte pour une démission."""
    # === Rémunérations acquises ===
    remun_section, total_brut_remun, total_cotisations_remun, total_net_remun = (
        socle_commun.compute_remunerations_section(
            employee_data,
            exit_data,
            employee_id=employee_data.get("id"),
            supabase_client=supabase_client,
        )
    )

    # === Préavis (même phrase que le certificat et l'attestation) ===
    preavis_section, montant_preavis, _versee = socle_commun.compute_preavis_section(
        exit_data, indemnities
    )

    # === Congés payés ===
    conges_section, montant_conges = socle_commun.compute_conges_section(indemnities)

    # === Sections génériques ===
    autres_section = socle_commun.compute_autres_regularisations_section()
    retenues_section = socle_commun.compute_retenues_section()

    # === Totaux ===
    total_brut_final = total_brut_remun + montant_conges + montant_preavis
    total_cotisations_final = total_cotisations_remun
    total_net_final = total_net_remun + montant_conges + montant_preavis

    return render_solde_tout_compte_html(
        employee_data,
        company_data,
        exit_data,
        motif_label="démission",
        sections=[
            remun_section,
            preavis_section,
            conges_section,
            autres_section,
            retenues_section,
        ],
        total_brut=total_brut_final,
        total_cotisations=total_cotisations_final,
        total_net=total_net_final,
        specific_mention="Rupture du contrat de travail à l'initiative du salarié (démission).",
    )
