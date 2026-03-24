"""
Génération PDF pour les entretiens annuels (fiche d'entretien clôturé).

Logique déplacée depuis services/annual_review_pdf_generator pour autonomie du module.
Utilise app.shared.infrastructure.pdf.helpers (setup_custom_styles, format_date).
Comportement identique au legacy.
"""
import io
from datetime import datetime
from typing import Any, Dict

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

from app.shared.infrastructure.pdf.helpers import format_date, setup_custom_styles


def generate_annual_review_pdf(
    review_data: Dict[str, Any],
    employee_data: Dict[str, Any],
    company_data: Dict[str, Any],
) -> bytes:
    """
    Génère un PDF professionnel pour un entretien annuel clôturé.
    Comportement identique à services.annual_review_pdf_generator.generate_annual_review_pdf.
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
        company_name = company_data.get("company_name", "")
        address_data = company_data.get("address")
        company_street = ""
        company_city = ""
        company_postal_code = ""
        if address_data:
            if isinstance(address_data, dict):
                company_street = address_data.get("street", "") or address_data.get("rue", "")
                company_city = address_data.get("city", "") or address_data.get("ville", "")
                company_postal_code = (
                    address_data.get("postal_code", "") or address_data.get("code_postal", "")
                )
            elif isinstance(address_data, str):
                company_street = address_data
        if not company_street:
            company_street = company_data.get("adresse_rue", "") or company_data.get("street", "")
        if not company_city:
            company_city = company_data.get("adresse_ville", "") or company_data.get("city", "")
        if not company_postal_code:
            company_postal_code = (
                company_data.get("adresse_code_postal", "") or company_data.get("postal_code", "")
            )
        company_info = company_name
        if company_street:
            company_info += f"\n{company_street}"
        if company_postal_code or company_city:
            company_info += f"\n{company_postal_code} {company_city}".strip()
        story.append(Paragraph(company_info, styles["EntrepriseHeader"]))
        story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph("FICHE D'ENTRETIEN", styles["TitrePrincipal"]))
    story.append(Spacer(1, 0.3 * cm))

    employee_name = (
        f"{employee_data.get('first_name', '')} {employee_data.get('last_name', '')}".strip()
    )
    job_title = employee_data.get("job_title", "")
    info_lines = []
    if employee_name:
        info_lines.append(f"<b>Employé :</b> {employee_name}")
    if job_title:
        info_lines.append(f"<b>Poste :</b> {job_title}")
    if review_data.get("planned_date"):
        info_lines.append(f"<b>Date prévue :</b> {format_date(review_data['planned_date'])}")
    if review_data.get("completed_date"):
        info_lines.append(f"<b>Date réalisée :</b> {format_date(review_data['completed_date'])}")
    if info_lines:
        story.append(Paragraph("<br/>".join(info_lines), styles["CorpsTexte"]))
        story.append(Spacer(1, 0.5 * cm))

    if review_data.get("rh_preparation_template"):
        story.append(Paragraph("<b>Notes de préparation RH</b>", styles["Important"]))
        story.append(Paragraph(review_data["rh_preparation_template"], styles["CorpsTexte"]))
        story.append(Spacer(1, 0.3 * cm))
    if review_data.get("employee_preparation_notes"):
        story.append(Paragraph("<b>Préparation de l'employé</b>", styles["Important"]))
        story.append(Paragraph(review_data["employee_preparation_notes"], styles["CorpsTexte"]))
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

    story.append(Spacer(1, 1 * cm))
    today = datetime.now().date()
    story.append(Paragraph(f"Document généré le {format_date(today)}", styles["Signature"]))
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
