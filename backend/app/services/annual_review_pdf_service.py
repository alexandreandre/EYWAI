"""
PDF simplifié pour envoi signature (hors PDF « fiche clôturée » détaillé du module).

Utilise reportlab (déjà présent dans requirements.txt).
"""

from __future__ import annotations

import html
import io
from datetime import datetime
from typing import Any, Dict

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.shared.infrastructure.pdf.helpers import (
    build_branding_header_reportlab,
    get_company_signatory,
    setup_custom_styles,
)

from app.modules.annual_reviews.domain.interview_types import (
    INTERVIEW_TYPE_LABELS,
    interview_type_label,
)

INTERVIEW_TYPE_LABELS = INTERVIEW_TYPE_LABELS  # compat re-export

_L6315_MENTION = (
    "Conformément à l'article L.6315-1 du Code du travail, le présent entretien "
    "professionnel permet de faire le point sur les compétences et les perspectives "
    "d'évolution professionnelle du salarié."
)


def generate_review_pdf(review: Dict[str, Any], employee: Dict[str, Any]) -> bytes:
    """
    Génère un PDF court pour signature : en-tête entreprise + type + salarié + compte-rendu / notes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    styles = setup_custom_styles(styles)
    story = []

    company = review.get("company") if isinstance(review.get("company"), dict) else {}
    if company:
        build_branding_header_reportlab(story, styles, company)
        story.append(Spacer(1, 0.5 * cm))

    title_type = review.get("interview_type") or "annual_performance"
    type_label = INTERVIEW_TYPE_LABELS.get(str(title_type), str(title_type))

    story.append(Paragraph(f"<b>Entretien — {type_label}</b>", styles["Heading2"]))
    gen_date = datetime.now().strftime("%d/%m/%Y %H:%M")
    story.append(Paragraph(f"<i>Date du document : {gen_date}</i>", styles["Normal"]))
    story.append(Spacer(1, 0.5 * cm))

    if title_type == "professional_2ans":
        story.append(Paragraph(_L6315_MENTION, styles["Normal"]))
        story.append(Spacer(1, 0.4 * cm))

    fn = employee.get("first_name") or ""
    ln = employee.get("last_name") or ""
    jt = employee.get("job_title") or "—"
    story.append(Paragraph("<b>Salarié</b>", styles["Heading3"]))
    story.append(Paragraph(f"{fn} {ln}".strip() or "—", styles["Normal"]))
    story.append(Paragraph(f"Poste : {jt}", styles["Normal"]))
    pd = review.get("planned_date") or review.get("completed_date")
    if pd:
        pd_str = pd.isoformat() if hasattr(pd, "isoformat") else str(pd)
        story.append(
            Paragraph(f"Date entretien (prévue / réalisée) : {pd_str}", styles["Normal"])
        )
    story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph("<b>Compte-rendu / notes</b>", styles["Heading3"]))
    parts = []
    for key, label in (
        ("meeting_report", "Compte-rendu"),
        ("evaluation_summary", "Synthèse"),
        ("rh_notes", "Notes RH"),
        ("objectives_achieved", "Objectifs atteints"),
        ("objectives_next_year", "Objectifs à venir"),
        ("strengths", "Points forts"),
        ("improvement_areas", "Axes de progrès"),
    ):
        val = review.get(key)
        if val:
            text = html.escape(str(val)).replace("\n", "<br/>")
            parts.append(f"<b>{label}</b><br/>{text}")
    body = "<br/><br/>".join(parts) if parts else "<i>(Aucun compte-rendu saisi.)</i>"
    story.append(Paragraph(body, styles["Normal"]))
    story.append(Spacer(1, cm))

    signatory, signatory_title = get_company_signatory(company or {})
    sig_data = [
        ["", ""],
        ["Signature du salarié", "Signature du responsable RH"],
        [
            '(Précédée de la mention "Lu et approuvé")',
            f"{html.escape(signatory)}<br/><i>{html.escape(signatory_title)}</i>",
        ],
    ]
    sig_table = Table(sig_data, colWidths=[8 * cm, 8 * cm])
    sig_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 1), (-1, -1), "TOP"),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                ("TOPPADDING", (0, 0), (-1, 0), 24),
                ("BOTTOMPADDING", (0, 2), (-1, 2), 36),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
            ]
        )
    )
    story.append(sig_table)
    story.append(Spacer(1, 0.5 * cm))
    story.append(
        Paragraph(
            '<font size="8" color="grey">Document généré par EYWAI</font>',
            styles["Normal"],
        )
    )

    doc.build(story)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf
