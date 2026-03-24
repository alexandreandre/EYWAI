# app/modules/cse/infrastructure/cse_pdf_impl.py
"""
Génération PDF CSE (convocations, PV, calendrier électoral).
Implémentation autonome ex-services.cse_pdf_service.
"""

import io
from datetime import datetime, date
from typing import Dict, Any, Optional, List
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors


def generate_convocation_pdf(meeting_data: Dict[str, Any]) -> bytes:
    """
    Génère le PDF de convocation pour une réunion CSE.
    
    Args:
        meeting_data: Données de la réunion (titre, date, heure, lieu, participants, agenda)
    
    Returns:
        bytes: Contenu du PDF généré
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1e40af'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    # Titre
    story.append(Paragraph("CONVOCATION RÉUNION CSE", title_style))
    story.append(Spacer(1, 0.5*cm))
    
    # Informations de la réunion
    story.append(Paragraph(f"<b>Titre:</b> {meeting_data.get('title', 'N/A')}", styles['Normal']))
    story.append(Spacer(1, 0.3*cm))
    
    meeting_date = meeting_data.get('meeting_date')
    if meeting_date:
        date_obj = datetime.fromisoformat(meeting_date) if isinstance(meeting_date, str) else meeting_date
        story.append(Paragraph(f"<b>Date:</b> {date_obj.strftime('%d/%m/%Y')}", styles['Normal']))
    
    meeting_time = meeting_data.get('meeting_time')
    if meeting_time:
        story.append(Paragraph(f"<b>Heure:</b> {meeting_time}", styles['Normal']))
    
    location = meeting_data.get('location')
    if location:
        story.append(Paragraph(f"<b>Lieu:</b> {location}", styles['Normal']))
    
    meeting_type = meeting_data.get('meeting_type', 'ordinaire')
    type_labels = {
        'ordinaire': 'Réunion ordinaire',
        'extraordinaire': 'Réunion extraordinaire',
        'cssct': 'CSSCT',
        'autre': 'Autre'
    }
    story.append(Paragraph(f"<b>Type:</b> {type_labels.get(meeting_type, meeting_type)}", styles['Normal']))
    
    story.append(Spacer(1, 0.5*cm))
    
    # Participants
    participants = meeting_data.get('participants', [])
    if participants:
        story.append(Paragraph("<b>Participants:</b>", styles['Heading3']))
        for participant in participants:
            name = f"{participant.get('first_name', '')} {participant.get('last_name', '')}".strip()
            if name:
                story.append(Paragraph(f"• {name}", styles['Normal']))
        story.append(Spacer(1, 0.5*cm))
    
    # Ordre du jour
    agenda = meeting_data.get('agenda')
    if agenda:
        story.append(Paragraph("<b>Ordre du jour:</b>", styles['Heading3']))
        # Si agenda est un dict avec des clés, les afficher
        if isinstance(agenda, dict):
            for key, value in agenda.items():
                story.append(Paragraph(f"<b>{key}:</b> {value}", styles['Normal']))
        else:
            story.append(Paragraph(str(agenda), styles['Normal']))
    
    doc.build(story)
    buffer.seek(0)
    return buffer.read()
def generate_minutes_pdf(
    meeting_data: Dict[str, Any],
    transcription: Optional[str] = None,
    summary: Optional[Dict[str, Any]] = None
) -> bytes:
    """
    Génère le PDF du procès-verbal depuis la transcription et la synthèse IA.
    
    Args:
        meeting_data: Données de la réunion
        transcription: Transcription brute (optionnel)
        summary: Résumé structuré IA (optionnel)
    
    Returns:
        bytes: Contenu du PDF généré
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1e40af'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    # Titre
    story.append(Paragraph("PROCÈS-VERBAL DE RÉUNION CSE", title_style))
    story.append(Spacer(1, 0.5*cm))
    
    # Informations de la réunion
    story.append(Paragraph(f"<b>Réunion:</b> {meeting_data.get('title', 'N/A')}", styles['Normal']))
    
    meeting_date = meeting_data.get('meeting_date')
    if meeting_date:
        date_obj = datetime.fromisoformat(meeting_date) if isinstance(meeting_date, str) else meeting_date
        story.append(Paragraph(f"<b>Date:</b> {date_obj.strftime('%d/%m/%Y')}", styles['Normal']))
    
    story.append(Spacer(1, 0.5*cm))
    
    # Résumé structuré (si disponible)
    if summary:
        story.append(Paragraph("<b>Résumé:</b>", styles['Heading2']))
        
        key_points = summary.get('key_points', [])
        if key_points:
            story.append(Paragraph("<b>Points clés:</b>", styles['Heading3']))
            for point in key_points:
                story.append(Paragraph(f"• {point}", styles['Normal']))
            story.append(Spacer(1, 0.3*cm))
        
        decisions = summary.get('decisions', [])
        if decisions:
            story.append(Paragraph("<b>Décisions prises:</b>", styles['Heading3']))
            for decision in decisions:
                story.append(Paragraph(f"• {decision}", styles['Normal']))
            story.append(Spacer(1, 0.3*cm))
        
        actions = summary.get('actions', [])
        if actions:
            story.append(Paragraph("<b>Actions à suivre:</b>", styles['Heading3']))
            for action in actions:
                story.append(Paragraph(f"• {action}", styles['Normal']))
            story.append(Spacer(1, 0.3*cm))
    
    # Transcription complète (si disponible)
    if transcription:
        story.append(PageBreak())
        story.append(Paragraph("<b>Transcription complète:</b>", styles['Heading2']))
        story.append(Spacer(1, 0.3*cm))
        # Découper la transcription en paragraphes pour un meilleur rendu
        paragraphs = transcription.split('\n\n')
        for para in paragraphs:
            if para.strip():
                story.append(Paragraph(para.strip(), styles['Normal']))
                story.append(Spacer(1, 0.2*cm))
    
    doc.build(story)
    buffer.seek(0)
    return buffer.read()
