"""
Case 4: Départ/Mise à la retraite - Solde de tout compte generation
"""

import io
from typing import Dict, Any
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib import colors

from app.modules.payroll.solde_de_tout_compte.common import pdf_helpers
from app.modules.payroll.solde_de_tout_compte.common import socle_commun


def generate_retraite_solde(
    styles: Dict,
    employee_data: Dict[str, Any],
    company_data: Dict[str, Any],
    exit_data: Dict[str, Any],
    indemnities: Dict[str, Any],
    supabase_client=None
) -> bytes:
    """
    Génère le PDF pour un départ/mise à la retraite

    Gère deux sous-cas :
    - Initiative salarié (retirement_initiator = "employee")
    - Initiative employeur (retirement_initiator = "employer")

    Returns:
        bytes: PDF content
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
    story = []

    # Déterminer le sous-cas (initiative salarié ou employeur)
    exit_notes = exit_data.get('exit_notes', {}) if isinstance(exit_data.get('exit_notes'), dict) else {}
    retirement_initiator = exit_notes.get('retirement_initiator') or exit_data.get('retirement_initiator', 'employee')
    is_employer_initiated = retirement_initiator == 'employer'

    # En-tête entreprise
    pdf_helpers.build_company_header(story, styles, company_data)

    # Titre principal
    pdf_helpers.build_title_header(story, styles)

    # Informations salarié et date de sortie
    nom_complet = f"{employee_data.get('first_name', '')} {employee_data.get('last_name', '')}"
    date_sortie = pdf_helpers.format_date(exit_data.get('last_working_day', ''))

    motif_text = "DÉPART À LA RETRAITE"
    if is_employer_initiated:
        motif_text = "MISE À LA RETRAITE"

    story.append(Paragraph(
        f"Je soussigné(e) <b>{nom_complet}</b>, ayant quitté l'entreprise le {date_sortie} par <b>{motif_text}</b>, "
        f"reconnais avoir reçu les sommes suivantes :",
        styles['CorpsTexte']
    ))
    story.append(Spacer(1, 0.8*cm))

    # === SECTION 1 : RÉMUNÉRATIONS ACQUISES (SOCLE COMMUN) ===
    total_brut_remun, total_cotisations_remun, total_net_remun = socle_commun.build_remunerations_section(
        story, styles, employee_data, exit_data, section_number=1
    )

    # === SECTION 2 : INDEMNITÉ DE RETRAITE ===
    story.append(Paragraph("<b>2. INDEMNITÉ DE RETRAITE</b>", styles['Important']))
    story.append(Spacer(1, 0.3*cm))

    # Récupérer l'indemnité de retraite selon le sous-cas
    if is_employer_initiated:
        indemnite_retraite = indemnities.get('indemnite_mise_retraite', {})
        libelle_indemnite = 'Indemnité de mise à la retraite'
    else:
        indemnite_retraite = indemnities.get('indemnite_depart_retraite', {})
        libelle_indemnite = 'Indemnité de départ à la retraite (initiative salarié)'

    montant_retraite = pdf_helpers.safe_float(indemnite_retraite.get('montant', 0))
    anciennete = pdf_helpers.safe_float(indemnities.get('anciennete_annees', 0))
    salaire_ref = pdf_helpers.safe_float(indemnities.get('salaire_reference', 0))

    # Déterminer la base de calcul
    base_retenue = "Non déterminée"
    if indemnite_retraite.get('base_calcul'):
        base_retenue = indemnite_retraite.get('base_calcul')
    elif indemnite_retraite.get('tranche1_annees'):
        base_retenue = "Légale"
    elif indemnite_retraite.get('conventionnelle'):
        base_retenue = "Conventionnelle"

    detail_retraite = f"Ancienneté : {anciennete:.2f} ans"
    if salaire_ref > 0:
        detail_retraite += f" | Salaire de référence : {pdf_helpers.format_currency(salaire_ref)}"
    detail_retraite += f" | Base : {base_retenue}"

    if montant_retraite == 0:
        detail_retraite = "Non applicable ou non renseigné"

    data_retraite = [
        [Paragraph('<b>Libellé</b>', styles['Normal']),
         Paragraph('<b>Détails</b>', styles['Normal']),
         Paragraph('<b>Montant</b>', styles['Normal'])],
        [
            libelle_indemnite,
            detail_retraite,
            pdf_helpers.format_currency(montant_retraite) if montant_retraite > 0 else ''
        ]
    ]

    table_retraite = Table(data_retraite, colWidths=[6*cm, 7*cm, 3*cm])
    table_retraite.setStyle(TableStyle([
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
    story.append(table_retraite)
    story.append(Spacer(1, 0.6*cm))

    # === SECTION 3 : PRÉAVIS ===
    story.append(Paragraph("<b>3. PRÉAVIS</b>", styles['Important']))
    story.append(Spacer(1, 0.3*cm))

    notice_period = exit_data.get('notice_period_days', 0)
    notice_indemnity_type = exit_data.get('notice_indemnity_type', 'not_applicable')
    indemnite_preavis = indemnities.get('indemnite_preavis', {})
    montant_preavis = pdf_helpers.safe_float(indemnite_preavis.get('montant', 0))

    # Déterminer si préavis exécuté ou dispensé
    preavis_executed = False
    preavis_waived = False

    if notice_period == 0:
        preavis_text = "Aucun préavis prévu"
    elif notice_indemnity_type == 'waived' or (notice_indemnity_type != 'paid' and montant_preavis == 0):
        # Préavis exécuté (pas d'indemnité compensatrice)
        preavis_executed = True
        preavis_text = f"Préavis de {notice_period} jours exécuté - Salaire inclus dans rémunérations"
    elif notice_indemnity_type == 'paid' and montant_preavis > 0:
        # Préavis non exécuté, dispense employeur
        preavis_waived = True
        preavis_text = f"Préavis de {notice_period} jours - Dispense d'exécution"
    else:
        preavis_text = f"Préavis de {notice_period} jours - Statut non déterminé"

    data_preavis = [
        [Paragraph('<b>Libellé</b>', styles['Normal']),
         Paragraph('<b>Détails</b>', styles['Normal']),
         Paragraph('<b>Montant</b>', styles['Normal'])],
        ['Préavis exécuté', preavis_text, ''],
        ['Indemnité compensatrice de préavis',
         "Dispense d'exécution - Indemnité compensatrice" if preavis_waived else "Non applicable (préavis exécuté ou non prévu)",
         pdf_helpers.format_currency(montant_preavis) if montant_preavis > 0 else '']
    ]

    table_preavis = Table(data_preavis, colWidths=[6*cm, 7*cm, 3*cm])
    table_preavis.setStyle(TableStyle([
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
    story.append(table_preavis)
    story.append(Spacer(1, 0.6*cm))

    # === SECTION 4 : CONGÉS PAYÉS (SOCLE COMMUN avec CP préavis) ===
    story.append(Paragraph("<b>4. CONGÉS PAYÉS</b>", styles['Important']))
    story.append(Spacer(1, 0.3*cm))

    indemnite_conges = indemnities.get('indemnite_conges', {})
    jours_restants = pdf_helpers.safe_float(indemnite_conges.get('jours_restants', 0))
    montant_conges = pdf_helpers.safe_float(indemnite_conges.get('montant', 0))
    details_conges = indemnite_conges.get('details', {})
    methode = details_conges.get('methode_retenue', 'maintien') if details_conges else 'maintien'
    cp_acquis = details_conges.get('conges_acquis') if details_conges else None
    cp_pris = details_conges.get('conges_pris') if details_conges else None

    detail_conges_text = f"{jours_restants:.2f} jours restants"
    if cp_acquis is not None and cp_pris is not None:
        detail_conges_text += f" ({cp_acquis:.0f} acquis - {cp_pris:.0f} pris)"
    detail_conges_text += f" - Méthode : {methode}"
    if jours_restants == 0:
        detail_conges_text = "Solde : 0 jour ou non renseigné"

    # Option A : Ligne séparée pour CP sur préavis si préavis indemnisé
    cp_preavis_text = "Non applicable ou non calculé"
    montant_cp_preavis = 0.0
    if preavis_waived and montant_preavis > 0:
        # Si préavis indemnisé, on pourrait avoir des CP afférents
        cp_preavis_text = "Congés payés afférents au préavis non exécuté"

    data_conges = [
        [Paragraph('<b>Libellé</b>', styles['Normal']),
         Paragraph('<b>Détails</b>', styles['Normal']),
         Paragraph('<b>Montant</b>', styles['Normal'])],
        [
            'Indemnité compensatrice de congés payés',
            detail_conges_text,
            pdf_helpers.format_currency(montant_conges) if montant_conges > 0 else ''
        ],
        [
            'Congés payés afférents au préavis',
            cp_preavis_text,
            pdf_helpers.format_currency(montant_cp_preavis) if montant_cp_preavis > 0 else ''
        ]
    ]

    table_conges = Table(data_conges, colWidths=[6*cm, 7*cm, 3*cm])
    table_conges.setStyle(TableStyle([
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
    story.append(table_conges)
    story.append(Spacer(1, 0.6*cm))

    # === SECTION 5 : AUTRES RÉGULARISATIONS (SOCLE COMMUN) ===
    socle_commun.build_autres_regularisations_section(story, styles, section_number=5)

    # === SECTION 6 : RETENUES ÉVENTUELLES (SOCLE COMMUN) ===
    socle_commun.build_retenues_section(story, styles, section_number=6)

    # === TOTAL GÉNÉRAL ===
    total_brut_final = total_brut_remun + montant_retraite + montant_preavis + montant_conges + montant_cp_preavis
    total_cotisations_final = total_cotisations_remun
    total_net_final = total_net_remun + montant_retraite + montant_preavis + montant_conges + montant_cp_preavis

    socle_commun.build_total_section(story, styles, total_brut_final, total_cotisations_final, total_net_final)

    # Mentions légales
    if is_employer_initiated:
        mention_retraite = "Rupture du contrat par mise à la retraite à l'initiative de l'employeur."
    else:
        mention_retraite = "Rupture du contrat par départ volontaire à la retraite à l'initiative du salarié."

    pdf_helpers.build_legal_mentions(story, styles, specific_mention=mention_retraite)

    # Signatures
    pdf_helpers.build_signatures(story, styles, company_data)

    # Pied de page
    pdf_helpers.build_footer(story, styles)

    # Build PDF
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes
