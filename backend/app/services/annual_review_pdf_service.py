"""
PDF simplifié pour envoi signature (hors PDF « fiche clôturée » détaillé du module).

Utilise reportlab (déjà présent dans requirements.txt).
"""

from __future__ import annotations

import html
import io
from datetime import datetime
from typing import Any, Dict

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

INTERVIEW_TYPE_LABELS: Dict[str, str] = {
    "annual_performance": "Entretien annuel de performance",
    "professional_2ans": "Entretien professionnel (2 ans)",
    "competency_6ans": "Bilan de compétences (6 ans)",
    "return_absence": "Entretien de retour d'absence",
    "mid_year": "Entretien de mi-année",
    "other": "Autre",
}


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
    story = []

    company_name = ""
    # company peut être passée dans review si enrichi par l'appelant
    company = review.get("company") if isinstance(review.get("company"), dict) else None
    if company:
        company_name = company.get("company_name") or company.get("name") or ""
    title_type = review.get("interview_type") or "annual_performance"
    type_label = INTERVIEW_TYPE_LABELS.get(str(title_type), str(title_type))

    safe_company = html.escape(company_name or "Entreprise")
    story.append(Paragraph(f"<b>{safe_company}</b>", styles["Title"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(f"<b>Entretien — {type_label}</b>", styles["Heading2"]))
    gen_date = datetime.now().strftime("%d/%m/%Y %H:%M")
    story.append(Paragraph(f"<i>Date du document : {gen_date}</i>", styles["Normal"]))
    story.append(Spacer(1, 0.5 * cm))

    fn = employee.get("first_name") or ""
    ln = employee.get("last_name") or ""
    jt = employee.get("job_title") or "—"
    story.append(Paragraph("<b>Salarié</b>", styles["Heading3"]))
    story.append(Paragraph(f"{fn} {ln}".strip() or "—", styles["Normal"]))
    story.append(Paragraph(f"Poste : {jt}", styles["Normal"]))
    pd = review.get("planned_date") or review.get("completed_date")
    if pd:
        if hasattr(pd, "isoformat"):
            pd_str = pd.isoformat()
        else:
            pd_str = str(pd)
        story.append(Paragraph(f"Date entretien (prévue / réalisée) : {pd_str}", styles["Normal"]))
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

    story.append(Paragraph('<font size="8" color="grey">Document généré par EYWAI</font>', styles["Normal"]))

    doc.build(story)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf
