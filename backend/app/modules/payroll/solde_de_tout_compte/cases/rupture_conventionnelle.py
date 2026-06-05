"""
Case 2: Rupture Conventionnelle - Solde de tout compte generation
"""

from typing import Dict, Any

from app.modules.payroll.solde_de_tout_compte.common import socle_commun
from app.modules.payroll.solde_de_tout_compte.common import pdf_helpers
from app.modules.payroll.solde_de_tout_compte.common.html_renderer import (
    amount_row,
    amounts_section,
    render_solde_tout_compte_html,
)


def generate_rupture_conventionnelle_solde(
    styles: Dict,
    employee_data: Dict[str, Any],
    company_data: Dict[str, Any],
    exit_data: Dict[str, Any],
    indemnities: Dict[str, Any],
    supabase_client=None,
) -> bytes:
    """Génère le PDF de solde de tout compte pour une rupture conventionnelle."""
    # === Rémunérations acquises ===
    remun_section, total_brut_remun, total_cotisations_remun, total_net_remun = (
        socle_commun.compute_remunerations_section(
            employee_data,
            exit_data,
            employee_id=employee_data.get("id"),
            supabase_client=supabase_client,
        )
    )

    # === Indemnité spécifique de rupture conventionnelle ===
    indemnite_rupture = indemnities.get("indemnite_rupture_conventionnelle", {})
    montant_rupture = pdf_helpers.safe_float(indemnite_rupture.get("montant_negocie", 0))
    montant_minimum = pdf_helpers.safe_float(indemnite_rupture.get("montant_minimum", 0))
    anciennete = pdf_helpers.safe_float(indemnities.get("anciennete_annees", 0))
    salaire_ref = pdf_helpers.safe_float(indemnities.get("salaire_reference", 0))

    detail_rupture = f"Ancienneté : {anciennete:.2f} ans"
    if salaire_ref > 0:
        detail_rupture += (
            f" | Salaire de référence : {pdf_helpers.format_currency(salaire_ref)}"
        )
    if montant_minimum > 0:
        detail_rupture += (
            f" | Minimum légal : {pdf_helpers.format_currency(montant_minimum)}"
        )
    if montant_rupture == 0:
        detail_rupture = "Montant non renseigné ou en attente de calcul"

    rupture_section = amounts_section(
        "INDEMNITÉ SPÉCIFIQUE DE RUPTURE CONVENTIONNELLE",
        [
            amount_row(
                "Indemnité spécifique de rupture conventionnelle",
                detail_rupture,
                montant_rupture if montant_rupture > 0 else None,
            )
        ],
    )

    # === Congés payés ===
    conges_section, montant_conges = socle_commun.compute_conges_section(indemnities)

    # === Sections génériques ===
    autres_section = socle_commun.compute_autres_regularisations_section()
    retenues_section = socle_commun.compute_retenues_section()

    # === Totaux ===
    total_brut_final = total_brut_remun + montant_rupture + montant_conges
    total_cotisations_final = total_cotisations_remun
    total_net_final = total_net_remun + montant_rupture + montant_conges

    return render_solde_tout_compte_html(
        employee_data,
        company_data,
        exit_data,
        motif_label="rupture conventionnelle",
        sections=[
            remun_section,
            rupture_section,
            conges_section,
            autres_section,
            retenues_section,
        ],
        total_brut=total_brut_final,
        total_cotisations=total_cotisations_final,
        total_net=total_net_final,
        specific_mention=(
            "Rupture du contrat de travail par rupture conventionnelle homologuée, "
            "conformément aux articles L1237-11 et suivants du Code du travail."
        ),
        articles="Articles D1234-7, L1234-20 et L1237-11 du Code du travail",
    )
