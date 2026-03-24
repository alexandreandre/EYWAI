"""
Case 5: Fin / Rupture de période d'essai - Solde de tout compte generation
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


def generate_fin_periode_essai_solde(
    styles: Dict,
    employee_data: Dict[str, Any],
    company_data: Dict[str, Any],
    exit_data: Dict[str, Any],
    indemnities: Dict[str, Any],
    supabase_client=None
) -> bytes:
    """
    Génère le PDF pour une fin/rupture de période d'essai

    Returns:
        bytes: PDF content
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
    story = []

    # Récupérer les paramètres de période d'essai
    exit_notes = exit_data.get('exit_notes', {}) if isinstance(exit_data.get('exit_notes'), dict) else {}
    probation_ended_by = exit_notes.get('probation_ended_by') or exit_data.get('probation_ended_by', 'unknown')
    notice_period_required = exit_notes.get('notice_period_required_days') or exit_data.get('notice_period_required_days')
    notice_period_given = exit_notes.get('notice_period_given_days') or exit_data.get('notice_period_given_days')
    notice_period_respected = exit_notes.get('notice_period_respected')
    if notice_period_respected is None:
        notice_period_respected = exit_data.get('notice_period_respected')

    # Déterminer si indemnité due
    notice_compensation_due = exit_notes.get('notice_compensation_due') or exit_data.get('notice_compensation_due')
    if notice_compensation_due is None:
        # Déduire si possible
        if probation_ended_by == 'employer' and notice_period_respected is False:
            notice_compensation_due = True
        elif probation_ended_by == 'employee':
            notice_compensation_due = False  # En général, pas d'indemnité si salarié rompt
        else:
            notice_compensation_due = None

    # En-tête entreprise
    pdf_helpers.build_company_header(story, styles, company_data)

    # Titre principal
    pdf_helpers.build_title_header(story, styles)

    # Informations salarié et date de sortie
    nom_complet = f"{employee_data.get('first_name', '')} {employee_data.get('last_name', '')}"
    date_sortie = pdf_helpers.format_date(exit_data.get('last_working_day', ''))

    story.append(Paragraph(
        f"Je soussigné(e) <b>{nom_complet}</b>, ayant quitté l'entreprise le {date_sortie} par <b>FIN / RUPTURE DE PÉRIODE D'ESSAI</b>, "
        f"reconnais avoir reçu les sommes suivantes :",
        styles['CorpsTexte']
    ))
    story.append(Spacer(1, 0.8*cm))

    # === SECTION 1 : RÉMUNÉRATIONS ACQUISES (SOCLE COMMUN) ===
    total_brut_remun, total_cotisations_remun, total_net_remun = socle_commun.build_remunerations_section(
        story, styles, employee_data, exit_data, section_number=1
    )

    # === SECTION 2 : PÉRIODE D'ESSAI ===
    story.append(Paragraph("<b>2. PÉRIODE D'ESSAI</b>", styles['Important']))
    story.append(Spacer(1, 0.3*cm))

    # Déterminer les libellés
    initiator_label = "Inconnu"
    if probation_ended_by == 'employee':
        initiator_label = "Salarié"
    elif probation_ended_by == 'employer':
        initiator_label = "Employeur"

    notice_respected_label = "Inconnu"
    if notice_period_respected is True:
        notice_respected_label = "Oui"
    elif notice_period_respected is False:
        notice_respected_label = "Non"

    notice_required_str = str(notice_period_required) if notice_period_required is not None else "Non renseigné"
    notice_given_str = str(notice_period_given) if notice_period_given is not None else "Non renseigné"

    data_periode_essai = [
        [Paragraph('<b>Information</b>', styles['Normal']),
         Paragraph('<b>Valeur</b>', styles['Normal'])],
        ['Rupture à l\'initiative', initiator_label],
        ['Délai de prévenance requis (jours)', notice_required_str],
        ['Délai de prévenance accordé (jours)', notice_given_str],
        ['Délai respecté', notice_respected_label]
    ]

    table_periode_essai = Table(data_periode_essai, colWidths=[8*cm, 8*cm])
    table_periode_essai.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e5e7eb')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#d1d5db')),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(table_periode_essai)
    story.append(Spacer(1, 0.6*cm))

    # === SECTION 3 : INDEMNITÉ COMPENSATRICE DE DÉLAI DE PRÉVENANCE ===
    story.append(Paragraph("<b>3. INDEMNITÉ COMPENSATRICE DE DÉLAI DE PRÉVENANCE</b>", styles['Important']))
    story.append(Spacer(1, 0.3*cm))

    indemnite_prevenance = indemnities.get('indemnite_delai_prevenance', {})
    montant_prevenance = pdf_helpers.safe_float(indemnite_prevenance.get('montant', 0))

    # Si l'indemnité est due mais non calculée, essayer de la calculer
    if notice_compensation_due and montant_prevenance == 0:
        # Le moteur devrait avoir calculé, mais si ce n'est pas le cas, on laisse vide
        detail_prevenance = "Indemnité due mais montant non calculé"
    elif notice_compensation_due:
        detail_prevenance = "Délai de prévenance non respecté - Indemnité compensatrice"
    elif notice_compensation_due is False:
        detail_prevenance = "Non applicable (délai respecté ou rupture salarié)"
    else:
        detail_prevenance = "Non renseigné ou non applicable"

    data_prevenance = [
        [Paragraph('<b>Libellé</b>', styles['Normal']),
         Paragraph('<b>Détails</b>', styles['Normal']),
         Paragraph('<b>Montant</b>', styles['Normal'])],
        [
            'Indemnité compensatrice de délai de prévenance (période d\'essai)',
            detail_prevenance,
            pdf_helpers.format_currency(montant_prevenance) if montant_prevenance > 0 else ''
        ]
    ]

    table_prevenance = Table(data_prevenance, colWidths=[6*cm, 7*cm, 3*cm])
    table_prevenance.setStyle(TableStyle([
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
    story.append(table_prevenance)
    story.append(Spacer(1, 0.6*cm))

    # === SECTION 4 : CONGÉS PAYÉS (SOCLE COMMUN) ===
    montant_conges = socle_commun.build_conges_section(story, styles, indemnities, section_number=4)

    # === SECTION 5 : AUTRES RÉGULARISATIONS (SOCLE COMMUN) ===
    socle_commun.build_autres_regularisations_section(story, styles, section_number=5)

    # === SECTION 6 : RETENUES ÉVENTUELLES (SOCLE COMMUN) ===
    socle_commun.build_retenues_section(story, styles, section_number=6)

    # === TOTAL GÉNÉRAL ===
    total_brut_final = total_brut_remun + montant_prevenance + montant_conges
    total_cotisations_final = total_cotisations_remun
    total_net_final = total_net_remun + montant_prevenance + montant_conges

    socle_commun.build_total_section(story, styles, total_brut_final, total_cotisations_final, total_net_final)

    # Mentions légales
    mention_periode_essai = "Fin / rupture du contrat pendant la période d'essai."
    if probation_ended_by == 'employer':
        mention_periode_essai += " Rupture à l'initiative de l'employeur."
    elif probation_ended_by == 'employee':
        mention_periode_essai += " Rupture à l'initiative du salarié."

    pdf_helpers.build_legal_mentions(story, styles, specific_mention=mention_periode_essai)

    # Signatures
    pdf_helpers.build_signatures(story, styles, company_data)

    # Pied de page
    pdf_helpers.build_footer(story, styles)

    # Build PDF
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes
