"""Lecture applicative — module Planning."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from app.core.database import supabase

from app.modules.planning.infrastructure import queries as infra_queries
from app.modules.planning.infrastructure.repository import planning_repository


def _week_start_iso(week_start: str) -> str:
    return week_start[:10]


def _week_end_iso(week_start: str) -> str:
    d = date.fromisoformat(_week_start_iso(week_start))
    return (d + timedelta(days=6)).isoformat()


def _format_time_for_api(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _shift_type_to_dict(st: Any) -> Optional[Dict[str, Any]]:
    if not st or not isinstance(st, dict):
        return None
    return {
        "id": str(st.get("id") or ""),
        "code": str(st.get("code") or ""),
        "label": str(st.get("label") or ""),
        "color": str(st.get("color") or ""),
        "default_start": st.get("default_start"),
        "default_end": st.get("default_end"),
    }


def _shift_row_to_response_dict(
    row: Dict[str, Any], *, is_rh: bool, strip_internal: bool = False
) -> Dict[str, Any]:
    emp = row.get("employees") if isinstance(row.get("employees"), dict) else {}
    st = row.get("shift_types")
    sd = row.get("shift_date")
    if isinstance(sd, datetime):
        sd = sd.date()
    elif isinstance(sd, str):
        sd = date.fromisoformat(sd[:10])
    out: Dict[str, Any] = {
        "id": str(row.get("id") or ""),
        "company_id": str(row.get("company_id") or ""),
        "employee_id": str(row.get("employee_id") or ""),
        "employee_first_name": emp.get("first_name") if emp else None,
        "employee_last_name": emp.get("last_name") if emp else None,
        "shift_type": _shift_type_to_dict(st),
        "transverse_category": row.get("transverse_category"),
        "shift_date": sd,
        "start_time": _format_time_for_api(row.get("start_time")),
        "end_time": _format_time_for_api(row.get("end_time")),
        "post": row.get("post"),
        "location": row.get("location"),
        "comment_employee": row.get("comment_employee"),
        "is_locked": bool(row.get("is_locked")),
        "source": str(row.get("source") or "manual"),
        "created_at": str(row.get("created_at") or ""),
    }
    show_internal = is_rh and not strip_internal
    if show_internal:
        out["comment_internal"] = row.get("comment_internal")
    else:
        out["comment_internal"] = None
    return out


def get_week_planning(company_id: str, week_start: str, is_rh: bool) -> dict:
    """
    Calcule week_end = week_start + 6 jours.
    Appelle get_week_planning_full(company_id, week_start, week_end).
    Appelle get_employee_week_hours(company_id, week_start, week_end).
    Récupère le week_status via planning_repository.get_week_status().
    Si pas de week_status : status='draft', payroll_transmitted=False,
    team_view_enabled=False.
    Si is_rh=True : retourne ShiftResponseRH (avec comment_internal).
    Si is_rh=False : masque comment_internal de chaque shift.
    Retourne un dict compatible WeekPlanningResponse.
    """
    ws_iso = _week_start_iso(week_start)
    we_iso = _week_end_iso(week_start)
    shifts_raw = infra_queries.get_week_planning_full(company_id, ws_iso, we_iso)
    employee_hours = infra_queries.get_employee_week_hours(company_id, ws_iso, we_iso)
    wstatus = planning_repository.get_week_status(company_id, ws_iso)
    if not wstatus:
        status = "draft"
        payroll_transmitted = False
        team_view_enabled = False
    else:
        status = str(wstatus.get("status") or "draft")
        payroll_transmitted = bool(wstatus.get("payroll_transmitted"))
        team_view_enabled = bool(wstatus.get("team_view_enabled"))

    shifts = [
        _shift_row_to_response_dict(r, is_rh=is_rh, strip_internal=not is_rh)
        for r in shifts_raw
    ]
    return {
        "week_start": date.fromisoformat(ws_iso),
        "week_end": date.fromisoformat(we_iso),
        "status": status,
        "payroll_transmitted": payroll_transmitted,
        "team_view_enabled": team_view_enabled,
        "shifts": shifts,
        "employee_hours": employee_hours,
    }


def get_shift_detail(shift_id: str, company_id: str, is_rh: bool) -> dict:
    """
    Récupère le shift via planning_repository.get_shift_by_id().
    Vérifie que shift['company_id'] == company_id → sinon raise PermissionError.
    Si is_rh=False : masque comment_internal.
    """
    row = planning_repository.get_shift_by_id(shift_id)
    if not row:
        raise LookupError("Shift introuvable.")
    if str(row.get("company_id") or "") != str(company_id):
        raise PermissionError("Shift hors entreprise active.")
    return _shift_row_to_response_dict(row, is_rh=is_rh, strip_internal=not is_rh)


def get_lock_history(company_id: str) -> list:
    """Appelle planning_repository.get_lock_history(company_id, limit=50)."""
    return planning_repository.get_lock_history(company_id, limit=50)


def get_company_settings(company_id: str) -> dict:
    """
    Appelle planning_repository.get_company_planning_settings(company_id).
    Si None : retourne dict avec valeurs par défaut
    (collective_agreement_id=None, team_view_default=False).
    """
    row = planning_repository.get_company_planning_settings(company_id)
    if not row:
        return {
            "collective_agreement_id": None,
            "collective_agreement": None,
            "team_view_default": False,
        }
    cc_id = row.get("collective_agreement_id")
    cc = None
    if cc_id:
        cc_row = planning_repository.get_cc_by_id(str(cc_id))
        if cc_row:
            cc = {
                "id": str(cc_row.get("id") or ""),
                "code": str(cc_row.get("code") or ""),
                "label": str(cc_row.get("label") or ""),
                "idcc": cc_row.get("idcc"),
            }
    return {
        "collective_agreement_id": str(cc_id) if cc_id else None,
        "collective_agreement": cc,
        "team_view_default": bool(row.get("team_view_default")),
    }


def get_shift_types_for_company(company_id: str) -> list:
    """
    Récupère get_company_planning_settings(company_id).
    Si collective_agreement_id défini :
        appelle planning_repository.get_shift_types_by_cc(cc_id).
    Sinon :
        appelle planning_repository.get_all_active_shift_types().
    """
    settings = planning_repository.get_company_planning_settings(company_id)
    cc_id = settings.get("collective_agreement_id") if settings else None
    if cc_id:
        rows = planning_repository.get_shift_types_by_cc(str(cc_id))
    else:
        rows = planning_repository.get_all_active_shift_types()
    return [
        {
            "id": str(r.get("id") or ""),
            "code": str(r.get("code") or ""),
            "label": str(r.get("label") or ""),
            "color": str(r.get("color") or ""),
            "default_start": r.get("default_start"),
            "default_end": r.get("default_end"),
        }
        for r in rows
    ]


def get_employee_planning(
    employee_id: str, week_start: str, team_view_enabled: bool
) -> dict:
    """
    Vue salarié.
    Calcule week_end = week_start + 6 jours.
    Si team_view_enabled=False :
        appelle planning_repository.get_shifts_by_employee_week()
        → uniquement les shifts de cet employé.
    Si team_view_enabled=True :
        appelle get_week_planning_full() pour toute la semaine
        (le salarié voit ses collègues).
    Masque toujours comment_internal.
    Retourne uniquement les shifts dont status != 'draft'
    (un salarié ne voit que les semaines publiées ou verrouillées).
    """
    ws_iso = _week_start_iso(week_start)
    we_iso = _week_end_iso(week_start)

    r_emp = (
        supabase.table("employees")
        .select("company_id")
        .eq("id", employee_id)
        .maybe_single()
        .execute()
    )
    company_id = (r_emp.data or {}).get("company_id") if r_emp and r_emp.data else None
    if not company_id:
        raise LookupError("Employé introuvable.")

    wstatus = planning_repository.get_week_status(str(company_id), ws_iso)
    status = str(wstatus.get("status") or "draft") if wstatus else "draft"
    if status == "draft":
        return {
            "week_start": date.fromisoformat(ws_iso),
            "week_end": date.fromisoformat(we_iso),
            "status": status,
            "payroll_transmitted": bool(wstatus.get("payroll_transmitted"))
            if wstatus
            else False,
            "team_view_enabled": bool(wstatus.get("team_view_enabled"))
            if wstatus
            else False,
            "shifts": [],
            "employee_hours": [],
        }

    if team_view_enabled:
        shifts_raw = infra_queries.get_week_planning_full(
            str(company_id), ws_iso, we_iso
        )
    else:
        shifts_raw = planning_repository.get_shifts_by_employee_week(
            employee_id, ws_iso, we_iso
        )

    shifts = [
        _shift_row_to_response_dict(r, is_rh=False, strip_internal=True)
        for r in shifts_raw
    ]
    employee_hours = infra_queries.get_employee_week_hours(
        str(company_id), ws_iso, we_iso
    )
    emp_hours = [h for h in employee_hours if h.get("employee_id") == employee_id]

    return {
        "week_start": date.fromisoformat(ws_iso),
        "week_end": date.fromisoformat(we_iso),
        "status": status,
        "payroll_transmitted": bool(wstatus.get("payroll_transmitted"))
        if wstatus
        else False,
        "team_view_enabled": bool(wstatus.get("team_view_enabled"))
        if wstatus
        else team_view_enabled,
        "shifts": shifts,
        "employee_hours": emp_hours,
    }
