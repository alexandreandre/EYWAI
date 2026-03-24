"""
Common sections (socle commun) for Solde de Tout Compte PDF generation
These sections are shared across all termination types
"""

from datetime import datetime, date
from typing import Dict, Any, List, Tuple
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors

from .pdf_helpers import safe_float, format_currency


def get_salary_prorata(employee_data: Dict[str, Any], exit_data: Dict[str, Any]) -> Dict[str, Any]:
    """Calcule le prorata du salaire du dernier mois"""
    try:
        salaire_base_obj = employee_data.get('salaire_de_base', {})
        if isinstance(salaire_base_obj, dict):
            salaire_base = safe_float(salaire_base_obj.get('valeur', 0))
        else:
            salaire_base = safe_float(salaire_base_obj, 0)

        # Date de fin du contrat
        exit_date_str = exit_data.get('last_working_day', '')
        if isinstance(exit_date_str, str):
            exit_date = datetime.fromisoformat(exit_date_str.replace('Z', '+00:00')).date()
        else:
            exit_date = exit_date_str

        # Date de début du mois
        mois_debut = date(exit_date.year, exit_date.month, 1)

        # Nombre de jours dans le mois
        if exit_date.month == 12:
            mois_fin = date(exit_date.year + 1, 1, 1)
        else:
            mois_fin = date(exit_date.year, exit_date.month + 1, 1)
        jours_dans_mois = (mois_fin - mois_debut).days

        # Nombre de jours travaillés dans le mois
        jours_travailles = (exit_date - mois_debut).days + 1

        # Prorata
        salaire_prorata = (salaire_base / jours_dans_mois) * jours_travailles if jours_dans_mois > 0 else 0

        return {
            'base_mensuelle': salaire_base,
            'jours_dans_mois': jours_dans_mois,
            'jours_travailles': jours_travailles,
            'montant_brut': salaire_prorata,
            'cotisations': 0.0,  # À calculer si nécessaire
            'net': salaire_prorata  # Approximation
        }
    except Exception as e:
        return {
            'base_mensuelle': 0.0,
            'jours_dans_mois': 0,
            'jours_travailles': 0,
            'montant_brut': 0.0,
            'cotisations': 0.0,
            'net': 0.0
        }


def build_remunerations_section(
    story: List,
    styles: Dict,
    employee_data: Dict[str, Any],
    exit_data: Dict[str, Any],
    section_number: int = 1
) -> Tuple[float, float, float]:
    """
    Construit la section Rémunérations acquises (Section 1)

    Returns:
        Tuple de (total_brut, total_cotisations, total_net)
    """
    story.append(Paragraph(f"<b>{section_number}. RÉMUNÉRATIONS ACQUISES</b>", styles['Important']))
    story.append(Spacer(1, 0.3*cm))

    data_remunerations = [
        [Paragraph('<b>Libellé</b>', styles['Normal']),
         Paragraph('<b>Détails</b>', styles['Normal']),
         Paragraph('<b>Montant brut</b>', styles['Normal']),
         Paragraph('<b>Cotisations</b>', styles['Normal']),
         Paragraph('<b>Net</b>', styles['Normal'])]
    ]

    total_brut_remun = 0.0
    total_cotisations_remun = 0.0
    total_net_remun = 0.0

    # 1. Salaire du dernier mois (proratisé)
    salaire_data = get_salary_prorata(employee_data, exit_data)
    base_mensuelle = safe_float(salaire_data.get('base_mensuelle', 0))
    jours_trav = salaire_data.get('jours_travailles', 0)
    jours_mois = salaire_data.get('jours_dans_mois', 0)
    brut_salaire = safe_float(salaire_data.get('montant_brut', 0))
    cotis_salaire = safe_float(salaire_data.get('cotisations', 0))
    net_salaire = safe_float(salaire_data.get('net', brut_salaire))

    detail_salaire = f"Base : {format_currency(base_mensuelle)} / {jours_mois} jours × {jours_trav} jours"
    if base_mensuelle == 0:
        detail_salaire = "Non renseigné"

    data_remunerations.append([
        'Salaire du dernier mois',
        detail_salaire,
        format_currency(brut_salaire) if brut_salaire > 0 else '',
        format_currency(cotis_salaire) if cotis_salaire > 0 else '',
        format_currency(net_salaire) if net_salaire > 0 else ''
    ])
    total_brut_remun += brut_salaire
    total_cotisations_remun += cotis_salaire
    total_net_remun += net_salaire

    # 2. Heures supplémentaires / complémentaires
    hs_brut = 0.0
    detail_hs = "Aucune heure supplémentaire enregistrée"
    data_remunerations.append([
        'Heures supplémentaires / complémentaires',
        detail_hs,
        format_currency(hs_brut) if hs_brut > 0 else '',
        '',
        ''
    ])
    total_brut_remun += hs_brut

    # 3. Primes et variables acquises
    primes_total = 0.0
    detail_primes = "Aucune prime acquise enregistrée"
    data_remunerations.append([
        'Primes et variables acquises',
        detail_primes,
        format_currency(primes_total) if primes_total > 0 else '',
        '',
        ''
    ])
    total_brut_remun += primes_total

    # 4. Avantages en nature
    avantages_total = 0.0
    detail_avantages = "Aucun avantage en nature"
    data_remunerations.append([
        'Avantages en nature',
        detail_avantages,
        format_currency(avantages_total) if avantages_total > 0 else '',
        '',
        ''
    ])
    total_brut_remun += avantages_total

    # Total rémunérations
    data_remunerations.append(['', '', '', '', ''])
    data_remunerations.append([
        Paragraph('<b>Total rémunérations acquises</b>', styles['Normal']),
        '',
        Paragraph(f'<b>{format_currency(total_brut_remun)}</b>', styles['Normal']),
        Paragraph(f'<b>{format_currency(total_cotisations_remun)}</b>', styles['Normal']),
        Paragraph(f'<b>{format_currency(total_net_remun)}</b>', styles['Normal'])
    ])

    table_remun = Table(data_remunerations, colWidths=[4*cm, 5*cm, 2.5*cm, 2.5*cm, 2.5*cm])
    table_remun.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e5e7eb')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1f2937')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (2, 1), (-1, -2), 'RIGHT'),
        ('ALIGN', (2, -1), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -2), 1, colors.HexColor('#d1d5db')),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#1e3a8a')),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#dbeafe')),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(table_remun)
    story.append(Spacer(1, 0.6*cm))

    return total_brut_remun, total_cotisations_remun, total_net_remun


