"""
Agrégation Analytics Gestion — cockpit RH (entretiens, formation, calendriers, médical, carrière, CSE).
"""

from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.database import supabase
from app.modules.annual_reviews.infrastructure.repository import SupabaseAnnualReviewRepository
from app.modules.certifications.application import queries as cert_queries
from app.modules.cse.application import queries as cse_queries
from app.modules.dashboard.schemas.analytics_gestion import (
    AnalyticsGestionPeriod,
    AnalyticsGestionResponse,
    CalendriersAnalytics,
    CarriereAnalytics,
    ConformiteAnalytics,
    CseAnalytics,
    CseMeetingPreview,
    EntretiensAnalytics,
    FormationAnalytics,
    MedicalAnalytics,
    ObjectivesAnalytics,
)
from app.modules.legal_obligations.application import queries as legal_queries
from app.modules.medical_follow_up.application import queries as medical_queries
from app.modules.medical_follow_up.application.service import get_obligation_repository
from app.modules.objectives.application.queries import get_achievement_rate
from app.modules.promotions.application.queries import get_promotion_stats_query
from app.modules.training.application.queries import get_evaluations_summary
from app.modules.training.infrastructure.repository import training_repository
from app.modules.training_budget.application.queries import get_budget

ACTIONABLE_STATUSES = frozenset({"planifie", "en_attente_acceptation", "accepte"})
CLOSED_STATUSES = frozenset({"realise", "cloture"})
ANNUAL_REVIEW_PRIORITY_DAYS = 14
ECART_THRESHOLD_HOURS = 2.0
ECART_THRESHOLD_RATIO = 0.1


def _parse_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    raw = str(value)[:10]
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _period_year(period_start: str, period_end: str) -> int:
    end = _parse_date(period_end) or date.today()
    return end.year


def _calendar_month_for_overview(period_end: str) -> Tuple[int, int]:
    """Calendriers paie : mois contenant la fin de période (ou mois courant)."""
    end = _parse_date(period_end) or date.today()
    return end.year, end.month


def _month_period_bounds(year: int, month: int) -> Tuple[date, date]:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def _is_forfait_jour(statut: Optional[str]) -> bool:
    if not statut:
        return False
    s = str(statut).lower().replace(" ", "_")
    return "forfait" in s and "jour" in s


def _sum_hours(values: List[Any]) -> float:
    total = 0.0
    for v in values:
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            total += float(v)
    return total


def _compute_month_completion(planned_days: List[Dict[str, Any]], year: int, month: int) -> str:
    days_in_month = calendar.monthrange(year, month)[1]
    by_jour = {int(d.get("jour", 0)): d for d in planned_days if d.get("jour")}
    for day in range(1, days_in_month + 1):
        dt = date(year, month, day)
        if dt.weekday() >= 5:
            continue
        row = by_jour.get(day)
        if row is None:
            return "a_saisir"
        hp = row.get("heures_prevues")
        if hp is None:
            return "a_saisir"
    return "saisi"


def _compute_row_status(
    planned_days: List[Dict[str, Any]],
    actual_days: List[Dict[str, Any]],
    year: int,
    month: int,
    forfait: bool,
) -> str:
    completion = _compute_month_completion(planned_days, year, month)
    if completion == "a_saisir":
        return "a_saisir"
    heures_prevues = _sum_hours([d.get("heures_prevues") for d in planned_days])
    heures_faites = _sum_hours([d.get("heures_faites") for d in actual_days])
    if forfait:
        jours_prevus = sum(
            1
            for d in planned_days
            if d.get("type") == "travail" and d.get("heures_prevues") == 1
        )
        jours_faits = sum(
            1 for d in actual_days if d.get("heures_faites") == 1
        )
        return "saisi_avec_ecart" if jours_faits != jours_prevus else "saisi"
    ecart = abs(heures_faites - heures_prevues)
    if ecart <= ECART_THRESHOLD_HOURS:
        return "saisi"
    if heures_prevues <= 0:
        return "saisi_avec_ecart" if ecart > ECART_THRESHOLD_HOURS else "saisi"
    if ecart / heures_prevues > ECART_THRESHOLD_RATIO:
        return "saisi_avec_ecart"
    return "saisi"


