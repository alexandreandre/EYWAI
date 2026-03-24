# app/modules/cse/infrastructure/cse_export_impl.py
"""
Exports Excel CSE (base élus, heures délégation, historique réunions).
Implémentation autonome ex-services.cse_export_service.
"""
from __future__ import annotations

import io
from datetime import datetime
from typing import Any, Dict, List

from app.shared.utils.export import generate_xlsx


def export_elected_members(members: List[Dict[str, Any]]) -> bytes:
    """Export Excel de la base des élus CSE."""
    headers = [
        "Nom",
        "Prénom",
        "Poste",
        "Rôle CSE",
        "Collège",
        "Date début mandat",
        "Date fin mandat",
        "Jours restants",
        "Statut"
    ]
    data = []
    for member in members:
        days_remaining = member.get('days_remaining')
        if days_remaining is None:
            try:
                end_date = datetime.fromisoformat(member.get('end_date', ''))
                today = datetime.now()
                days_remaining = (end_date - today).days
            except Exception:
                days_remaining = None
        status = "Actif"
        if days_remaining is not None:
            if days_remaining < 0:
                status = "Expiré"
            elif days_remaining <= 90:
                status = "Expire bientôt"
        start_date = member.get('start_date', '')
        if start_date:
            try:
                start_date = datetime.fromisoformat(start_date).strftime('%d/%m/%Y')
            except Exception:
                pass
        end_date = member.get('end_date', '')
        if end_date:
            try:
                end_date = datetime.fromisoformat(end_date).strftime('%d/%m/%Y')
            except Exception:
                pass
        data.append({
            "Nom": member.get('last_name', ''),
            "Prénom": member.get('first_name', ''),
            "Poste": member.get('job_title', ''),
            "Rôle CSE": member.get('role', '').capitalize(),
            "Collège": member.get('college', ''),
            "Date début mandat": start_date,
            "Date fin mandat": end_date,
            "Jours restants": days_remaining if days_remaining is not None else '',
            "Statut": status
        })
    return generate_xlsx(data, headers, "Base élus CSE")


def export_delegation_hours(
    hours: List[Dict[str, Any]], summary: List[Dict[str, Any]]
) -> bytes:
    """Export Excel des heures de délégation."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = Workbook()
    ws_summary = wb.active
    ws_summary.title = "Récapitulatif"
    headers_summary = [
        "Élu",
        "Quota mensuel (h)",
        "Heures consommées (h)",
        "Heures restantes (h)",
        "Période"
    ]
    header_fill = PatternFill(
        start_color="366092", end_color="366092", fill_type="solid"
    )
    header_font = Font(bold=True, color="FFFFFF")
    for col_idx, header in enumerate(headers_summary, start=1):
        cell = ws_summary.cell(row=1, column=col_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
    for row_idx, item in enumerate(summary, start=2):
        ws_summary.cell(
            row=row_idx, column=1,
            value=f"{item.get('first_name', '')} {item.get('last_name', '')}"
        )
        ws_summary.cell(row=row_idx, column=2, value=item.get('quota_hours_per_month', 0))
        ws_summary.cell(row=row_idx, column=3, value=item.get('consumed_hours', 0))
        ws_summary.cell(row=row_idx, column=4, value=item.get('remaining_hours', 0))
        period_start = item.get('period_start', '')
        period_end = item.get('period_end', '')
        if period_start and period_end:
            try:
                start = datetime.fromisoformat(period_start).strftime('%d/%m/%Y')
                end = datetime.fromisoformat(period_end).strftime('%d/%m/%Y')
                ws_summary.cell(row=row_idx, column=5, value=f"{start} - {end}")
            except Exception:
                ws_summary.cell(row=row_idx, column=5, value=f"{period_start} - {period_end}")
    for col_idx in range(1, len(headers_summary) + 1):
        h = headers_summary[col_idx - 1]
        max_length = max(
            len(str(h)),
            max(
                (len(str(ws_summary.cell(row=row_idx, column=col_idx).value or '')))
                for row_idx in range(2, ws_summary.max_row + 1)
            ),
            default=0,
        )
        ws_summary.column_dimensions[
            ws_summary.cell(row=1, column=col_idx).column_letter
        ].width = min(max_length + 2, 50)
    ws_detail = wb.create_sheet("Détail heures")
    headers_detail = ["Date", "Élu", "Durée (h)", "Motif", "Réunion associée"]
    for col_idx, header in enumerate(headers_detail, start=1):
        cell = ws_detail.cell(row=1, column=col_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
    for row_idx, hour in enumerate(hours, start=2):
        date_str = hour.get('date', '')
        if date_str:
            try:
                date_str = datetime.fromisoformat(date_str).strftime('%d/%m/%Y')
            except Exception:
                pass
        ws_detail.cell(row=row_idx, column=1, value=date_str)
        ws_detail.cell(
            row=row_idx, column=2,
            value=f"{hour.get('first_name', '')} {hour.get('last_name', '')}"
        )
        ws_detail.cell(row=row_idx, column=3, value=hour.get('duration_hours', 0))
        ws_detail.cell(row=row_idx, column=4, value=hour.get('reason', ''))
        ws_detail.cell(row=row_idx, column=5, value=hour.get('meeting_title', ''))
    for col_idx in range(1, len(headers_detail) + 1):
        h = headers_detail[col_idx - 1]
        max_length = max(
            len(str(h)),
            max(
                (len(str(ws_detail.cell(row=row_idx, column=col_idx).value or '')))
                for row_idx in range(2, ws_detail.max_row + 1)
            ),
            default=0,
        )
        ws_detail.column_dimensions[
            ws_detail.cell(row=1, column=col_idx).column_letter
        ].width = min(max_length + 2, 50)
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.read()


def export_meetings_history(meetings: List[Dict[str, Any]]) -> bytes:
    """Export Excel de l'historique des réunions CSE."""
    headers = [
        "Titre",
        "Date",
        "Heure",
        "Type",
        "Statut",
        "Lieu",
        "Nombre participants",
        "PV généré"
    ]
    data = []
    for meeting in meetings:
        meeting_date = meeting.get('meeting_date', '')
        if meeting_date:
            try:
                meeting_date = datetime.fromisoformat(meeting_date).strftime('%d/%m/%Y')
            except Exception:
                pass
        meeting_time = meeting.get('meeting_time', '')
        if meeting_time:
            try:
                meeting_time = meeting_time[:5]
            except Exception:
                pass
        status_labels = {
            'a_venir': 'À venir',
            'en_cours': 'En cours',
            'terminee': 'Terminée'
        }
        status = status_labels.get(meeting.get('status', ''), meeting.get('status', ''))
        type_labels = {
            'ordinaire': 'Ordinaire',
            'extraordinaire': 'Extraordinaire',
            'cssct': 'CSSCT',
            'autre': 'Autre'
        }
        meeting_type = type_labels.get(
            meeting.get('meeting_type', ''), meeting.get('meeting_type', '')
        )
        has_minutes = "Oui" if meeting.get('has_minutes') else "Non"
        data.append({
            "Titre": meeting.get('title', ''),
            "Date": meeting_date,
            "Heure": meeting_time,
            "Type": meeting_type,
            "Statut": status,
            "Lieu": meeting.get('location', ''),
            "Nombre participants": meeting.get('participant_count', 0),
            "PV généré": has_minutes
        })
    return generate_xlsx(data, headers, "Historique réunions CSE")
