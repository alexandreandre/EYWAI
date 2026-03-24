"""
Case 2: Rupture Conventionnelle - Solde de tout compte generation
"""

import io
from typing import Dict, Any
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib import colors

from app.modules.payroll.solde_de_tout_compte.common import pdf_helpers
from app.modules.payroll.solde_de_tout_compte.common import socle_commun


def generate_rupture_conventionnelle_solde(
    styles: Dict,
    employee_data: Dict[str, Any],
    company_data: Dict[str, Any],
    exit_data: Dict[str, Any],
    indemnities: Dict[str, Any],
    supabase_client=None
) -> bytes:
    """
    Génère le PDF pour une rupture conventionnelle

    Returns:
        bytes: PDF content
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
    story = []

    # En-tête entreprise
    pdf_helpers.build_company_header(story, styles, company_data)

    # Titre principal
    pdf_helpers.build_title_header(story, styles)

    # Informations salarié et date de sortie
    nom_complet = f"{employee_data.get('first_name', '')} {employee_data.get('last_name', '')}"
    date_sortie = pdf_helpers.format_date(exit_data.get('last_working_day', ''))

    story.append(Paragraph(
        f"Je soussigné(e) <b>{nom_complet}</b>, ayant quitté l'entreprise le {date_sortie} par <b>RUPTURE CONVENTIONNELLE</b>, "
        f"reconnais avoir reçu les sommes suivantes :",
        styles['CorpsTexte']
    ))
    story.append(Spacer(1, 0.8*cm))

    # === SECTION 1 : RÉMUNÉRATIONS ACQUISES (SOCLE COMMUN) ===
    total_brut_remun, total_cotisations_remun, total_net_remun = socle_commun.build_remunerations_section(
        story, styles, employee_data, exit_data, section_number=1
    )

    # === SECTION 2 : INDEMNITÉ SPÉCIFIQUE DE RUPTURE CONVENTIONNELLE ===
    story.append(Paragraph("<b>2. INDEMNITÉ SPÉCIFIQUE DE RUPTURE CONVENTIONNELLE</b>", styles['Important']))
    story.append(Spacer(1, 0.3*cm))

    indemnite_rupture = indemnities.get('indemnite_rupture_conventionnelle', {})
    montant_rupture = pdf_helpers.safe_float(indemnite_rupture.get('montant_negocie', 0))
    montant_minimum = pdf_helpers.safe_float(indemnite_rupture.get('montant_minimum', 0))
    anciennete = pdf_helpers.safe_float(indemnities.get('anciennete_annees', 0))
    salaire_ref = pdf_helpers.safe_float(indemnities.get('salaire_reference', 0))

    detail_rupture = f"Ancienneté : {anciennete:.2f} ans"
    if salaire_ref > 0:
        detail_rupture += f" | Salaire de référence : {pdf_helpers.format_currency(salaire_ref)}"
    if montant_minimum > 0:
        detail_rupture += f" | Minimum légal : {pdf_helpers.format_currency(montant_minimum)}"
    if montant_rupture == 0:
        detail_rupture = "Montant non renseigné ou en attente de calcul"

    data_rupture = [
        [Paragraph('<b>Libellé</b>', styles['Normal']),
         Paragraph('<b>Détails</b>', styles['Normal']),
         Paragraph('<b>Montant</b>', styles['Normal'])],
        [
            'Indemnité spécifique de rupture conventionnelle',
            detail_rupture,
            pdf_helpers.format_currency(montant_rupture) if montant_rupture > 0 else ''
        ]
    ]

    table_rupture = Table(data_rupture, colWidths=[6*cm, 7*cm, 3*cm])
    table_rupture.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e5e7eb')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (2, 1), (2, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#d1d5db')),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(table_rupture)
    story.append(Spacer(1, 0.6*cm))

    # === SECTION 3 : CONGÉS PAYÉS (SOCLE COMMUN) ===
    montant_conges = socle_commun.build_conges_section(story, styles, indemnities, section_number=3)

    # === SECTION 4 : AUTRES RÉGULARISATIONS (SOCLE COMMUN) ===
    socle_commun.build_autres_regularisations_section(story, styles, section_number=4)

    # === SECTION 5 : RETENUES ÉVENTUELLES (SOCLE COMMUN) ===
    socle_commun.build_retenues_section(story, styles, section_number=5)

    # === TOTAL GÉNÉRAL ===
    total_brut_final = total_brut_remun + montant_rupture + montant_conges
    total_cotisations_final = total_cotisations_remun
    total_net_final = total_net_remun + montant_rupture + montant_conges

    socle_commun.build_total_section(story, styles, total_brut_final, total_cotisations_final, total_net_final)

    # Mentions légales
    pdf_helpers.build_legal_mentions(
        story,
        styles,
        specific_mention="Rupture du contrat de travail par rupture conventionnelle homologuée, conformément aux articles L1237-11 et suivants du Code du travail."
    )

    # Signatures
    pdf_helpers.build_signatures(story, styles, company_data)

    # Pied de page
    pdf_helpers.build_footer(story, styles, articles="Articles D1234-7, L1234-20 et L1237-11 du Code du travail")

    # Build PDF
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes
