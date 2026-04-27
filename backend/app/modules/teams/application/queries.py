"""Requêtes applicatives — module Équipes."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from app.modules.teams.infrastructure.repository import teams_repository
from app.modules.teams.schemas.responses import (
    TeamAnalyticsItem,
    TeamAnalyticsResponse,
    TeamDetailPayload,
    TeamListResponse,
    TeamMemberItem,
    TeamNameAvailabilityResponse,
    TeamResponse,
)


def _ts(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _as_str_id(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _parse_period_date(s: str) -> date:
    return datetime.fromisoformat(s[:10]).date()


def _count_workdays(start: date, end: date) -> int:
    n = 0
    d = start
    while d <= end:
        if d.weekday() < 5:
            n += 1
        d += timedelta(days=1)
    return n


def _team_row_to_response(row: Dict[str, Any], *, employee_count: int) -> Dict[str, Any]:
    nested = row.get("employees")
    mfn: Optional[str] = None
    mln: Optional[str] = None
    if isinstance(nested, dict):
        mfn = nested.get("first_name")
        mln = nested.get("last_name")
    return {
        "id": str(row["id"]),
        "company_id": str(row["company_id"]),
        "name": str(row.get("name") or ""),
        "description": row.get("description"),
        "color": str(row.get("color") or "#6366f1"),
        "manager_employee_id": _as_str_id(row.get("manager_employee_id")),
        "manager_first_name": mfn,
        "manager_last_name": mln,
        "status": str(row.get("status") or "active"),
        "employee_count": employee_count,
        "created_at": _ts(row.get("created_at")),
        "updated_at": _ts(row.get("updated_at")),
    }


def get_teams(company_id: str, include_archived: bool = False) -> dict:
    """
    Récupère les équipes avec employee_count pour chacune.
    Retourne TeamListResponse compatible dict.
    """
    rows = teams_repository.get_teams_by_company(company_id, include_archived)
    teams_out: List[Dict[str, Any]] = []
    for row in rows:
        tid = str(row["id"])
        cnt = teams_repository.get_employee_count(tid)
        teams_out.append(_team_row_to_response(row, employee_count=cnt))
    archived_count = teams_repository.count_teams_by_company_and_status(
        company_id, "archived"
    )
    return TeamListResponse(
        teams=[TeamResponse(**t) for t in teams_out],
        total=len(teams_out),
        archived_count=archived_count,
    ).model_dump()


def get_team_detail(team_id: str, company_id: str) -> dict:
    """
    Récupère l'équipe + liste des salariés membres.
    Vérifie company_id → PermissionError si mismatch.
    """
    row = teams_repository.get_team_by_id(team_id)
    if not row:
        raise LookupError("Équipe introuvable.")
    if str(row.get("company_id")) != str(company_id):
        raise PermissionError("Accès non autorisé à cette équipe.")
    cnt = teams_repository.get_employee_count(team_id)
    team_dict = _team_row_to_response(row, employee_count=cnt)
    members_raw = teams_repository.get_employees_by_team(team_id)
    members = [
        TeamMemberItem(
            id=str(m.get("id") or ""),
            first_name=m.get("first_name"),
            last_name=m.get("last_name"),
            job_title=m.get("job_title"),
        )
        for m in members_raw
        if isinstance(m, dict)
    ]
    return TeamDetailPayload(
        team=TeamResponse(**team_dict), members=members
    ).model_dump()


def get_team_analytics(
    company_id: str,
    period_start: str,
    period_end: str,
    team_ids: Optional[List[str]] = None,
) -> dict:
    """
    Calcule les indicateurs par équipe (+ « Sans équipe ») sur la période.
    """
    p_start = _parse_period_date(period_start)
    p_end = _parse_period_date(period_end)
    if p_end < p_start:
        raise ValueError("La fin de période doit être postérieure au début.")

    workdays = _count_workdays(p_start, p_end)
    if workdays <= 0:
        workdays = 1

    employees = teams_repository.get_employees_with_team(company_id)
    payslips = teams_repository.get_payslips_for_period(
        company_id, period_start, period_end
    )
    expenses = teams_repository.get_expenses_for_period(
        company_id, period_start, period_end
    )
    absences = teams_repository.get_absences_for_period(
        company_id, period_start, period_end
    )
    active_teams = teams_repository.get_teams_by_company(
        company_id, include_archived=False
    )

    emp_team: Dict[str, Optional[str]] = {}
    for e in employees:
        if not isinstance(e, dict):
            continue
        eid = str(e.get("id") or "")
        if not eid:
            continue
        tid = e.get("team_id")
        emp_team[eid] = str(tid) if tid else None

    brut_by_emp: Dict[str, float] = defaultdict(float)
    cout_by_emp: Dict[str, float] = defaultdict(float)
    for p in payslips:
        if not isinstance(p, dict):
            continue
        eid = str(p.get("employee_id") or "")
        if not eid:
            continue
        brut_by_emp[eid] += float(p.get("salaire_brut") or 0)
        cout_by_emp[eid] += float(p.get("cout_total_employeur") or 0)

    expenses_by_emp: Dict[str, float] = defaultdict(float)
    for x in expenses:
        if not isinstance(x, dict):
            continue
        eid = str(x.get("employee_id") or "")
        if not eid:
            continue
        expenses_by_emp[eid] += float(x.get("amount") or 0)

    absence_days_by_emp: Dict[str, float] = defaultdict(float)
    for a in absences:
        if not isinstance(a, dict):
            continue
        eid = str(a.get("employee_id") or "")
        if not eid:
            continue
        days = a.get("selected_days") or []
        if isinstance(days, list):
            absence_days_by_emp[eid] += float(len(days))

    def _rollup(team_key: Optional[str]) -> tuple[int, float, float, float, float]:
        emps = [eid for eid, tid in emp_team.items() if tid == team_key]
        ec = len(emps)
        mb = sum(brut_by_emp[e] for e in emps)
        mt = sum(cout_by_emp[e] for e in emps)
        ndf = sum(expenses_by_emp[e] for e in emps)
        ab = sum(absence_days_by_emp[e] for e in emps)
        return ec, mb, mt, ndf, ab

    items: List[TeamAnalyticsItem] = []
    for trow in active_teams:
        if not isinstance(trow, dict):
            continue
        tid = str(trow.get("id") or "")
        if not tid:
            continue
        ec, mb, mt, ndf, ab = _rollup(tid)
        taux = (
            (ab / float(ec * workdays)) * 100.0 if ec > 0 else 0.0
        )
        c_moy = (mt / float(ec)) if ec > 0 else 0.0
        items.append(
            TeamAnalyticsItem(
                team_id=tid,
                team_name=str(trow.get("name") or ""),
                team_color=str(trow.get("color") or "#6366f1"),
                employee_count=ec,
                masse_salariale_brute=mb,
                masse_salariale_totale=mt,
                notes_de_frais=ndf,
                absences_jours=ab,
                taux_absenteisme=round(taux, 4),
                cout_moyen_par_salarie=round(c_moy, 2),
            )
        )

    ec0, mb0, mt0, ndf0, ab0 = _rollup(None)
    taux0 = (ab0 / float(ec0 * workdays)) * 100.0 if ec0 > 0 else 0.0
    c_moy0 = (mt0 / float(ec0)) if ec0 > 0 else 0.0
    items.append(
        TeamAnalyticsItem(
            team_id=None,
            team_name="Sans équipe",
            team_color="#64748b",
            employee_count=ec0,
            masse_salariale_brute=mb0,
            masse_salariale_totale=mt0,
            notes_de_frais=ndf0,
            absences_jours=ab0,
            taux_absenteisme=round(taux0, 4),
            cout_moyen_par_salarie=round(c_moy0, 2),
        )
    )

    items.sort(key=lambda it: (it.team_id is None, it.team_name.lower()))

    if team_ids:
        sel = {str(x) for x in team_ids if x}
        items = [
            it
            for it in items
            if it.team_id is None or (it.team_id and str(it.team_id) in sel)
        ]

    total_masse_brute = float(sum(brut_by_emp.values()))
    total_notes = float(sum(expenses_by_emp.values()))

    return TeamAnalyticsResponse(
        period_start=period_start,
        period_end=period_end,
        items=items,
        total_employees=len(emp_team),
        total_masse_brute=total_masse_brute,
        total_notes_de_frais=total_notes,
    ).model_dump()


def check_team_name_available(
    company_id: str,
    name: str,
    exclude_team_id: Optional[str] = None,
) -> dict:
    """Validation temps réel du nom d'équipe (unicité insensible à la casse)."""
    exists = teams_repository.check_name_exists(
        company_id, name, exclude_team_id
    )
    return TeamNameAvailabilityResponse(
        available=not exists, name=name
    ).model_dump()
