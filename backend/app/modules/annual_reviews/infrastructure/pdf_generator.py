"""
Génération PDF pour les entretiens annuels (fiche d'entretien clôturé).

Logique déplacée depuis services/annual_review_pdf_generator pour autonomie du module.
Utilise app.shared.infrastructure.pdf.helpers (setup_custom_styles, format_date).
Comportement identique au legacy.
"""

import io
from datetime import datetime
from typing import Any, Dict

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.modules.annual_reviews.domain.interview_types import L6315_INTERVIEW_TYPES
from app.shared.infrastructure.pdf.helpers import (
    build_branding_header_reportlab,
    format_date,
    get_company_signatory,
    setup_custom_styles,
)

_L6315_MENTION = (
    "Conformément à l'article L.6315-1 du Code du travail, le présent entretien "
    "professionnel permet de faire le point sur les compétences et les perspectives "
    "d'évolution professionnelle du salarié."
)


def generate_annual_review_pdf(
    review_data: Dict[str, Any],
    employee_data: Dict[str, Any],
    company_data: Dict[str, Any],
) -> bytes:
    """
    Génère un PDF professionnel pour un entretien annuel clôturé.
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
    story = []
    styles = getSampleStyleSheet()
    styles = setup_custom_styles(styles)

    if company_data:
        build_branding_header_reportlab(story, styles, company_data)
        story.append(Spacer(1, 0.5 * cm))

    interview_type = review_data.get("interview_type") or "annual_performance"
    title = "FICHE D'ENTRETIEN"
    if interview_type in L6315_INTERVIEW_TYPES or interview_type == "professional_2ans":
        title = "ENTRETIEN PROFESSIONNEL"
    elif interview_type == "annual_cadres":
        title = "ENTRETIEN ANNUEL DES CADRES"
    elif interview_type == "annual_forfait_jour":
        title = "ENTRETIEN ANNUEL FORFAIT JOUR"
    story.append(Paragraph(title, styles["TitrePrincipal"]))
    story.append(Spacer(1, 0.3 * cm))

    employee_name = (
        f"{employee_data.get('first_name', '')} {employee_data.get('last_name', '')}"
    ).strip()
    job_title = employee_data.get("job_title", "")
    info_lines = []
    if employee_name:
        info_lines.append(f"<b>Employé :</b> {employee_name}")
    if job_title:
        info_lines.append(f"<b>Poste :</b> {job_title}")
    if review_data.get("planned_date"):
        info_lines.append(
            f"<b>Date prévue :</b> {format_date(review_data['planned_date'])}"
        )
    if review_data.get("completed_date"):
        info_lines.append(
            f"<b>Date réalisée :</b> {format_date(review_data['completed_date'])}"
        )
    if info_lines:
        story.append(Paragraph("<br/>".join(info_lines), styles["CorpsTexte"]))
        story.append(Spacer(1, 0.5 * cm))

    if interview_type in L6315_INTERVIEW_TYPES or interview_type == "professional_2ans":
        story.append(Paragraph(_L6315_MENTION, styles["CorpsTexte"]))
        story.append(Spacer(1, 0.4 * cm))

    if review_data.get("rh_preparation_template"):
        story.append(Paragraph("<b>Notes de préparation RH</b>", styles["Important"]))
        story.append(
            Paragraph(review_data["rh_preparation_template"], styles["CorpsTexte"])
        )
        story.append(Spacer(1, 0.3 * cm))
    if review_data.get("employee_preparation_notes"):
        story.append(Paragraph("<b>Préparation de l'employé</b>", styles["Important"]))
        story.append(
            Paragraph(review_data["employee_preparation_notes"], styles["CorpsTexte"])
        )
        story.append(Spacer(1, 0.3 * cm))
    if review_data.get("meeting_report"):
        story.append(Paragraph("<b>Compte-rendu d'entretien</b>", styles["Important"]))
        story.append(Paragraph(review_data["meeting_report"], styles["CorpsTexte"]))
        story.append(Spacer(1, 0.3 * cm))

    has_evaluation = any(
        [
            review_data.get("evaluation_summary"),
            review_data.get("objectives_achieved"),
            review_data.get("objectives_next_year"),
            review_data.get("strengths"),
            review_data.get("improvement_areas"),
            review_data.get("training_needs"),
            review_data.get("career_development"),
            review_data.get("salary_review"),
            review_data.get("overall_rating"),
        ]
    )
    if has_evaluation:
        story.append(Paragraph("<b>Évaluation et suivi</b>", styles["Important"]))
        story.append(Spacer(1, 0.2 * cm))
        for label, key in [
            ("Résumé de l'évaluation :", "evaluation_summary"),
            ("Objectifs atteints :", "objectives_achieved"),
            ("Objectifs futurs :", "objectives_next_year"),
            ("Points forts :", "strengths"),
            ("Axes d'amélioration :", "improvement_areas"),
            ("Besoins en formation :", "training_needs"),
            ("Évolution professionnelle :", "career_development"),
            ("Revue salariale :", "salary_review"),
            ("Note globale :", "overall_rating"),
        ]:
            if review_data.get(key):
                story.append(Paragraph(f"<b>{label}</b>", styles["CorpsTexte"]))
                story.append(Paragraph(review_data[key], styles["CorpsTexte"]))
                story.append(Spacer(1, 0.2 * cm))

    if review_data.get("rh_notes"):
        story.append(Paragraph("<b>Notes RH complémentaires</b>", styles["Important"]))
        story.append(Paragraph(review_data["rh_notes"], styles["CorpsTexte"]))
        story.append(Spacer(1, 0.3 * cm))

    story.append(Spacer(1, 0.8 * cm))
    today = datetime.now().date()
    story.append(
        Paragraph(f"Document généré le {format_date(today)}", styles["Signature"])
    )
    story.append(Spacer(1, 0.8 * cm))

    signatory, signatory_title = get_company_signatory(company_data or {})
    sig_data = [
        ["", ""],
        ["Signature du salarié", "Signature du responsable RH"],
        [
            '(Précédée de la mention "Lu et approuvé")',
            f"{signatory}<br/><i>{signatory_title}</i>",
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

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