def _validated_absence_days_in_month(
    absences: List[Dict[str, Any]], year: int, month: int
) -> Set[int]:
    days: Set[int] = set()
    start, end = _month_period_bounds(year, month)
    for req in absences:
        selected = req.get("selected_days")
        if not isinstance(selected, list):
            continue
        for raw in selected:
            d = _parse_date(raw)
            if d and start <= d <= end:
                days.add(d.day)
    return days


def _detect_absence_conflicts(
    planned_days: List[Dict[str, Any]], validated_days: Set[int]
) -> int:
    conflicts = 0
    by_jour = {int(d.get("jour", 0)): d for d in planned_days if d.get("jour")}
    for day in validated_days:
        row = by_jour.get(day)
        if not row:
            conflicts += 1
            continue
        t = str(row.get("type") or "")
        if t not in ("arret_maladie", "conge"):
            conflicts += 1
    return conflicts


def _build_entretiens_stats(company_id: str, year: int) -> EntretiensAnalytics:
    repo = SupabaseAnnualReviewRepository()
    rows = repo.list_by_company(company_id, year=year)
    today = date.today()
    window_end = today + timedelta(days=ANNUAL_REVIEW_PRIORITY_DAYS)

    by_status: Dict[str, int] = defaultdict(int)
    actionable = 0
    overdue = 0
    upcoming_14d = 0
    closed = 0
    total = len(rows)

    for row in rows:
        status = str(row.get("status") or "")
        by_status[status] += 1
        if status in CLOSED_STATUSES:
            closed += 1
        if status not in ACTIONABLE_STATUSES:
            continue
        actionable += 1
        planned = _parse_date(row.get("planned_date"))
        if planned and planned < today:
            overdue += 1
        elif planned and today <= planned <= window_end:
            upcoming_14d += 1
        elif not planned and status in ("en_attente_acceptation", "accepte"):
            upcoming_14d += 1

    closure_rate = round((closed / total) * 100.0, 1) if total else 0.0
    return EntretiensAnalytics(
        actionable_count=actionable,
        overdue_count=overdue,
        upcoming_14d_count=upcoming_14d,
        closure_rate_pct=closure_rate,
        by_status=dict(by_status),
    )


def _build_calendriers_overview(
    company_id: str, year: int, month: int
) -> CalendriersAnalytics:
    emp_res = (
        supabase.table("employees")
        .select("id, statut")
        .eq("company_id", company_id)
        .eq("employment_status", "actif")
        .execute()
    )
    employees = emp_res.data or []
    if not employees:
        return CalendriersAnalytics()

    employee_ids = [str(e["id"]) for e in employees]
    sched_res = (
        supabase.table("employee_schedules")
        .select("employee_id, planned_calendar, actual_hours")
        .eq("company_id", company_id)
        .eq("year", year)
        .eq("month", month)
        .in_("employee_id", employee_ids)
        .execute()
    )
    schedule_by_emp = {
        str(r["employee_id"]): r for r in (sched_res.data or [])
    }

    absences = []
    try:
        from app.modules.absences.infrastructure.repository import absence_repository

        absences = absence_repository.list_validated_for_employees(employee_ids)
    except Exception:
        absences = []

    absences_by_emp: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for a in absences:
        absences_by_emp[str(a.get("employee_id", ""))].append(a)

    total = len(employees)
    saisis = 0
    a_saisir = 0
    avec_ecart = 0
    conflits = 0

    for emp in employees:
        eid = str(emp["id"])
        forfait = _is_forfait_jour(emp.get("statut"))
        sched = schedule_by_emp.get(eid) or {}
        planned_raw = sched.get("planned_calendar") or {}
        actual_raw = sched.get("actual_hours") or {}
        planned_days = (
            planned_raw.get("calendrier_prevu", [])
            if isinstance(planned_raw, dict)
            else []
        )
        actual_days = (
            actual_raw.get("calendrier_reel", [])
            if isinstance(actual_raw, dict)
            else []
        )
        row_status = _compute_row_status(
            planned_days, actual_days, year, month, forfait
        )
        if row_status == "a_saisir":
            a_saisir += 1
        else:
            saisis += 1
        if row_status == "saisi_avec_ecart":
            avec_ecart += 1
        validated_days = _validated_absence_days_in_month(
            absences_by_emp.get(eid, []), year, month
        )
        if _detect_absence_conflicts(planned_days, validated_days) > 0:
            conflits += 1

    progress = round((saisis / total) * 100) if total else 0
    return CalendriersAnalytics(
        total=total,
        saisis=saisis,
        a_saisir=a_saisir,
        avec_ecart=avec_ecart,
        conflits_absences=conflits,
        progress_percent=progress,
    )


