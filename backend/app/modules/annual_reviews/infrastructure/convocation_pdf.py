"""
Génération PDF de la lettre de convocation à un entretien (RH → salarié).

Format standard en attendant le modèle définitif Colorplast.
"""

from __future__ import annotations

import io
from datetime import date, datetime
from typing import Any, Dict

from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.modules.annual_reviews.domain.interview_types import interview_type_label
from app.shared.infrastructure.pdf.helpers import (
    build_branding_header_reportlab,
    format_date,
    get_company_signatory,
    safe_str,
    setup_custom_styles,
)


def _format_planned_datetime(planned_date: Any) -> str:
    if not planned_date:
        return "date à confirmer"
    if isinstance(planned_date, datetime):
        return planned_date.strftime("%d/%m/%Y à %H:%M")
    if isinstance(planned_date, date):
        return format_date(planned_date)
    s = str(planned_date)
    if "T" in s:
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return dt.strftime("%d/%m/%Y à %H:%M")
        except ValueError:
            pass
    return format_date(s) if s else "date à confirmer"


def generate_convocation_pdf(
    review_data: Dict[str, Any],
    employee_data: Dict[str, Any],
    company_data: Dict[str, Any],
) -> bytes:
    """Génère la lettre de convocation PDF pour un entretien transmis au salarié."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    story = []
    styles = getSampleStyleSheet()
    styles = setup_custom_styles(styles)
    styles.add(
        ParagraphStyle(
            name="ConvocTitle",
            parent=styles["TitrePrincipal"],
            fontSize=14,
            spaceAfter=16,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ConvocRight",
            parent=styles["Normal"],
            fontSize=11,
            alignment=TA_RIGHT,
            spaceAfter=6,
        )
    )

    if company_data:
        build_branding_header_reportlab(story, styles, company_data)
        story.append(Spacer(1, 0.5 * cm))

    today_str = date.today().strftime("%d/%m/%Y")
    story.append(Paragraph(f"<b>{today_str}</b>", styles["ConvocRight"]))
    story.append(Spacer(1, 0.6 * cm))

    employee_name = (
        f"{employee_data.get('first_name', '')} {employee_data.get('last_name', '')}"
    ).strip()
    job_title = safe_str(employee_data.get("job_title")) or "—"
    interview_label = interview_type_label(review_data.get("interview_type"))
    planned_str = _format_planned_datetime(review_data.get("planned_date"))
    company_name = safe_str(company_data.get("company_name")) or "l'entreprise"

    story.append(Paragraph("CONVOCATION À UN ENTRETIEN", styles["ConvocTitle"]))
    story.append(Spacer(1, 0.3 * cm))

    story.append(
        Paragraph(
            f"<b>À l'attention de :</b> {employee_name}<br/>"
            f"<b>Fonction :</b> {job_title}",
            styles["CorpsTexte"],
        )
    )
    story.append(Spacer(1, 0.4 * cm))

    body = f"""
    Madame, Monsieur,<br/><br/>
    Nous avons l'honneur de vous convoquer à un <b>{interview_label}</b>
    qui se tiendra le <b>{planned_str}</b> au sein de {company_name}.<br/><br/>
    Cet entretien a pour objet de faire un point sur votre parcours, vos missions
    et, le cas échéant, vos perspectives d'évolution professionnelle.<br/><br/>
    Nous vous remercions de bien vouloir accuser réception de la présente convocation
    et de vous présenter muni(e) de vos éléments de préparation.<br/><br/>
    Veuillez agréer, Madame, Monsieur, l'expression de nos salutations distinguées.
    """
    story.append(Paragraph(body, styles["CorpsTexte"]))
    story.append(Spacer(1, 1.2 * cm))

    signatory, signatory_title = get_company_signatory(company_data or {})
    story.append(Paragraph(f"<b>{signatory}</b>", styles["ConvocRight"]))
    story.append(Paragraph(f"<i>{signatory_title}</i>", styles["ConvocRight"]))
    story.append(Spacer(1, 1.5 * cm))
    story.append(
        Paragraph(
            "<i>Document généré électroniquement — valant convocation.</i>",
            styles["Signature"],
        )
    )

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
