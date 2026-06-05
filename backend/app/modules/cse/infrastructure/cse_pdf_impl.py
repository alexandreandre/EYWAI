# app/modules/cse/infrastructure/cse_pdf_impl.py
"""
Génération PDF CSE (convocations, PV, calendrier électoral).
Implémentation autonome ex-services.cse_pdf_service.
"""

import io
from datetime import datetime
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.shared.infrastructure.pdf.helpers import (
    build_branding_header_reportlab,
    setup_custom_styles,
)


def _format_meeting_date(meeting_date: Any) -> str:
    if not meeting_date:
        return "—"
    date_obj = (
        datetime.fromisoformat(meeting_date)
        if isinstance(meeting_date, str)
        else meeting_date
    )
    return date_obj.strftime("%d/%m/%Y")


def _participant_names(participants: List[Dict[str, Any]]) -> List[str]:
    names = []
    for participant in participants or []:
        name = (
            f"{participant.get('first_name', '')} {participant.get('last_name', '')}"
        ).strip()
        if name:
            names.append(name)
    return names


def generate_convocation_pdf(meeting_data: Dict[str, Any]) -> bytes:
    """
    Génère le PDF de convocation pour une réunion CSE.
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
    story: List[Any] = []
    styles = getSampleStyleSheet()
    styles = setup_custom_styles(styles)
    styles.add(
        ParagraphStyle(
            name="CSETitle",
            parent=styles["Heading1"],
            fontSize=16,
            textColor=colors.HexColor("#1e40af"),
            spaceAfter=20,
            alignment=TA_CENTER,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CSEBody",
            parent=styles["Normal"],
            fontSize=11,
            alignment=TA_JUSTIFY,
            leading=14,
        )
    )

    company_data = meeting_data.get("company_data") or {}
    if company_data:
        build_branding_header_reportlab(story, styles, company_data)
        story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph("CONVOCATION — RÉUNION DU CSE", styles["CSETitle"]))
    story.append(Spacer(1, 0.4 * cm))

    meeting_type = meeting_data.get("meeting_type", "ordinaire")
    type_labels = {
        "ordinaire": "Réunion ordinaire",
        "extraordinaire": "Réunion extraordinaire",
        "cssct": "CSSCT",
        "autre": "Autre",
    }
    type_label = type_labels.get(meeting_type, meeting_type)
    date_str = _format_meeting_date(meeting_data.get("meeting_date"))
    meeting_time = meeting_data.get("meeting_time") or "—"
    location = meeting_data.get("location") or "—"

    intro = f"""
    Conformément aux dispositions du Code du travail relatives au Comité social
    et économique, vous êtes convoqué(e) à la <b>{type_label.lower()}</b>
    du Comité social et économique.
    """
    story.append(Paragraph(intro, styles["CSEBody"]))
    story.append(Spacer(1, 0.4 * cm))

    info_rows = [
        ["Objet", meeting_data.get("title", "—")],
        ["Date", date_str],
        ["Heure", meeting_time],
        ["Lieu", location],
        ["Type", type_label],
    ]
    info_table = Table(info_rows, colWidths=[4 * cm, 12 * cm])
    info_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f3f4f6")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(info_table)
    story.append(Spacer(1, 0.5 * cm))

    legal_delay = (
        "Rappel : la convocation doit être adressée aux membres titulaires et "
        "suppléants du CSE au moins <b>3 jours francs</b> avant la date de la "
        "réunion (article L.2313-5 du Code du travail), sauf urgence pour une "
        "réunion extraordinaire."
    )
    story.append(Paragraph(legal_delay, styles["CSEBody"]))
    story.append(Spacer(1, 0.5 * cm))

    participants = meeting_data.get("participants", [])
    names = _participant_names(participants)
    if names:
        story.append(Paragraph("<b>Destinataires convoqués :</b>", styles["Heading3"]))
        for name in names:
            story.append(Paragraph(f"• {name}", styles["Normal"]))
        story.append(Spacer(1, 0.4 * cm))

    agenda = meeting_data.get("agenda")
    story.append(Paragraph("<b>Ordre du jour :</b>", styles["Heading3"]))
    if agenda:
        if isinstance(agenda, dict):
            for key, value in agenda.items():
                story.append(
                    Paragraph(f"<b>{key} :</b> {value}", styles["Normal"])
                )
        elif isinstance(agenda, list):
            for item in agenda:
                story.append(Paragraph(f"• {item}", styles["Normal"]))
        else:
            story.append(Paragraph(str(agenda), styles["Normal"]))
    else:
        story.append(Paragraph("—", styles["Normal"]))
    story.append(Spacer(1, 0.8 * cm))

    sent_date = meeting_data.get("convocation_sent_date") or "…………………"
    story.append(
        Paragraph(f"<b>Date d'envoi de la convocation :</b> {sent_date}", styles["Normal"])
    )
    story.append(Spacer(1, 1.2 * cm))
    story.append(Paragraph("<b>Le Président du CSE</b>", styles["Normal"]))
    story.append(Spacer(1, 1.5 * cm))
    story.append(Paragraph("Signature :", styles["Normal"]))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()


def generate_minutes_pdf(
    meeting_data: Dict[str, Any],
    transcription: Optional[str] = None,
    summary: Optional[Dict[str, Any]] = None,
) -> bytes:
    """Génère le PDF du procès-verbal depuis la transcription et la synthèse IA."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    story: List[Any] = []
    styles = getSampleStyleSheet()
    styles = setup_custom_styles(styles)
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=16,
        textColor=colors.HexColor("#1e40af"),
        spaceAfter=20,
        alignment=TA_CENTER,
    )

    company_data = meeting_data.get("company_data") or {}
    if company_data:
        build_branding_header_reportlab(story, styles, company_data)
        story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph("PROCÈS-VERBAL DE RÉUNION CSE", title_style))
    story.append(Spacer(1, 0.4 * cm))

    story.append(
        Paragraph(
            f"<b>Réunion :</b> {meeting_data.get('title', 'N/A')}",
            styles["Normal"],
        )
    )
    story.append(
        Paragraph(
            f"<b>Date :</b> {_format_meeting_date(meeting_data.get('meeting_date'))}",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 0.4 * cm))

    participants = meeting_data.get("participants", [])
    names = _participant_names(participants)
    story.append(Paragraph("<b>Liste de présence :</b>", styles["Heading3"]))
    if names:
        for name in names:
            story.append(Paragraph(f"• {name}", styles["Normal"]))
    else:
        story.append(Paragraph("Présents : —", styles["Normal"]))
    story.append(Spacer(1, 0.4 * cm))

    if summary:
        story.append(Paragraph("<b>Résumé :</b>", styles["Heading2"]))
        key_points = summary.get("key_points", [])
        if key_points:
            story.append(Paragraph("<b>Points clés :</b>", styles["Heading3"]))
            for point in key_points:
                story.append(Paragraph(f"• {point}", styles["Normal"]))
            story.append(Spacer(1, 0.3 * cm))

        decisions = summary.get("decisions", [])
        if decisions:
            story.append(Paragraph("<b>Décisions prises :</b>", styles["Heading3"]))
            for decision in decisions:
                story.append(Paragraph(f"• {decision}", styles["Normal"]))
            story.append(Spacer(1, 0.3 * cm))

        actions = summary.get("actions", [])
        if actions:
            story.append(Paragraph("<b>Actions à suivre :</b>", styles["Heading3"]))
            for action in actions:
                story.append(Paragraph(f"• {action}", styles["Normal"]))
            story.append(Spacer(1, 0.3 * cm))

    if transcription:
        story.append(PageBreak())
        story.append(Paragraph("<b>Transcription complète :</b>", styles["Heading2"]))
        story.append(Spacer(1, 0.3 * cm))
        for para in transcription.split("\n\n"):
            if para.strip():
                story.append(Paragraph(para.strip(), styles["Normal"]))
                story.append(Spacer(1, 0.2 * cm))

    story.append(Spacer(1, 0.8 * cm))
    story.append(
        Paragraph(
            "Le présent procès-verbal a été approuvé par les membres présents "
            "lors de la réunion ou lors de la réunion suivante.",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 1 * cm))

    sig_data = [
        ["", ""],
        ["Signature du Secrétaire", "Signature du Président"],
        ["", ""],
    ]
    sig_table = Table(sig_data, colWidths=[8 * cm, 8 * cm])
    sig_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                ("TOPPADDING", (0, 0), (-1, 0), 30),
                ("BOTTOMPADDING", (0, 2), (-1, 2), 40),
            ]
        )
    )
    story.append(sig_table)

    doc.build(story)
    buffer.seek(0)
    return buffer.read()


def generate_election_calendar_pdf(
    cycle_data: Dict[str, Any], timeline: List[Dict[str, Any]]
) -> bytes:
    """Génère le PDF du calendrier des obligations sociales."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    story: List[Any] = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=colors.HexColor("#1e40af"),
        spaceAfter=30,
        alignment=TA_CENTER,
    )

    company_data = cycle_data.get("company_data") or {}
    if company_data:
        styles = setup_custom_styles(styles)
        build_branding_header_reportlab(story, styles, company_data)
        story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph("CALENDRIER DES OBLIGATIONS SOCIALES", title_style))
    story.append(Spacer(1, 0.5 * cm))

    story.append(
        Paragraph(
            f"<b>Cycle:</b> {cycle_data.get('cycle_name', 'N/A')}",
            styles["Normal"],
        )
    )

    mandate_end = cycle_data.get("mandate_end_date")
    if mandate_end:
        story.append(
            Paragraph(
                f"<b>Fin de mandat:</b> {_format_meeting_date(mandate_end)}",
                styles["Normal"],
            )
        )

    election_date = cycle_data.get("election_date")
    if election_date:
        story.append(
            Paragraph(
                f"<b>Date des élections:</b> {_format_meeting_date(election_date)}",
                styles["Normal"],
            )
        )

    story.append(Spacer(1, 0.5 * cm))

    if timeline:
        story.append(
            Paragraph("<b>Étapes du calendrier électoral:</b>", styles["Heading2"])
        )
        story.append(Spacer(1, 0.3 * cm))

        table_data = [["Étape", "Date butoir", "Statut"]]
        for step in sorted(timeline, key=lambda x: x.get("step_order", 0)):
            step_name = step.get("step_name", "N/A")
            due_date = step.get("due_date", "")
            due_date_str = _format_meeting_date(due_date) if due_date else "N/A"
            status = step.get("status", "pending")
            status_labels = {
                "pending": "En attente",
                "completed": "Terminée",
                "overdue": "En retard",
            }
            table_data.append([step_name, due_date_str, status_labels.get(status, status)])

        table = Table(table_data, colWidths=[8 * cm, 4 * cm, 3 * cm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 12),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ]
            )
        )
        story.append(table)

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
