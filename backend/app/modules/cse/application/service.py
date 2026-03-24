# app/modules/cse/application/service.py
"""
Service applicatif CSE — orchestration des cas d'usage.
Regroupe commands, queries et logique d'export (ex-router).
"""
import calendar
from datetime import date, datetime
from typing import List, Optional, Union

from fastapi import HTTPException

from app.modules.cse.application import commands, queries
from app.modules.cse.application.dto import ExportFile
from app.modules.cse.infrastructure.providers import (
    cse_export_provider,
    cse_pdf_provider,
)


def _to_dict(obj) -> dict:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return obj.dict() if hasattr(obj, "dict") else obj


# ---------------------------------------------------------------------------
# Exports fichiers — logique ex-router déplacée ici
# ---------------------------------------------------------------------------

def export_elected_members_file(company_id: str) -> ExportFile:
    """Export Excel base des élus CSE. Comportement identique à l'endpoint /exports/elected-members."""
    queries.check_module_active(company_id)
    members = queries.get_elected_members(company_id, active_only=False)
    members_dict = [_to_dict(m) for m in members]
    content = cse_export_provider.export_elected_members(members_dict)
    return ExportFile(
        content=content,
        filename="base_elus_cse.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def _parse_date(
    value: Optional[Union[date, datetime, str]], default: date
) -> date:
    """Normalise une date (str ISO ou date/datetime) vers date ; utilise default si value est None."""
    if value is None:
        return default
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value).date()
    return default


def export_delegation_hours_file(
    company_id: str,
    period_start: Optional[Union[date, str]] = None,
    period_end: Optional[Union[date, str]] = None,
) -> ExportFile:
    """Export Excel des heures de délégation. Période par défaut = mois en cours."""
    queries.check_module_active(company_id)
    now = date.today()
    default_start = date(now.year, now.month, 1)
    _, last_day = calendar.monthrange(now.year, now.month)
    default_end = date(now.year, now.month, last_day)

    period_start = _parse_date(period_start, default_start)
    period_end = _parse_date(period_end, default_end)

    members = queries.get_elected_members(company_id, active_only=True)
    all_hours: List = []
    for member in members:
        hours = queries.get_delegation_hours(
            company_id, member.employee_id, period_start, period_end
        )
        all_hours.extend(hours)
    summary = queries.get_delegation_summary(company_id, period_start, period_end)

    hours_dict = [_to_dict(h) for h in all_hours]
    summary_dict = [_to_dict(s) for s in summary]
    content = cse_export_provider.export_delegation_hours(hours_dict, summary_dict)
    return ExportFile(
        content=content,
        filename="heures_delegation_cse.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def export_meetings_history_file(company_id: str) -> ExportFile:
    """Export Excel historique des réunions CSE."""
    queries.check_module_active(company_id)
    meetings = queries.get_meetings(company_id)
    meetings_dict = [_to_dict(m) for m in meetings]
    content = cse_export_provider.export_meetings_history(meetings_dict)
    return ExportFile(
        content=content,
        filename="historique_reunions_cse.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def export_minutes_annual_file(company_id: str, year: int) -> ExportFile:
    """Export PDF des PV annuels (première réunion de l'année avec PV). Comportement identique à l'endpoint."""
    queries.check_module_active(company_id)
    meetings = queries.get_meetings(company_id, status="terminee")
    meetings_with_pv: List[dict] = []
    for m in meetings:
        meeting_date = (
            datetime.fromisoformat(m.meeting_date).date()
            if isinstance(m.meeting_date, str)
            else m.meeting_date
        )
        if meeting_date.year != year:
            continue
        minutes_path = queries.get_meeting_minutes_path(m.id, company_id)
        if not minutes_path:
            continue
        try:
            meeting_detail = queries.get_meeting_by_id(m.id, company_id)
            meeting_dict = _to_dict(meeting_detail)
            meeting_dict["minutes_pdf_path"] = minutes_path
            meetings_with_pv.append(meeting_dict)
        except Exception:
            continue

    if not meetings_with_pv:
        raise HTTPException(status_code=404, detail="Aucun PV trouvé pour cette année")

    pdf_bytes = cse_pdf_provider.generate_minutes(meetings_with_pv[0])
    return ExportFile(
        content=pdf_bytes,
        filename=f"pv_annuels_{year}.pdf",
        media_type="application/pdf",
    )


def export_election_calendar_file(
    company_id: str,
    cycle_id: Optional[str] = None,
) -> ExportFile:
    """Export PDF calendrier des obligations sociales. Si cycle_id absent, utilise le plus récent."""
    queries.check_module_active(company_id)
    if cycle_id:
        cycle = queries.get_election_cycle_by_id(cycle_id, company_id)
    else:
        cycles = queries.get_election_cycles(company_id)
        if not cycles:
            raise HTTPException(status_code=404, detail="Aucun cycle électoral trouvé")
        cycle = cycles[0]
    cycle_dict = _to_dict(cycle)
    timeline = cycle_dict.get("timeline", [])
    content = cse_pdf_provider.generate_election_calendar(cycle_dict, timeline)
    return ExportFile(
        content=content,
        filename=f"calendrier_electoral_{cycle.cycle_name}.pdf",
        media_type="application/pdf",
    )


def get_meeting_minutes_path_or_raise(meeting_id: str, company_id: str) -> str:
    """Chemin du PV d'une réunion ; lève HTTPException 404 si absent."""
    path = queries.get_meeting_minutes_path(meeting_id, company_id)
    if not path:
        raise HTTPException(status_code=404, detail="PV non disponible")
    return path


# Réexport commands / queries pour usage unifié
__all__ = [
    "commands",
    "queries",
    "export_elected_members_file",
    "export_delegation_hours_file",
    "export_meetings_history_file",
    "export_minutes_annual_file",
    "export_election_calendar_file",
    "get_meeting_minutes_path_or_raise",
]
