"""
Case Generic: Fallback pour types de sortie non spécifiques
"""

from typing import Dict, Any

from app.modules.payroll.solde_de_tout_compte.common import pdf_helpers
from app.modules.payroll.solde_de_tout_compte.common.html_renderer import (
    amount_row,
    amounts_section,
    render_solde_tout_compte_html,
)

_EXIT_TYPE_LABELS = {
    "fin_cdd": "fin de contrat à durée déterminée",
    "fin_mission": "fin de mission (intérim)",
    "deces": "décès du salarié",
}


def generate_generic_solde(
    styles: Dict,
    employee_data: Dict[str, Any],
    company_data: Dict[str, Any],
    exit_data: Dict[str, Any],
    indemnities: Dict[str, Any],
) -> bytes:
    """
    Version générique du solde de tout compte pour les autres types de sortie.
    """
    rows = []
    total_general = 0.0

    montant_preavis = pdf_helpers.safe_float(
        indemnities.get("indemnite_preavis", {}).get("montant", 0)
    )
    if montant_preavis > 0:
        rows.append(
            amount_row("Indemnité compensatrice de préavis", "", montant_preavis)
        )
        total_general += montant_preavis

    montant_conges = pdf_helpers.safe_float(
        indemnities.get("indemnite_conges", {}).get("montant", 0)
    )
    if montant_conges > 0:
        rows.append(
            amount_row("Indemnité compensatrice de congés payés", "", montant_conges)
        )
        total_general += montant_conges

    montant_licenciement = pdf_helpers.safe_float(
        indemnities.get("indemnite_licenciement", {}).get("montant", 0)
    )
    if montant_licenciement > 0:
        rows.append(
            amount_row("Indemnité légale de licenciement", "", montant_licenciement)
        )
        total_general += montant_licenciement

    montant_rupture = pdf_helpers.safe_float(
        indemnities.get("indemnite_rupture_conventionnelle", {}).get(
            "montant_negocie", 0
        )
    )
    if montant_rupture > 0:
        rows.append(
            amount_row("Indemnité de rupture conventionnelle", "", montant_rupture)
        )
        total_general += montant_rupture

    final_net = pdf_helpers.safe_float(exit_data.get("final_net_amount", 0))
    if final_net > 0:
        rows.append(amount_row("Dernier salaire net", "", final_net))
        total_general += final_net

    if not rows:
        rows.append(amount_row("Sommes dues", "Aucune somme renseignée", None))

    sommes_section = amounts_section("SOMMES DUES", rows)

    exit_type = exit_data.get("exit_type", "")
    motif_label = _EXIT_TYPE_LABELS.get(
        exit_type, "la rupture du contrat de travail"
    )

    return render_solde_tout_compte_html(
        employee_data,
        company_data,
        exit_data,
        motif_label=motif_label,
        sections=[sommes_section],
        total_brut=total_general,
        total_cotisations=0.0,
        total_net=total_general,
    )
