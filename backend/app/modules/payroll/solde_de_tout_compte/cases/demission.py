"""
Case 1: Démission - Solde de tout compte generation
"""

import io
from typing import Dict, Any
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors

from app.modules.payroll.solde_de_tout_compte.common import pdf_helpers
from app.modules.payroll.solde_de_tout_compte.common import socle_commun


def generate_demission_solde(
    styles: Dict,
    employee_data: Dict[str, Any],
    company_data: Dict[str, Any],
    exit_data: Dict[str, Any],
    indemnities: Dict[str, Any],
    supabase_client=None,
) -> bytes:
    """
    Génère le PDF pour une démission

    Returns:
        bytes: PDF content
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm)
    story = []

    # En-tête entreprise
    pdf_helpers.build_company_header(story, styles, company_data)

    # Titre principal
    pdf_helpers.build_title_header(story, styles)

    # Informations salarié et date de sortie
    nom_complet = (
        f"{employee_data.get('first_name', '')} {employee_data.get('last_name', '')}"
    )
    date_sortie = pdf_helpers.format_date(exit_data.get("last_working_day", ""))

    story.append(
        Paragraph(
            f"Je soussigné(e) <b>{nom_complet}</b>, ayant quitté l'entreprise le {date_sortie} par <b>DÉMISSION</b>, "
            f"reconnais avoir reçu les sommes suivantes :",
            styles["CorpsTexte"],
        )
    )
    story.append(Spacer(1, 0.8 * cm))

    # === SECTION 1 : RÉMUNÉRATIONS ACQUISES (SOCLE COMMUN) ===
    total_brut_remun, total_cotisations_remun, total_net_remun = (
        socle_commun.build_remunerations_section(
            story, styles, employee_data, exit_data, section_number=1
        )
    )

    # === SECTION 2 : CONGÉS PAYÉS (SOCLE COMMUN) ===
    montant_conges = socle_commun.build_conges_section(
        story, styles, indemnities, section_number=2
    )

    # === SECTION 3 : PRÉAVIS (SPÉCIFIQUE DÉMISSION) ===
    story.append(Paragraph("<b>3. PRÉAVIS</b>", styles["Important"]))
    story.append(Spacer(1, 0.3 * cm))

    notice_period = exit_data.get("notice_period_days", 0)
    notice_indemnity_type = exit_data.get("notice_indemnity_type", "not_applicable")
    indemnite_preavis = indemnities.get("indemnite_preavis", {})
    montant_preavis = pdf_helpers.safe_float(indemnite_preavis.get("montant", 0))
    is_gross_misconduct = exit_data.get("is_gross_misconduct", False)

    # Préavis exécuté
    if notice_period > 0 and not is_gross_misconduct:
        if notice_indemnity_type == "waived" or montant_preavis == 0:
            preavis_text = f"Préavis de {notice_period} jours exécuté - Salaire inclus dans rémunérations"
        else:
            preavis_text = f"Préavis de {notice_period} jours - Dispense d'exécution"
    elif is_gross_misconduct:
        preavis_text = "Aucun préavis (faute grave)"
    else:
        preavis_text = (
            "Aucun préavis"
            if notice_period == 0
            else f"Préavis de {notice_period} jours"
        )

    # Indemnité compensatrice de préavis (si dispense employeur)
    if notice_indemnity_type == "paid" and montant_preavis > 0:
        preavis_text_comp = "Dispense d'exécution - Indemnité compensatrice"
    else:
        preavis_text_comp = "Non applicable (préavis exécuté ou non prévu)"

    data_preavis = [
        [
            Paragraph("<b>Libellé</b>", styles["Normal"]),
            Paragraph("<b>Détails</b>", styles["Normal"]),
            Paragraph("<b>Montant</b>", styles["Normal"]),
        ],
        ["Préavis exécuté", preavis_text, ""],
        [
            "Indemnité compensatrice de préavis",
            preavis_text_comp,
            pdf_helpers.format_currency(montant_preavis) if montant_preavis > 0 else "",
        ],
    ]

    table_preavis = Table(data_preavis, colWidths=[6 * cm, 7 * cm, 3 * cm])
    table_preavis.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e7eb")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (2, 1), (2, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#d1d5db")),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(table_preavis)
    story.append(Spacer(1, 0.6 * cm))

    # === SECTION 4 : AUTRES RÉGULARISATIONS (SOCLE COMMUN) ===
    socle_commun.build_autres_regularisations_section(story, styles, section_number=4)

    # === SECTION 5 : RETENUES ÉVENTUELLES (SOCLE COMMUN) ===
    socle_commun.build_retenues_section(story, styles, section_number=5)

    # === TOTAL GÉNÉRAL ===
    total_brut_final = total_brut_remun + montant_conges + montant_preavis
    total_cotisations_final = total_cotisations_remun
    total_net_final = total_net_remun + montant_conges + montant_preavis

    socle_commun.build_total_section(
        story, styles, total_brut_final, total_cotisations_final, total_net_final
    )

    # Mentions légales
    pdf_helpers.build_legal_mentions(story, styles)

    # Signatures
    pdf_helpers.build_signatures(story, styles, company_data)

    # Pied de page
    pdf_helpers.build_footer(story, styles)

    # Build PDF
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes
