"""
Case 3: Licenciement - Solde de tout compte generation
"""

from typing import Dict, Any

from app.modules.payroll.solde_de_tout_compte.common import socle_commun
from app.modules.payroll.solde_de_tout_compte.common import pdf_helpers
from app.modules.payroll.solde_de_tout_compte.common.html_renderer import (
    amount_row,
    amounts_section,
    render_solde_tout_compte_html,
)


def generate_licenciement_solde(
    styles: Dict,
    employee_data: Dict[str, Any],
    company_data: Dict[str, Any],
    exit_data: Dict[str, Any],
    indemnities: Dict[str, Any],
    supabase_client=None,
) -> bytes:
    """Génère le PDF de solde de tout compte pour un licenciement."""
    is_gross_misconduct = exit_data.get("is_gross_misconduct", False)

    motif_label = "licenciement (hors faute grave/lourde)"
    if is_gross_misconduct:
        motif_label = "licenciement pour faute grave/lourde"

    # === Rémunérations acquises ===
    remun_section, total_brut_remun, total_cotisations_remun, total_net_remun = (
        socle_commun.compute_remunerations_section(
            employee_data,
            exit_data,
            employee_id=employee_data.get("id"),
            supabase_client=supabase_client,
        )
    )

    # === Indemnité de licenciement ===
    indemnite_licenciement = indemnities.get("indemnite_licenciement", {})
    montant_licenciement = pdf_helpers.safe_float(
        indemnite_licenciement.get("montant", 0)
    )
    anciennete = pdf_helpers.safe_float(indemnities.get("anciennete_annees", 0))
    salaire_ref = pdf_helpers.safe_float(indemnities.get("salaire_reference", 0))

    base_retenue = "Non déterminée"
    if indemnite_licenciement.get("tranche1_annees"):
        base_retenue = "Légale (article L1234-9)"
    elif indemnite_licenciement.get("motif") == "Ancienneté < 8 mois":
        base_retenue = "Non applicable (ancienneté insuffisante)"

    detail_licenciement = f"Ancienneté : {anciennete:.2f} ans"
    if salaire_ref > 0:
        detail_licenciement += (
            f" | Salaire de référence : {pdf_helpers.format_currency(salaire_ref)}"
        )
    detail_licenciement += f" | Base : {base_retenue}"

    if is_gross_misconduct:
        detail_licenciement = "Faute grave/lourde — pas d'indemnité"
        montant_licenciement = 0.0
    elif montant_licenciement == 0:
        detail_licenciement = "Non applicable ou non renseigné"

    licenciement_section = amounts_section(
        "INDEMNITÉ DE LICENCIEMENT",
        [
            amount_row(
                "Indemnité de licenciement (légale / conventionnelle)",
                detail_licenciement,
                montant_licenciement if montant_licenciement > 0 else None,
            )
        ],
    )

    # === Préavis ===
    notice_period = exit_data.get("notice_period_days", 0)
    notice_indemnity_type = exit_data.get("notice_indemnity_type", "not_applicable")
    indemnite_preavis = indemnities.get("indemnite_preavis", {})
    montant_preavis = pdf_helpers.safe_float(indemnite_preavis.get("montant", 0))

    preavis_waived = False
    if is_gross_misconduct:
        preavis_text = "Aucun préavis (faute grave/lourde)"
    elif notice_period == 0:
        preavis_text = "Aucun préavis prévu"
    elif notice_indemnity_type == "waived" or (
        notice_indemnity_type != "paid" and montant_preavis == 0
    ):
        preavis_text = (
            f"Préavis de {notice_period} jours exécuté — "
            "salaire inclus dans les rémunérations"
        )
    elif notice_indemnity_type == "paid" and montant_preavis > 0:
        preavis_waived = True
        preavis_text = f"Préavis de {notice_period} jours — dispense d'exécution"
    else:
        preavis_text = f"Préavis de {notice_period} jours — statut non déterminé"

    preavis_section = amounts_section(
        "PRÉAVIS",
        [
            amount_row("Préavis", preavis_text, None),
            amount_row(
                "Indemnité compensatrice de préavis",
                "Dispense d'exécution — indemnité compensatrice"
                if preavis_waived
                else "Non applicable (préavis exécuté ou non prévu)",
                montant_preavis if montant_preavis > 0 else None,
            ),
        ],
    )

    # === Congés payés (avec ligne CP afférents au préavis) ===
    cp_preavis_text = "Non applicable ou non calculé"
    montant_cp_preavis = 0.0
    if preavis_waived and montant_preavis > 0:
        cp_preavis_text = "Congés payés afférents au préavis non exécuté"

    conges_section, montant_conges = socle_commun.compute_conges_section(
        indemnities,
        include_cp_preavis=True,
        cp_preavis_detail=cp_preavis_text,
        montant_cp_preavis=montant_cp_preavis,
    )

    # === Sections génériques ===
    autres_section = socle_commun.compute_autres_regularisations_section()
    retenues_section = socle_commun.compute_retenues_section()

    # === Totaux ===
    total_brut_final = (
        total_brut_remun
        + montant_licenciement
        + montant_preavis
        + montant_conges
        + montant_cp_preavis
    )
    total_cotisations_final = total_cotisations_remun
    total_net_final = (
        total_net_remun
        + montant_licenciement
        + montant_preavis
        + montant_conges
        + montant_cp_preavis
    )

    mention_licenciement = "Rupture du contrat par licenciement (hors faute grave/lourde)."
    if is_gross_misconduct:
        mention_licenciement = (
            "Rupture du contrat par licenciement pour faute grave/lourde."
        )

    return render_solde_tout_compte_html(
        employee_data,
        company_data,
        exit_data,
        motif_label=motif_label,
        sections=[
            remun_section,
            licenciement_section,
            preavis_section,
            conges_section,
            autres_section,
            retenues_section,
        ],
        total_brut=total_brut_final,
        total_cotisations=total_cotisations_final,
        total_net=total_net_final,
        specific_mention=mention_licenciement,
    )
