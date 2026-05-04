# app/modules/medical_follow_up/api/router.py
"""
Router du module Suivi médical.

Préfixe attendu à l’inclusion : /api/medical-follow-up.
Appelle uniquement la couche application (queries, commands, service).
Aucune logique métier ni accès DB. Comportement HTTP identique au legacy.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Set

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.core.security import get_current_user
from app.modules.medical_follow_up.application import commands, queries, reminders
from app.modules.medical_follow_up.application.dto import ObligationListDTO
from app.modules.medical_follow_up.application.service import (
    ensure_module_enabled,
    ensure_rh_access,
    resolve_company_id_for_medical,
)
from app.modules.medical_follow_up.schemas import (
    CreateOnDemandBody,
    KPIsResponse,
    MarkCompletedBody,
    MarkPlanifiedBody,
    ObligationListItem,
    SettingsResponse,
)
from app.modules.users.schemas.responses import User

router = APIRouter(tags=["Medical Follow-up"])

_ACTIVE_STATUSES = frozenset({"a_faire", "planifiee"})


def _parse_iso_date(value: object) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    return None


def _is_compliant_obligation(d: ObligationListDTO) -> bool:
    """Obligation considérée comme réalisée conforme (statuts terminaux + réalisée à temps)."""
    st = (d.status or "").strip().lower()
    if st in {"completed", "done", "realise", "completed_on_time"}:
        return True
    if st == "realisee":
        due = _parse_iso_date(d.due_date)
        comp = _parse_iso_date(d.completed_date)
        if due is not None and comp is not None:
            return comp <= due
        return True
    return False


def _is_overdue_active(d: ObligationListDTO, today: date) -> bool:
    st = (d.status or "").strip().lower()
    if st not in _ACTIVE_STATUSES:
        return False
    due = _parse_iso_date(d.due_date)
    if due is None:
        return False
    return due < today


def _is_upcoming_window(
    d: ObligationListDTO, today: date, end: date
) -> bool:
    st = (d.status or "").strip().lower()
    if st not in _ACTIVE_STATUSES:
        return False
    due = _parse_iso_date(d.due_date)
    if due is None:
        return False
    return today <= due <= end


def _visit_label(visit_type: str) -> str:
    return reminders.VISIT_TYPE_LABELS.get(
        visit_type, visit_type.replace("_", " ")
    )


class VisitTypeComplianceItem(BaseModel):
    visit_type: str
    label: str
    total: int
    compliant: int
    overdue: int
    compliance_rate: float


class EmployeeOverdueItem(BaseModel):
    employee_id: str
    employee_name: str
    obligations_overdue: int
    most_urgent_due_date: date
    visit_types: List[str]


class ComplianceReportResponse(BaseModel):
    generated_at: datetime
    total_employees: int
    total_obligations: int
    compliant: int
    overdue: int
    upcoming_30: int
    upcoming_7: int
    compliance_rate: float
    by_visit_type: List[VisitTypeComplianceItem]
    employees_overdue: List[EmployeeOverdueItem]


def _build_compliance_report(
    company_id: str, current_user: User
) -> ComplianceReportResponse:
    today = date.today()
    end_30 = today + timedelta(days=30)
    end_7 = today + timedelta(days=7)

    dtos = queries.list_obligations(
        company_id,
        current_user,
        employee_id=None,
        visit_type=None,
        status=None,
        priority=None,
        due_from=None,
        due_to=None,
    )

    total_obligations = len(dtos)
    distinct_employees: Set[str] = set()
    compliant = 0
    overdue = 0
    upcoming_30 = 0
    upcoming_7 = 0

    for d in dtos:
        distinct_employees.add(d.employee_id)
        if _is_compliant_obligation(d):
            compliant += 1
        if _is_overdue_active(d, today):
            overdue += 1
        if _is_upcoming_window(d, today, end_30):
            upcoming_30 += 1
        if _is_upcoming_window(d, today, end_7):
            upcoming_7 += 1

    compliance_rate = (
        round((compliant / total_obligations) * 100.0, 2)
        if total_obligations
        else 0.0
    )

    by_vt: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {"total": 0, "compliant": 0, "overdue": 0}
    )
    for d in dtos:
        vt = d.visit_type or "inconnu"
        by_vt[vt]["total"] += 1
        if _is_compliant_obligation(d):
            by_vt[vt]["compliant"] += 1
        if _is_overdue_active(d, today):
            by_vt[vt]["overdue"] += 1

    by_visit_type_list: List[VisitTypeComplianceItem] = []
    for vt, agg in by_vt.items():
        tot = agg["total"]
        comp = agg["compliant"]
        ovd = agg["overdue"]
        rate = round((comp / tot) * 100.0, 2) if tot else 0.0
        by_visit_type_list.append(
            VisitTypeComplianceItem(
                visit_type=vt,
                label=_visit_label(vt),
                total=tot,
                compliant=comp,
                overdue=ovd,
                compliance_rate=rate,
            )
        )
    by_visit_type_list.sort(key=lambda x: x.compliance_rate)

    overdue_by_emp: Dict[str, List[ObligationListDTO]] = defaultdict(list)
    for d in dtos:
        if _is_overdue_active(d, today):
            overdue_by_emp[d.employee_id].append(d)

    employees_overdue: List[EmployeeOverdueItem] = []
    for eid, rows in overdue_by_emp.items():
        due_dates = [_parse_iso_date(x.due_date) for x in rows]
        due_dates_valid = [x for x in due_dates if x is not None]
        most_urgent = min(due_dates_valid) if due_dates_valid else today
        names = [
            f"{(x.employee_first_name or '').strip()} {(x.employee_last_name or '').strip()}".strip()
            for x in rows
        ]
        employee_name = next((n for n in names if n), eid)
        vtypes = sorted({x.visit_type or "inconnu" for x in rows})
        employees_overdue.append(
            EmployeeOverdueItem(
                employee_id=eid,
                employee_name=employee_name,
                obligations_overdue=len(rows),
                most_urgent_due_date=most_urgent,
                visit_types=vtypes,
            )
        )
    employees_overdue.sort(key=lambda x: x.most_urgent_due_date)

    return ComplianceReportResponse(
        generated_at=datetime.now(timezone.utc),
        total_employees=len(distinct_employees),
        total_obligations=total_obligations,
        compliant=compliant,
        overdue=overdue,
        upcoming_30=upcoming_30,
        upcoming_7=upcoming_7,
        compliance_rate=compliance_rate,
        by_visit_type=by_visit_type_list,
        employees_overdue=employees_overdue,
    )


def _company_id_rh(current_user: User = Depends(get_current_user)) -> str:
    """Dépendance : module activé + accès RH ; retourne company_id."""
    company_id = ensure_module_enabled(current_user)
    ensure_rh_access(current_user, company_id)
    return company_id


def _to_list_item(d: ObligationListDTO) -> ObligationListItem:
    """Conversion DTO → schéma de réponse (sans logique métier)."""
    return ObligationListItem(
        id=d.id,
        company_id=d.company_id,
        employee_id=d.employee_id,
        visit_type=d.visit_type,
        trigger_type=d.trigger_type,
        due_date=d.due_date,
        priority=d.priority,
        status=d.status,
        justification=d.justification,
        planned_date=d.planned_date,
        completed_date=d.completed_date,
        rule_source=d.rule_source,
        collective_agreement_idcc=d.collective_agreement_idcc,
        request_motif=d.request_motif,
        request_date=d.request_date,
        employee_first_name=d.employee_first_name,
        employee_last_name=d.employee_last_name,
    )


# --- GET /obligations (liste avec filtres, RH)
@router.get("/obligations", response_model=List[ObligationListItem])
def list_obligations(
    employee_id: Optional[str] = Query(None),
    visit_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    priority: Optional[int] = Query(None),
    due_from: Optional[str] = Query(None),
    due_to: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(_company_id_rh),
):
    """Liste des obligations avec filtres. Réservé RH."""
    return [
        _to_list_item(d)
        for d in queries.list_obligations(
            company_id,
            current_user,
            employee_id=employee_id,
            visit_type=visit_type,
            status=status,
            priority=priority,
            due_from=due_from,
            due_to=due_to,
        )
    ]


# --- GET /obligations/overdue (RH)
@router.get("/obligations/overdue", response_model=List[ObligationListItem])
def list_obligations_overdue(
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(_company_id_rh),
):
    """Obligations en retard (échéance passée, non réalisées)."""
    rows = reminders.list_overdue_obligation_rows(company_id)
    return [_to_list_item(ObligationListDTO.from_row(r)) for r in rows]


# --- GET /obligations/upcoming (RH)
@router.get("/obligations/upcoming", response_model=List[ObligationListItem])
def list_obligations_upcoming(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(_company_id_rh),
):
    """Obligations à échéance dans les ``days`` prochains jours (non réalisées)."""
    rows = reminders.list_upcoming_obligation_rows(company_id, days)
    return [_to_list_item(ObligationListDTO.from_row(r)) for r in rows]


# --- POST /send-reminders (RH)
@router.post("/send-reminders")
def send_medical_reminders_endpoint(
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(_company_id_rh),
):
    """Envoie des notifications in-app de rappel aux salariés concernés."""
    result = reminders.send_medical_reminders(company_id)
    sent = int(result.get("sent", 0))
    message = f"{sent} rappel(s) envoyé(s)" if sent else "Aucun rappel envoyé"
    return {**result, "message": message}


# --- GET /compliance-report (RH)
@router.get("/compliance-report", response_model=ComplianceReportResponse)
def get_compliance_report(
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(_company_id_rh),
):
    """Rapport de conformité structuré (obligations actives et réalisées)."""
    return _build_compliance_report(company_id, current_user)


# --- GET /kpis (RH)
@router.get("/kpis", response_model=KPIsResponse)
def get_kpis(
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(_company_id_rh),
):
    """KPIs : en retard, à échéance < 30 j, total actives, réalisées ce mois."""
    kpis = queries.get_kpis(company_id, current_user)
    return KPIsResponse(
        overdue_count=kpis.overdue_count,
        due_within_30_count=kpis.due_within_30_count,
        active_total=kpis.active_total,
        completed_this_month=kpis.completed_this_month,
    )


# --- PATCH /obligations/{obligation_id}/planified
@router.patch("/obligations/{obligation_id}/planified")
def mark_planified(
    obligation_id: str,
    body: MarkPlanifiedBody,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(_company_id_rh),
):
    """Marquer une obligation comme planifiée."""
    return commands.mark_planified(obligation_id, body, company_id, current_user)


# --- PATCH /obligations/{obligation_id}/completed
@router.patch("/obligations/{obligation_id}/completed")
def mark_completed(
    obligation_id: str,
    body: MarkCompletedBody,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(_company_id_rh),
):
    """Marquer une obligation comme réalisée."""
    return commands.mark_completed(obligation_id, body, company_id, current_user)


# --- POST /obligations/on-demand
@router.post("/obligations/on-demand")
def create_on_demand(
    body: CreateOnDemandBody,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(_company_id_rh),
):
    """Créer une obligation « visite à la demande »."""
    return commands.create_on_demand(body, company_id, current_user)


# --- GET /obligations/employee/{employee_id} (RH)
@router.get(
    "/obligations/employee/{employee_id}", response_model=List[ObligationListItem]
)
def list_obligations_for_employee(
    employee_id: str,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(_company_id_rh),
):
    """Obligations d'un collaborateur (fiche collaborateur). Réservé RH."""
    return [
        _to_list_item(d)
        for d in queries.list_obligations_for_employee(
            company_id,
            employee_id,
            current_user,
        )
    ]


# --- GET /me (obligations du collaborateur connecté)
@router.get("/me", response_model=List[ObligationListItem])
def my_obligations(current_user: User = Depends(get_current_user)):
    """Obligations du collaborateur connecté (espace « Mon suivi médical »)."""
    return [
        _to_list_item(d) for d in queries.get_my_obligations_with_guards(current_user)
    ]


# --- GET /settings
@router.get("/settings", response_model=SettingsResponse)
def get_medical_settings(current_user: User = Depends(get_current_user)):
    """Indique si le module est activé pour l'entreprise active (pour le front)."""
    company_id = resolve_company_id_for_medical(current_user)
    result = queries.get_medical_settings(company_id, current_user)
    return SettingsResponse(enabled=result["enabled"])