def _build_medical(company_id: str) -> MedicalAnalytics:
    kpis = medical_queries.get_kpis(company_id, current_user=None)
    repo = get_obligation_repository()
    rows = repo.list_for_company(company_id)
    today = date.today()

    total_obligations = len(rows)
    compliant = 0
    overdue_by_emp: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for row in rows:
        status = str(row.get("status") or "")
        due = _parse_date(row.get("due_date"))
        if status == "realisee":
            compliant += 1
        elif due and due < today and status in ("a_faire", "planifiee"):
            eid = str(row.get("employee_id", ""))
            overdue_by_emp[eid].append(row)

    compliance_rate = (
        round((compliant / total_obligations) * 100.0, 1) if total_obligations else 0.0
    )

    employees_overdue_top: List[Dict[str, object]] = []
    for eid, emp_rows in overdue_by_emp.items():
        due_dates = [_parse_date(r.get("due_date")) for r in emp_rows]
        due_valid = [d for d in due_dates if d]
        most_urgent = min(due_valid) if due_valid else today
        first = emp_rows[0]
        name = (
            f"{(first.get('employee_first_name') or '').strip()} "
            f"{(first.get('employee_last_name') or '').strip()}"
        ).strip() or eid
        employees_overdue_top.append(
            {
                "employee_id": eid,
                "employee_name": name,
                "obligations_overdue": len(emp_rows),
                "most_urgent_due_date": most_urgent.isoformat(),
            }
        )
    employees_overdue_top.sort(
        key=lambda x: str(x.get("most_urgent_due_date") or "")
    )
    employees_overdue_top = employees_overdue_top[:5]

    return MedicalAnalytics(
        overdue_count=kpis.overdue_count,
        due_within_30_count=kpis.due_within_30_count,
        active_total=kpis.active_total,
        completed_this_month=kpis.completed_this_month,
        compliance_rate_pct=compliance_rate,
        employees_overdue_top=employees_overdue_top,
    )


def _build_formation(company_id: str, year: int) -> FormationAnalytics:
    consumed_year = float(training_repository.get_total_consumed(company_id, year))
    eval_items = get_evaluations_summary(company_id)
    eval_count = len(eval_items)
    eval_avg: Optional[float] = None
    if eval_items:
        ratings = [
            float(getattr(x, "avg_rating", 0) or 0)
            for x in eval_items
            if getattr(x, "avg_rating", None) is not None
        ]
        if ratings:
            eval_avg = round(sum(ratings) / len(ratings), 2)

    try:
        budget = get_budget(company_id, year)
        return FormationAnalytics(
            budget_consumption_pct=round(budget.consumption_pct, 1),
            budget_alert_level=budget.alert_level,
            budget_consumed=round(budget.consumed, 2),
            budget_envelope=round(budget.global_envelope, 2),
            training_consumed_year=consumed_year,
            evaluations_count=eval_count,
            evaluations_average=eval_avg,
        )
    except LookupError:
        return FormationAnalytics(
            training_consumed_year=consumed_year,
            evaluations_count=eval_count,
            evaluations_average=eval_avg,
        )


def _build_conformite(company_id: str) -> ConformiteAnalytics:
    cert = cert_queries.get_dashboard_counts(company_id)
    overdue = legal_queries.get_overdue_count(company_id).count
    all_status = legal_queries.get_all_status(company_id)
    due_soon = sum(1 for s in all_status if s.professional_interview_status == "due_soon")
    up_to_date = sum(
        1 for s in all_status if s.professional_interview_status == "up_to_date"
    )
    return ConformiteAnalytics(
        certifications_expired=cert.expired,
        certifications_expiring=cert.expiring,
        legal_obligations_overdue=overdue,
        legal_obligations_due_soon=due_soon,
        legal_obligations_up_to_date=up_to_date,
    )


def _build_carriere(company_id: str, year: int) -> CarriereAnalytics:
    stats = get_promotion_stats_query(company_id, year=year)
    draft_count = 0
    try:
        from app.modules.promotions.infrastructure.repository import get_promotion_repository

        drafts = get_promotion_repository().list(
            company_id=company_id, year=year, status="draft", limit=500
        )
        draft_count = len(drafts)
    except Exception:
        draft_count = 0

    avenants_pending = 0
    try:
        doc_res = (
            supabase.table("generated_documents")
            .select("id", count="exact")
            .eq("company_id", company_id)
            .eq("document_type", "avenant_salaire")
            .in_("status", ["brouillon", "envoye"])
            .execute()
        )
        avenants_pending = int(doc_res.count or 0)
    except Exception:
        avenants_pending = 0

    return CarriereAnalytics(
        total_promotions=stats.total_promotions,
        approval_rate_pct=round(stats.approval_rate, 1),
        average_salary_increase_pct=stats.average_salary_increase,
        promotions_by_month=dict(stats.promotions_by_month),
        promotions_draft_count=draft_count,
        avenants_pending_signature=avenants_pending,
    )


def _build_cse(company_id: str) -> CseAnalytics:
    today = date.today()
    period_start = date(today.year, today.month, 1)
    period_end = date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])

    mandate_alerts = cse_queries.get_mandate_alerts(company_id, months_before=3)
    election_alerts = cse_queries.get_election_alerts(company_id)
    critical = sum(
        1
        for a in election_alerts
        if str(getattr(a, "alert_level", "") or getattr(a, "level", "")) == "critical"
    )

    summary = cse_queries.get_delegation_summary(company_id, period_start, period_end)
    over_quota = 0
    consumed = 0.0
    quota = 0.0
    for row in summary:
        remaining = float(getattr(row, "remaining_hours", 0) or 0)
        consumed_h = float(getattr(row, "consumed_hours", 0) or 0)
        quota_h = float(getattr(row, "quota_hours_per_month", 0) or 0)
        consumed += consumed_h
        quota += quota_h
        if remaining < 0:
            over_quota += 1

    meetings = cse_queries.get_meetings(company_id, status="a_venir")
    previews: List[CseMeetingPreview] = []
    sorted_meetings = sorted(
        meetings,
        key=lambda m: str(getattr(m, "meeting_date", "") or ""),
    )[:3]
    for m in sorted_meetings:
        previews.append(
            CseMeetingPreview(
                id=str(getattr(m, "id", "")),
                title=str(getattr(m, "title", "Réunion")),
                meeting_date=str(getattr(m, "meeting_date", "")),
                meeting_time=getattr(m, "meeting_time", None),
            )
        )

    return CseAnalytics(
        mandate_alerts_count=len(mandate_alerts),
        election_alerts_count=len(election_alerts),
        election_critical_count=critical,
        delegation_over_quota_count=over_quota,
        delegation_consumed_hours=round(consumed, 1),
        delegation_quota_hours=round(quota, 1),
        upcoming_meetings=previews,
    )


def build_analytics_gestion(
    company_id: str,
    period_start: str,
    period_end: str,
) -> AnalyticsGestionResponse:
    """Construit la réponse agrégée Analytics Gestion pour une entreprise RH."""
    year = _period_year(period_start, period_end)
    cal_year, cal_month = _calendar_month_for_overview(period_end)

    achievement = get_achievement_rate(company_id, year)
    objectives = ObjectivesAnalytics(
        achievement_rate_pct=round(achievement, 1) if achievement is not None else None
    )

    return AnalyticsGestionResponse(
        period=AnalyticsGestionPeriod(
            period_start=period_start,
            period_end=period_end,
            year=year,
            calendar_year=cal_year,
            calendar_month=cal_month,
        ),
        entretiens=_build_entretiens_stats(company_id, year),
        conformite=_build_conformite(company_id),
        formation=_build_formation(company_id, year),
        calendriers=_build_calendriers_overview(company_id, cal_year, cal_month),
        medical=_build_medical(company_id),
        objectives=objectives,
        carriere=_build_carriere(company_id, year),
        cse=_build_cse(company_id),
    )
