"""
Case 5: Fin / Rupture de période d'essai - Solde de tout compte generation
"""

from typing import Dict, Any

from app.modules.payroll.solde_de_tout_compte.common import socle_commun
from app.modules.payroll.solde_de_tout_compte.common import pdf_helpers
from app.modules.payroll.solde_de_tout_compte.common.html_renderer import (
    amount_row,
    amounts_section,
    info_row,
    info_section,
    render_solde_tout_compte_html,
)


def generate_fin_periode_essai_solde(
    styles: Dict,
    employee_data: Dict[str, Any],
    company_data: Dict[str, Any],
    exit_data: Dict[str, Any],
    indemnities: Dict[str, Any],
    supabase_client=None,
) -> bytes:
    """Génère le PDF de solde de tout compte pour une fin/rupture de période d'essai."""
    exit_notes = (
        exit_data.get("exit_notes", {})
        if isinstance(exit_data.get("exit_notes"), dict)
        else {}
    )
    probation_ended_by = exit_notes.get("probation_ended_by") or exit_data.get(
        "probation_ended_by", "unknown"
    )
    notice_period_required = exit_notes.get(
        "notice_period_required_days"
    ) or exit_data.get("notice_period_required_days")
    notice_period_given = exit_notes.get("notice_period_given_days") or exit_data.get(
        "notice_period_given_days"
    )
    notice_period_respected = exit_notes.get("notice_period_respected")
    if notice_period_respected is None:
        notice_period_respected = exit_data.get("notice_period_respected")

    notice_compensation_due = exit_notes.get(
        "notice_compensation_due"
    ) or exit_data.get("notice_compensation_due")
    if notice_compensation_due is None:
        if probation_ended_by == "employer" and notice_period_respected is False:
            notice_compensation_due = True
        elif probation_ended_by == "employee":
            notice_compensation_due = False
        else:
            notice_compensation_due = None

    # === Rémunérations acquises ===
    remun_section, total_brut_remun, total_cotisations_remun, total_net_remun = (
        socle_commun.compute_remunerations_section(
            employee_data,
            exit_data,
            employee_id=employee_data.get("id"),
            supabase_client=supabase_client,
        )
    )

    # === Période d'essai (informations) ===
    initiator_label = "Inconnu"
    if probation_ended_by == "employee":
        initiator_label = "Salarié"
    elif probation_ended_by == "employer":
        initiator_label = "Employeur"

    notice_respected_label = "Inconnu"
    if notice_period_respected is True:
        notice_respected_label = "Oui"
    elif notice_period_respected is False:
        notice_respected_label = "Non"

    notice_required_str = (
        str(notice_period_required)
        if notice_period_required is not None
        else "Non renseigné"
    )
    notice_given_str = (
        str(notice_period_given) if notice_period_given is not None else "Non renseigné"
    )

    periode_essai_section = info_section(
        "PÉRIODE D'ESSAI",
        [
            info_row("Rupture à l'initiative", initiator_label),
            info_row("Délai de prévenance requis (jours)", notice_required_str),
            info_row("Délai de prévenance accordé (jours)", notice_given_str),
            info_row("Délai respecté", notice_respected_label),
        ],
    )

    # === Indemnité compensatrice de délai de prévenance ===
    indemnite_prevenance = indemnities.get("indemnite_delai_prevenance", {})
    montant_prevenance = pdf_helpers.safe_float(indemnite_prevenance.get("montant", 0))

    if notice_compensation_due and montant_prevenance == 0:
        detail_prevenance = "Indemnité due mais montant non calculé"
    elif notice_compensation_due:
        detail_prevenance = "Délai de prévenance non respecté — indemnité compensatrice"
    elif notice_compensation_due is False:
        detail_prevenance = "Non applicable (délai respecté ou rupture salarié)"
    else:
        detail_prevenance = "Non renseigné ou non applicable"

    prevenance_section = amounts_section(
        "INDEMNITÉ COMPENSATRICE DE DÉLAI DE PRÉVENANCE",
        [
            amount_row(
                "Indemnité compensatrice de délai de prévenance (période d'essai)",
                detail_prevenance,
                montant_prevenance if montant_prevenance > 0 else None,
            )
        ],
    )

    # === Congés payés ===
    conges_section, montant_conges = socle_commun.compute_conges_section(indemnities)

    # === Sections génériques ===
    autres_section = socle_commun.compute_autres_regularisations_section()
    retenues_section = socle_commun.compute_retenues_section()

    # === Totaux ===
    total_brut_final = total_brut_remun + montant_prevenance + montant_conges
    total_cotisations_final = total_cotisations_remun
    total_net_final = total_net_remun + montant_prevenance + montant_conges

    mention_periode_essai = "Fin / rupture du contrat pendant la période d'essai."
    if probation_ended_by == "employer":
        mention_periode_essai += " Rupture à l'initiative de l'employeur."
    elif probation_ended_by == "employee":
        mention_periode_essai += " Rupture à l'initiative du salarié."

    return render_solde_tout_compte_html(
        employee_data,
        company_data,
        exit_data,
        motif_label="fin / rupture de période d'essai",
        sections=[
            remun_section,
            periode_essai_section,
            prevenance_section,
            conges_section,
            autres_section,
            retenues_section,
        ],
        total_brut=total_brut_final,
        total_cotisations=total_cotisations_final,
        total_net=total_net_final,
        specific_mention=mention_periode_essai,
    )