def build_conges_section(
    story: List,
    styles: Dict,
    indemnities: Dict[str, Any],
    section_number: int = 4,
    include_cp_preavis: bool = False
) -> float:
    """
    Construit la section Congés payés

    Args:
        include_cp_preavis: Si True, ajoute une ligne pour CP afférents au préavis

    Returns:
        Montant total des congés payés
    """
    story.append(Paragraph(f"<b>{section_number}. CONGÉS PAYÉS</b>", styles['Important']))
    story.append(Spacer(1, 0.3*cm))

    indemnite_conges = indemnities.get('indemnite_conges', {})
    jours_restants = safe_float(indemnite_conges.get('jours_restants', 0))
    montant_conges = safe_float(indemnite_conges.get('montant', 0))
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

    data_conges = [
        [Paragraph('<b>Libellé</b>', styles['Normal']),
         Paragraph('<b>Détails</b>', styles['Normal']),
         Paragraph('<b>Montant</b>', styles['Normal'])],
        [
            'Indemnité compensatrice de congés payés',
            detail_conges_text,
            format_currency(montant_conges) if montant_conges > 0 else ''
        ]
    ]

    # Option A : Ligne séparée pour CP sur préavis si préavis indemnisé
    montant_cp_preavis = 0.0
    if include_cp_preavis:
        cp_preavis_text = "Non applicable ou non calculé"
        # TODO: Récupérer depuis indemnities si disponible
        data_conges.append([
            'Congés payés afférents au préavis',
            cp_preavis_text,
            format_currency(montant_cp_preavis) if montant_cp_preavis > 0 else ''
        ])

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

    return montant_conges + montant_cp_preavis


def build_autres_regularisations_section(
    story: List,
    styles: Dict,
    section_number: int = 5
) -> None:
    """Construit la section Autres régularisations"""
    story.append(Paragraph(f"<b>{section_number}. AUTRES RÉGULARISATIONS</b>", styles['Important']))
    story.append(Spacer(1, 0.3*cm))

    data_autres = [
        [Paragraph('<b>Libellé</b>', styles['Normal']),
         Paragraph('<b>Détails</b>', styles['Normal']),
         Paragraph('<b>Montant</b>', styles['Normal'])],
        ['RTT / repos compensateurs', 'Aucun RTT ou repos compensateur non pris enregistré', ''],
        ['Frais professionnels', 'Aucune note de frais validée non remboursée enregistrée', '']
    ]

    table_autres = Table(data_autres, colWidths=[6*cm, 7*cm, 3*cm])
    table_autres.setStyle(TableStyle([
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
    story.append(table_autres)
    story.append(Spacer(1, 0.6*cm))


def build_retenues_section(
    story: List,
    styles: Dict,
    section_number: int = 6
) -> None:
    """Construit la section Retenues éventuelles"""
    story.append(Paragraph(f"<b>{section_number}. RETENUES ÉVENTUELLES</b>", styles['Important']))
    story.append(Spacer(1, 0.3*cm))

    data_retenues = [
        [Paragraph('<b>Libellé</b>', styles['Normal']),
         Paragraph('<b>Détails</b>', styles['Normal']),
         Paragraph('<b>Montant</b>', styles['Normal'])],
        ['Retenues sur salaire', 'Aucune retenue enregistrée', '']
    ]

    table_retenues = Table(data_retenues, colWidths=[6*cm, 7*cm, 3*cm])
    table_retenues.setStyle(TableStyle([
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
    story.append(table_retenues)
    story.append(Spacer(1, 0.8*cm))


def build_total_section(
    story: List,
    styles: Dict,
    total_brut: float,
    total_cotisations: float,
    total_net: float
) -> None:
    """Construit la section Total général"""
    data_total = [
        ['', Paragraph('<b>TOTAL BRUT</b>', styles['Normal']),
         Paragraph(f'<b>{format_currency(total_brut)}</b>', styles['Normal'])],
        ['', Paragraph('<b>TOTAL COTISATIONS</b>', styles['Normal']),
         Paragraph(f'<b>{format_currency(total_cotisations)}</b>', styles['Normal'])],
        ['', Paragraph('<b>TOTAL NET À PAYER</b>', styles['Normal']),
         Paragraph(f'<b>{format_currency(total_net)}</b>', styles['Normal'])]
    ]

    table_total = Table(data_total, colWidths=[6*cm, 7*cm, 3*cm])
    table_total.setStyle(TableStyle([
        ('FONTNAME', (1, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('LINEABOVE', (1, 0), (2, 0), 2, colors.HexColor('#1e3a8a')),
        ('BACKGROUND', (1, -1), (2, -1), colors.HexColor('#dbeafe')),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(table_total)
    story.append(Spacer(1, 0.8*cm))
