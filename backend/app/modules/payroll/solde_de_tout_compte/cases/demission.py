"""
Case 1: Démission - Solde de tout compte generation
"""

from typing import Dict, Any

from app.modules.payroll.solde_de_tout_compte.common import socle_commun
from app.modules.payroll.solde_de_tout_compte.common import pdf_helpers
from app.modules.payroll.solde_de_tout_compte.common.html_renderer import (
    amount_row,
    amounts_section,
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

    # === Préavis (spécifique démission) ===
    notice_period = exit_data.get("notice_period_days", 0)
    notice_indemnity_type = exit_data.get("notice_indemnity_type", "not_applicable")
    indemnite_preavis = indemnities.get("indemnite_preavis", {})
    montant_preavis = pdf_helpers.safe_float(indemnite_preavis.get("montant", 0))
    is_gross_misconduct = exit_data.get("is_gross_misconduct", False)

    if notice_period > 0 and not is_gross_misconduct:
        if notice_indemnity_type == "waived" or montant_preavis == 0:
            preavis_text = (
                f"Préavis de {notice_period} jours exécuté — "
                "salaire inclus dans les rémunérations"
            )
        else:
            preavis_text = f"Préavis de {notice_period} jours — dispense d'exécution"
    elif is_gross_misconduct:
        preavis_text = "Aucun préavis (faute grave)"
    else:
        preavis_text = (
            "Aucun préavis"
            if notice_period == 0
            else f"Préavis de {notice_period} jours"
        )

    if notice_indemnity_type == "paid" and montant_preavis > 0:
        preavis_text_comp = "Dispense d'exécution — indemnité compensatrice"
    else:
        preavis_text_comp = "Non applicable (préavis exécuté ou non prévu)"

    preavis_section = amounts_section(
        "PRÉAVIS",
        [
            amount_row("Préavis", preavis_text, None),
            amount_row(
                "Indemnité compensatrice de préavis",
                preavis_text_comp,
                montant_preavis if montant_preavis > 0 else None,
            ),
        ],
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
