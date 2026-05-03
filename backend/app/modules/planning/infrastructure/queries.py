"""
Requêtes Planning complexes (jointures, agrégations Python, contrôles transverses).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional

from app.core.database import supabase

# Jointures shifts : plusieurs FK vers employees → hints PostgREST explicites
SHIFT_ROW_SELECT = (
    "*, "
    "employees!employee_id(id, first_name, last_name, duree_hebdomadaire), "
    "replacing_employee:employees!replacing_employee_id(id, first_name, last_name), "
    "original_employee:employees!original_employee_id(id, first_name, last_name), "
    "shift_types(id, code, label, color, default_start, default_end)"
)


def _parse_shift_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return date.fromisoformat(value[:10])
    return None


def _parse_time_value(value: Any) -> Optional[time]:
    if value is None:
        return None
    if isinstance(value, time):
        return value
    if isinstance(value, str):
        parts = value.split(":")
        h, m = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
        s = int(parts[2]) if len(parts) > 2 else 0
        return time(h, m, s)
    return None


def _shift_duration_minutes(start: time, end: time) -> int:
    """Durée en minutes ; si end <= start, compte une sortie après minuit."""
    d0 = date.min
    t_start = datetime.combine(d0, start)
    t_end = datetime.combine(d0, end)
    if t_end <= t_start:
        t_end += timedelta(days=1)
    return int((t_end - t_start).total_seconds() // 60)


def get_week_planning_full(
    company_id: str, week_start: str, week_end: str
) -> List[Dict[str, Any]]:
    """
    Retourne tous les shifts de la semaine avec jointures complètes :
    employees(id, first_name, last_name, duree_hebdomadaire),
    shift_types(id, code, label, color, default_start, default_end)
    Trié par employee last_name ASC, shift_date ASC, start_time ASC
    """
    r = (
        supabase.table("shifts")
        .select(SHIFT_ROW_SELECT)
        .eq("company_id", company_id)
        .gte("shift_date", week_start)
        .lte("shift_date", week_end)
        .execute()
    )
    rows: List[Dict[str, Any]] = (r.data or []) if r else []

    def sort_key(row: Dict[str, Any]) -> tuple:
        emp = row.get("employees") or {}
        ln = (emp.get("last_name") or "").lower()
        sd = str(row.get("shift_date") or "")
        st = str(row.get("start_time") or "")
        return (ln, sd, st)

    rows.sort(key=sort_key)
    return rows


def get_employee_week_hours(
    company_id: str, week_start: str, week_end: str
) -> List[Dict[str, Any]]:
    """
    Retourne par employé : employee_id, total_minutes, contract_minutes, delta.
    total_minutes : somme (end - start) des shifts hors transverse (Python).
    contract_minutes : arrondi(duree_hebdomadaire * 60) depuis la table employees
    (défaut 35 h si NULL).
    """
    r = (
        supabase.table("shifts")
        .select("employee_id, start_time, end_time, transverse_category")
        .eq("company_id", company_id)
        .gte("shift_date", week_start)
        .lte("shift_date", week_end)
        .execute()
    )
    rows: List[Dict[str, Any]] = (r.data or []) if r else []
    totals: Dict[str, int] = {}
    for row in rows:
        if row.get("transverse_category") is not None:
            continue
        eid = row.get("employee_id")
        if not eid:
            continue
        st = _parse_time_value(row.get("start_time"))
        et = _parse_time_value(row.get("end_time"))
        if st is None or et is None:
            continue
        eid_str = str(eid)
        totals[eid_str] = totals.get(eid_str, 0) + _shift_duration_minutes(st, et)

    base_rows = [{"employee_id": k, "total_minutes": v} for k, v in sorted(totals.items())]
    if not base_rows:
        return []

    ids = [r["employee_id"] for r in base_rows]
    emp_r = (
        supabase.table("employees")
        .select("id, duree_hebdomadaire")
        .in_("id", ids)
        .execute()
    )
    emp_map: Dict[str, Any] = {}
    for e in emp_r.data or []:
        if e.get("id") is not None:
            emp_map[str(e["id"])] = e

    out: List[Dict[str, Any]] = []
    for row in base_rows:
        eid = str(row["employee_id"])
        emp = emp_map.get(eid) or {}
        dh = emp.get("duree_hebdomadaire")
        hours_week = float(dh) if dh is not None else 35.0
        contract_minutes = int(round(hours_week * 60))
        total = int(row["total_minutes"])
        out.append(
            {
                "employee_id": eid,
                "total_minutes": total,
                "contract_minutes": contract_minutes,
                "delta": total - contract_minutes,
            }
        )
    return out


def get_week_shifts_for_payroll(
    company_id: str, week_start: str
) -> List[Dict[str, Any]]:
    """
    Retourne les shifts verrouillés d'une semaine pour transmission paie :
    is_locked=True, shift_date entre week_start et week_start+6 jours.
    Jointure : employees(id, first_name, last_name, duree_hebdomadaire),
    shift_types(id, code, label)
    """
    ws = _parse_shift_date(week_start)
    if ws is None:
        return []
    week_end = ws + timedelta(days=6)
    week_end_s = week_end.isoformat()
    r = (
        supabase.table("shifts")
        .select(
            "*, "
            "employees!employee_id(id, first_name, last_name, duree_hebdomadaire), "
            "replacing_employee:employees!replacing_employee_id(id, first_name, last_name), "
            "original_employee:employees!original_employee_id(id, first_name, last_name), "
            "shift_types(id, code, label)"
        )
        .eq("company_id", company_id)
        .eq("is_locked", True)
        .gte("shift_date", week_start[:10])
        .lte("shift_date", week_end_s)
        .execute()
    )
    return (r.data or []) if r else []


def get_employee_shifts_for_conflict_check(
    employee_id: str, shift_date: str, exclude_shift_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Retourne tous les shifts d'un salarié pour un jour donné.
    Utilisé par le moteur de conflits (Bloc 4).
    Si exclude_shift_id fourni, exclure ce shift (cas de modification).
    """
    q = (
        supabase.table("shifts")
        .select("*")
        .eq("employee_id", employee_id)
        .eq("shift_date", shift_date[:10])
    )
    if exclude_shift_id:
        q = q.neq("id", exclude_shift_id)
    r = q.execute()
    return (r.data or []) if r else []


def check_absence_on_date(employee_id: str, shift_date: str) -> Optional[Dict[str, Any]]:
    """
    Vérifie si le salarié a une absence validée sur cette date.
    selected_days est une liste JSON de dates (ex: ["2026-04-22", "2026-04-23"]).
    On filtre status='validated' puis on vérifie côté Python si shift_date
    est dans selected_days.
    """
    r = (
        supabase.table("absence_requests")
        .select("id, employee_id, type, selected_days, status")
        .eq("employee_id", employee_id)
        .eq("status", "validated")
        .execute()
    )

    rows = (r.data or []) if r else []
    shift_date_str = str(shift_date)

    for row in rows:
        selected_days = row.get("selected_days") or []
        days_as_str = [str(d) for d in selected_days]
        if shift_date_str in days_as_str:
            return row

    return None


def get_payroll_period_locked(company_id: str, month: int, year: int) -> bool:
    """
    Vérifie si la paie du mois est clôturée (RG-11).
    Retourne False si la table payroll_runs n'existe pas encore.
    """
    try:
        r = (
            supabase.table("payroll_runs")
            .select("id, period_start, status")
            .eq("company_id", company_id)
            .eq("status", "closed")
            .execute()
        )
        rows = (r.data or []) if r else []
        for row in rows:
            period_start = row.get("period_start", "")
            try:
                d = date.fromisoformat(str(period_start)[:10])
                if d.month == month and d.year == year:
                    return True
            except Exception:
                continue
        return False
    except Exception:
        # Table inexistante ou erreur Supabase → paie non clôturée par défaut
        return False


def _sort_shift_rows(rows: List[Dict[str, Any]]) -> None:
    def sort_key(row: Dict[str, Any]) -> tuple:
        emp = row.get("employees") or {}
        ln = (emp.get("last_name") or "").lower()
        sd = str(row.get("shift_date") or "")
        st = str(row.get("start_time") or "")
        return (ln, sd, st)

    rows.sort(key=sort_key)


def get_shifts_company_date_range_joined(
    company_id: str, date_start: str, date_end: str
) -> List[Dict[str, Any]]:
    """Tous les shifts entre deux dates (inclus) avec jointures employé / type."""
    r = (
        supabase.table("shifts")
        .select(SHIFT_ROW_SELECT)
        .eq("company_id", company_id)
        .gte("shift_date", date_start)
        .lte("shift_date", date_end)
        .execute()
    )
    rows: List[Dict[str, Any]] = (r.data or []) if r else []
    _sort_shift_rows(rows)
    return rows


def get_shifts_employee_date_range_joined(
    employee_id: str, company_id: str, date_start: str, date_end: str
) -> List[Dict[str, Any]]:
    """Shifts d'un salarié sur une période (jointures pour affichage type / nom)."""
    r = (
        supabase.table("shifts")
        .select(SHIFT_ROW_SELECT)
        .eq("company_id", company_id)
        .eq("employee_id", employee_id)
        .gte("shift_date", date_start)
        .lte("shift_date", date_end)
        .execute()
    )
    rows: List[Dict[str, Any]] = (r.data or []) if r else []
    _sort_shift_rows(rows)
    return rows


def get_shifts_company_on_call_date_range(
    company_id: str, date_start: str, date_end: str
) -> List[Dict[str, Any]]:
    """Astreintes : transverse_category astreinte ou on_call (historique)."""
    r = (
        supabase.table("shifts")
        .select(SHIFT_ROW_SELECT)
        .eq("company_id", company_id)
        .gte("shift_date", date_start)
        .lte("shift_date", date_end)
        .in_("transverse_category", ["astreinte", "on_call"])
        .execute()
    )
    rows: List[Dict[str, Any]] = (r.data or []) if r else []
    _sort_shift_rows(rows)
    return rows


def get_shifts_company_replacements_date_range(
    company_id: str, date_start: str, date_end: str
) -> List[Dict[str, Any]]:
    """Shifts marqués remplacement sur la période (inclus)."""
    r = (
        supabase.table("shifts")
        .select(SHIFT_ROW_SELECT)
        .eq("company_id", company_id)
        .gte("shift_date", date_start)
        .lte("shift_date", date_end)
        .eq("is_replacement", True)
        .execute()
    )
    rows: List[Dict[str, Any]] = (r.data or []) if r else []
    _sort_shift_rows(rows)
    return rows


def get_shift_by_id_joined(shift_id: str) -> Optional[Dict[str, Any]]:
    """Une ligne shift avec jointures affichage (PostgREST)."""
    r = (
        supabase.table("shifts")
        .select(SHIFT_ROW_SELECT)
        .eq("id", shift_id)
        .maybe_single()
        .execute()
    )
    return r.data if r else None