def generate_election_calendar_pdf(cycle_data: Dict[str, Any], timeline: List[Dict[str, Any]]) -> bytes:
    """
    Génère le PDF du calendrier des obligations sociales.
    
    Args:
        cycle_data: Données du cycle électoral
        timeline: Liste des étapes de la timeline
    
    Returns:
        bytes: Contenu du PDF généré
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1e40af'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    # Titre
    story.append(Paragraph("CALENDRIER DES OBLIGATIONS SOCIALES", title_style))
    story.append(Spacer(1, 0.5*cm))
    
    # Informations du cycle
    story.append(Paragraph(f"<b>Cycle:</b> {cycle_data.get('cycle_name', 'N/A')}", styles['Normal']))
    
    mandate_end = cycle_data.get('mandate_end_date')
    if mandate_end:
        date_obj = datetime.fromisoformat(mandate_end) if isinstance(mandate_end, str) else mandate_end
        story.append(Paragraph(f"<b>Fin de mandat:</b> {date_obj.strftime('%d/%m/%Y')}", styles['Normal']))
    
    election_date = cycle_data.get('election_date')
    if election_date:
        date_obj = datetime.fromisoformat(election_date) if isinstance(election_date, str) else election_date
        story.append(Paragraph(f"<b>Date des élections:</b> {date_obj.strftime('%d/%m/%Y')}", styles['Normal']))
    
    story.append(Spacer(1, 0.5*cm))
    
    # Timeline
    if timeline:
        story.append(Paragraph("<b>Étapes du calendrier électoral:</b>", styles['Heading2']))
        story.append(Spacer(1, 0.3*cm))
        
        # Tableau avec les étapes
        table_data = [["Étape", "Date butoir", "Statut"]]
        for step in sorted(timeline, key=lambda x: x.get('step_order', 0)):
            step_name = step.get('step_name', 'N/A')
            due_date = step.get('due_date', '')
            if due_date:
                date_obj = datetime.fromisoformat(due_date) if isinstance(due_date, str) else due_date
                due_date_str = date_obj.strftime('%d/%m/%Y')
            else:
                due_date_str = 'N/A'
            
            status = step.get('status', 'pending')
            status_labels = {
                'pending': 'En attente',
                'completed': 'Terminée',
                'overdue': 'En retard'
            }
            status_str = status_labels.get(status, status)
            
            table_data.append([step_name, due_date_str, status_str])
        
        table = Table(table_data, colWidths=[8*cm, 4*cm, 3*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(table)
    
    doc.build(story)
    buffer.seek(0)
    return buffer.read()
