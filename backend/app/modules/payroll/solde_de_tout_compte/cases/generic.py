"""
Case Generic: Fallback pour types de sortie non spécifiques
"""

import io
from typing import Dict, Any
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib import colors

from app.modules.payroll.solde_de_tout_compte.common import pdf_helpers


def generate_generic_solde(
    styles: Dict,
    employee_data: Dict[str, Any],
    company_data: Dict[str, Any],
    exit_data: Dict[str, Any],
    indemnities: Dict[str, Any]
) -> bytes:
    """
    Version générique du solde de tout compte pour les autres types de sortie
    (pour compatibilité avec d'éventuels autres types non encore implémentés)

    Returns:
        bytes: PDF content
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
    story = []

    # En-tête
    story.append(Paragraph(
        f"<b>{company_data.get('name', company_data.get('raison_sociale', 'Entreprise'))}</b>",
        styles['EntrepriseHeader']
    ))
    story.append(Spacer(1, 0.5*cm))

    # Titre
    story.append(Paragraph("REÇU POUR SOLDE DE TOUT COMPTE", styles['TitrePrincipal']))
    story.append(Spacer(1, 0.8*cm))

    # Informations
    nom_complet = f"{employee_data.get('first_name', '')} {employee_data.get('last_name', '')}"
    date_sortie = pdf_helpers.format_date(exit_data.get('last_working_day', ''))

    story.append(Paragraph(
        f"Je soussigné(e) <b>{nom_complet}</b>, ayant quitté l'entreprise le {date_sortie}, "
        f"reconnais avoir reçu les sommes suivantes :",
        styles['CorpsTexte']
    ))
    story.append(Spacer(1, 0.5*cm))

    # Tableau des indemnités
    data_indemnites = [
        ['<b>Description</b>', '<b>Montant</b>']
    ]

    total_general = 0.0

    # Indemnité de préavis
    if indemnities.get('indemnite_preavis', {}).get('montant', 0) > 0:
        montant = indemnities['indemnite_preavis']['montant']
        data_indemnites.append([
            'Indemnité compensatrice de préavis',
            pdf_helpers.format_currency(montant)
        ])
        total_general += montant

    # Indemnité de congés payés
    if indemnities.get('indemnite_conges', {}).get('montant', 0) > 0:
        montant = indemnities['indemnite_conges']['montant']
        data_indemnites.append([
            'Indemnité compensatrice de congés payés',
            pdf_helpers.format_currency(montant)
        ])
        total_general += montant

    # Indemnité de licenciement
    if indemnities.get('indemnite_licenciement', {}).get('montant', 0) > 0:
        montant = indemnities['indemnite_licenciement']['montant']
        data_indemnites.append([
            'Indemnité légale de licenciement',
            pdf_helpers.format_currency(montant)
        ])
        total_general += montant

    # Indemnité de rupture conventionnelle
    if indemnities.get('indemnite_rupture_conventionnelle', {}).get('montant_negocie', 0) > 0:
        montant = indemnities['indemnite_rupture_conventionnelle']['montant_negocie']
        data_indemnites.append([
            'Indemnité de rupture conventionnelle',
            pdf_helpers.format_currency(montant)
        ])
        total_general += montant

    # Dernière paie
    if exit_data.get('final_net_amount'):
        data_indemnites.append([
            'Dernier salaire net',
            pdf_helpers.format_currency(exit_data['final_net_amount'])
        ])
        total_general += exit_data['final_net_amount']

    # Ligne de total
    data_indemnites.append(['', ''])
    data_indemnites.append([
        '<b>TOTAL NET À PAYER</b>',
        f'<b>{pdf_helpers.format_currency(total_general)}</b>'
    ])

    table = Table(data_indemnites, colWidths=[12*cm, 4*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e5e7eb')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1f2937')),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -3), 1, colors.HexColor('#d1d5db')),
        ('LINEABOVE', (0, -1), (-1, -1), 2, colors.HexColor('#1e3a8a')),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#dbeafe')),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))

    story.append(table)
    story.append(Spacer(1, 1*cm))

    # Mention légale de quittance
    texte_quittance = """
    <b>Le présent reçu vaut quittance pour solde de tout compte.</b><br/>
    Je reconnais avoir pris connaissance de la faculté de dénonciation qui m'est offerte
    par l'article D1234-7 du Code du travail, aux termes duquel je dispose d'un délai
    de six mois à compter de ce jour pour dénoncer les sommes qui m'auraient été réglées
    par l'employeur.
    """
    story.append(Paragraph(texte_quittance, styles['Important']))
    story.append(Spacer(1, 1*cm))

    # Espaces pour signatures
    from datetime import datetime
    date_aujourd_hui = pdf_helpers.format_date(datetime.now().date())

    # Tableau pour les signatures
    data_signatures = [
        ['Fait en double exemplaire', ''],
        [f"À {company_data.get('city', '___________')}, le {date_aujourd_hui}", ''],
        ['', ''],
        ['<b>Signature du salarié</b>', '<b>Signature de l\'employeur</b>'],
        ['(Précédée de la mention "Lu et approuvé")', '(Cachet de l\'entreprise)'],
        ['', ''],
        ['', ''],
        ['', '']
    ]

    table_signatures = Table(data_signatures, colWidths=[8*cm, 8*cm])
    table_signatures.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)),
        ('SPAN', (0, 1), (1, 1)),
        ('SPAN', (0, 2), (1, 2)),
        ('ALIGN', (0, 0), (-1, 2), 'CENTER'),
        ('VALIGN', (0, 3), (-1, -1), 'TOP'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 3), (-1, 3), 20),
        ('BOTTOMPADDING', (0, 4), (-1, 4), 40),
    ]))

    story.append(table_signatures)
    story.append(Spacer(1, 0.5*cm))

    # Pied de page
    story.append(Paragraph(
        "<i>Article D1234-7 du Code du travail</i>",
        ParagraphStyle(
            name='MentionLegale',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#9ca3af'),
            alignment=TA_CENTER
        )
    ))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes
