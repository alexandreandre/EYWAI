"""
PDF formatting helpers and style setup for Solde de Tout Compte documents
"""

from datetime import datetime, date
from typing import Any
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.lib import colors


def setup_custom_styles(base_styles):
    """
    Configure les styles personnalisés pour les documents

    Args:
        base_styles: ReportLab style sheet (from getSampleStyleSheet())

    Returns:
        Modified style sheet with custom styles added
    """
    # Style titre principal
    base_styles.add(ParagraphStyle(
        name='TitrePrincipal',
        parent=base_styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#1e3a8a'),
        spaceAfter=20,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    ))

    # Style pour les en-têtes d'entreprise
    base_styles.add(ParagraphStyle(
        name='EntrepriseHeader',
        parent=base_styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#1f2937'),
        spaceAfter=6,
        alignment=TA_LEFT
    ))

    # Style pour le corps de texte
    base_styles.add(ParagraphStyle(
        name='CorpsTexte',
        parent=base_styles['Normal'],
        fontSize=11,
        textColor=colors.black,
        spaceAfter=12,
        alignment=TA_JUSTIFY,
        leading=16
    ))

    # Style pour les informations importantes
    base_styles.add(ParagraphStyle(
        name='Important',
        parent=base_styles['Normal'],
        fontSize=11,
        textColor=colors.black,
        spaceAfter=10,
        fontName='Helvetica-Bold'
    ))

    # Style pour les signatures
    base_styles.add(ParagraphStyle(
        name='Signature',
        parent=base_styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#6b7280'),
        spaceAfter=6,
        alignment=TA_RIGHT
    ))

    return base_styles


def format_date(date_value: Any) -> str:
    """Formate une date en français"""
    if isinstance(date_value, str):
        try:
            date_value = datetime.fromisoformat(date_value.replace('Z', '+00:00')).date()
        except (ValueError, TypeError):
            try:
                date_value = datetime.strptime(date_value, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                return date_value

    if isinstance(date_value, (datetime, date)):
        mois_francais = [
            'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
            'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'
        ]
        return f"{date_value.day} {mois_francais[date_value.month - 1]} {date_value.year}"

    return str(date_value)


def format_currency(amount: float) -> str:
    """Formate un montant en euros"""
    return f"{amount:,.2f} €".replace(',', ' ')


def safe_float(value: Any, default: float = 0.0) -> float:
    """Convertit une valeur en float de manière sécurisée"""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_str(value: Any, default: str = "") -> str:
    """Convertit une valeur en string de manière sécurisée"""
    if value is None:
        return default
    try:
        return str(value)
    except Exception:
        return default


def build_company_header(story, styles, company_data):
    """Construit l'en-tête entreprise"""
    company_name = company_data.get('name') or company_data.get('raison_sociale') or 'Entreprise'
    company_address = company_data.get('address') or ''
    company_siret = company_data.get('siret') or ''

    from reportlab.platypus import Paragraph, Spacer
    from reportlab.lib.units import cm

    story.append(Paragraph(f"<b>{company_name}</b>", styles['EntrepriseHeader']))
    if company_address:
        story.append(Paragraph(company_address, styles['EntrepriseHeader']))
    if company_siret:
        story.append(Paragraph(f"SIRET : {company_siret}", styles['EntrepriseHeader']))
    story.append(Spacer(1, 0.8*cm))


def build_title_header(story, styles):
    """Construit le titre principal"""
    from reportlab.platypus import Paragraph, Spacer
    from reportlab.lib.units import cm

    story.append(Paragraph("REÇU POUR SOLDE DE TOUT COMPTE", styles['TitrePrincipal']))
    story.append(Spacer(1, 0.5*cm))


def build_legal_mentions(story, styles, specific_mention: str = None):
    """Construit les mentions légales"""
    from reportlab.platypus import Paragraph, Spacer
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib import colors
    from reportlab.lib.units import cm

    # Mention légale de quittance
    texte_quittance = """
    <b>Le présent reçu vaut quittance pour solde de tout compte.</b><br/><br/>
    Je reconnais avoir pris connaissance de la faculté de dénonciation qui m'est offerte
    par l'article D1234-7 du Code du travail, aux termes duquel je dispose d'un délai
    de six mois à compter de ce jour pour dénoncer les sommes qui m'auraient été réglées
    par l'employeur.
    """
    story.append(Paragraph(texte_quittance, styles['Important']))
    story.append(Spacer(1, 0.5*cm))

    # Mention légale spécifique (optionnelle)
    if specific_mention:
        story.append(Paragraph(
            f"<i>{specific_mention}</i>",
            ParagraphStyle(
                name='MentionLegaleSpecific',
                parent=styles['Normal'],
                fontSize=9,
                textColor=colors.HexColor('#6b7280'),
                alignment=TA_LEFT
            )
        ))
        story.append(Spacer(1, 0.3*cm))

    # Mention légale article L1234-20
    story.append(Paragraph(
        "<i>Le présent reçu est établi en application de l'article L1234-20 du Code du travail</i>",
        ParagraphStyle(
            name='MentionLegaleArticle',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#6b7280'),
            alignment=TA_LEFT
        )
    ))
    story.append(Spacer(1, 1*cm))


def build_signatures(story, styles, company_data):
    """Construit la section signatures"""
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.units import cm
    from datetime import datetime

    date_aujourd_hui = format_date(datetime.now().date())
    company_city = company_data.get('city') or '___________'

    data_signatures = [
        ['Fait en double exemplaire', ''],
        [f"À {company_city}, le {date_aujourd_hui}", ''],
        ['', ''],
        [Paragraph('<b>Signature du salarié</b>', styles['Normal']),
         Paragraph('<b>Signature de l\'employeur</b>', styles['Normal'])],
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


def build_footer(story, styles, articles: str = "Articles D1234-7 et L1234-20 du Code du travail"):
    """Construit le pied de page"""
    from reportlab.platypus import Paragraph
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib import colors

    story.append(Paragraph(
        f"<i>{articles}</i>",
        ParagraphStyle(
            name='MentionLegale',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#9ca3af'),
            alignment=TA_CENTER
        )
    ))
