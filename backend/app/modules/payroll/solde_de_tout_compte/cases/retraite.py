"""
Case 4: Départ/Mise à la retraite - Solde de tout compte generation
"""

from typing import Dict, Any

from app.shared.domain.pluriel import accord

from app.modules.payroll.solde_de_tout_compte.common import socle_commun
from app.modules.payroll.solde_de_tout_compte.common import pdf_helpers
from app.modules.payroll.solde_de_tout_compte.common.html_renderer import (
    amount_row,
    amounts_section,
    render_solde_tout_compte_html,
)


def generate_retraite_solde(
    styles: Dict,
    employee_data: Dict[str, Any],
    company_data: Dict[str, Any],
    exit_data: Dict[str, Any],
    indemnities: Dict[str, Any],
    supabase_client=None,
) -> bytes:
    """
    Génère le PDF de solde de tout compte pour un départ/mise à la retraite.

    Gère deux sous-cas : initiative salarié ou initiative employeur.
    """
    exit_notes = (
        exit_data.get("exit_notes", {})
        if isinstance(exit_data.get("exit_notes"), dict)
        else {}
    )
    retirement_initiator = exit_notes.get("retirement_initiator") or exit_data.get(
        "retirement_initiator", "employee"
    )
    is_employer_initiated = retirement_initiator == "employer"
    motif_label = "mise à la retraite" if is_employer_initiated else "départ à la retraite"

    # === Rémunérations acquises ===
    remun_section, total_brut_remun, total_cotisations_remun, total_net_remun = (
        socle_commun.compute_remunerations_section(
            employee_data,
            exit_data,
            employee_id=employee_data.get("id"),
            supabase_client=supabase_client,
        )
    )

    # === Indemnité de retraite ===
    if is_employer_initiated:
        indemnite_retraite = indemnities.get("indemnite_mise_retraite", {})
        libelle_indemnite = "Indemnité de mise à la retraite"
    else:
        indemnite_retraite = indemnities.get("indemnite_depart_retraite", {})
        libelle_indemnite = "Indemnité de départ à la retraite (initiative salarié)"

    montant_retraite = pdf_helpers.safe_float(indemnite_retraite.get("montant", 0))
    anciennete = pdf_helpers.safe_float(indemnities.get("anciennete_annees", 0))
    salaire_ref = pdf_helpers.safe_float(indemnities.get("salaire_reference", 0))

    base_retenue = "Non déterminée"
    if indemnite_retraite.get("base_calcul"):
        base_retenue = indemnite_retraite.get("base_calcul")
    elif indemnite_retraite.get("tranche1_annees"):
        base_retenue = "Légale"
    elif indemnite_retraite.get("conventionnelle"):
        base_retenue = "Conventionnelle"

    detail_retraite = (
        "Ancienneté : " + f"{anciennete:.2f}".replace(".", ",") + f" {accord(anciennete, 'an')}"
    )
    if salaire_ref > 0:
        detail_retraite += (
            f" | Salaire de référence : {pdf_helpers.format_currency(salaire_ref)}"
        )
    detail_retraite += f" | Base : {base_retenue}"
    if montant_retraite == 0:
        detail_retraite = "Non applicable ou non renseigné"

    retraite_section = amounts_section(
        "INDEMNITÉ DE RETRAITE",
        [
            amount_row(
                libelle_indemnite,
                detail_retraite,
                montant_retraite if montant_retraite > 0 else None,
            )
        ],
    )

    # === Préavis (même phrase que le certificat et l'attestation) ===
    preavis_section, montant_preavis, preavis_waived = socle_commun.compute_preavis_section(
        exit_data, indemnities
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
        + montant_retraite
        + montant_preavis
        + montant_conges
        + montant_cp_preavis
    )
    total_cotisations_final = total_cotisations_remun
    total_net_final = (
        total_net_remun
        + montant_retraite
        + montant_preavis
        + montant_conges
        + montant_cp_preavis
    )

    if is_employer_initiated:
        mention_retraite = (
            "Rupture du contrat par mise à la retraite à l'initiative de l'employeur."
        )
    else:
        mention_retraite = (
            "Rupture du contrat par départ volontaire à la retraite "
            "à l'initiative du salarié."
        )

    return render_solde_tout_compte_html(
        employee_data,
        company_data,
        exit_data,
        motif_label=motif_label,
        sections=[
            remun_section,
            retraite_section,
            preavis_section,
            conges_section,
            autres_section,
            retenues_section,
        ],
        total_brut=total_brut_final,
        total_cotisations=total_cotisations_final,
        total_net=total_net_final,
        specific_mention=mention_retraite,
    )
