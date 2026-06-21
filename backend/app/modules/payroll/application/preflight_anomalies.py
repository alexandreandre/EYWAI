"""
Agrégation des anomalies pré-paie (revue avant lancement).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional

from app.core.database import supabase
from app.modules.badgeuse.application import punch_service as badgeuse_service
from app.modules.payroll.infrastructure import preflight_repository
from app.modules.payroll.schemas.preflight_responses import (
    PreflightAnomaly,
    PreflightAnomalyCounts,
    PreflightAnomalyResolution,
    PreflightAnomaliesResponse,
    PreflightDayEcartDetail,
)
from app.modules.schedules.domain.ecart_rules import (
    compute_day_ecarts,
    compute_heures_supplementaires,
    compute_row_status,
    detect_absence_conflict_days,
    is_forfait_jour,
    month_period_bounds,
    sum_hours,
    validated_absence_days_in_month,
)

OPEN_STATUSES = frozenset({"a_traiter"})


def _anomaly_id(employee_id: str, anomaly_type: str) -> str:
    return f"{employee_id}:{anomaly_type}"


def _employee_name(first: Any, last: Any) -> str:
    return f"{str(first or '').strip()} {str(last or '').strip()}".strip()


def _resolution_key(employee_id: str, anomaly_type: str) -> str:
    return f"{employee_id}:{anomaly_type}"


def _merge_resolution(
    anomaly: PreflightAnomaly,
    resolution_row: Optional[Dict[str, Any]],
) -> PreflightAnomaly:
    if not resolution_row:
        return anomaly
    status = str(resolution_row.get("status") or "justifie")
    if status not in ("justifie", "resolu"):
        status = "justifie"
    anomaly.status = status  # type: ignore[assignment]
    anomaly.resolution = PreflightAnomalyResolution(
        status=status,  # type: ignore[arg-type]
        motif=resolution_row.get("motif"),
        commentaire=resolution_row.get("commentaire"),
        resolved_by=str(resolution_row.get("resolved_by") or "") or None,
        resolved_at=resolution_row.get("resolved_at"),
    )
    return anomaly


def _build_counts(anomalies: List[PreflightAnomaly]) -> PreflightAnomalyCounts:
    counts = PreflightAnomalyCounts()
    for a in anomalies:
        if a.type == "ecart_heures":
            counts.ecart_heures += 1
        elif a.type == "heures_non_saisies":
            counts.heures_non_saisies += 1
        elif a.type == "pointage":
            counts.pointage += 1
        elif a.type == "conflit_absence":
            counts.conflit_absence += 1
        elif a.type == "hs_routing_pending":
            counts.hs_routing_pending += 1
        elif a.type == "hs_pointage_a_valider":
            counts.hs_pointage_a_valider += 1
        if a.severity == "bloquant":
            counts.bloquant += 1
        else:
            counts.a_verifier += 1
    return counts


def build_preflight_anomalies(
    company_id: str, year: int, month: int
) -> PreflightAnomaliesResponse:
    emp_res = (
        supabase.table("employees")
        .select("id, first_name, last_name, statut, team_id")
        .eq("company_id", company_id)
        .eq("employment_status", "actif")
        .execute()
    )
    employees = emp_res.data or []
    if not employees:
        return PreflightAnomaliesResponse(
            year=year,
            month=month,
            total=0,
            total_open=0,
            total_treated=0,
            counts=PreflightAnomalyCounts(),
            anomalies=[],
        )

    employee_ids = [str(e["id"]) for e in employees]
    emp_by_id = {str(e["id"]): e for e in employees}

    sched_res = (
        supabase.table("employee_schedules")
        .select("employee_id, planned_calendar, actual_hours")
        .eq("company_id", company_id)
        .eq("year", year)
        .eq("month", month)
        .in_("employee_id", employee_ids)
        .execute()
    )
    schedule_by_emp = {str(r["employee_id"]): r for r in (sched_res.data or [])}

    absences: List[Dict[str, Any]] = []
    try:
        from app.modules.absences.infrastructure.repository import absence_repository

        absences = absence_repository.list_validated_for_employees(employee_ids)
    except Exception:
        absences = []

    absences_by_emp: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for a in absences:
        absences_by_emp[str(a.get("employee_id", ""))].append(a)

    start, end = month_period_bounds(year, month)
    badgeuse_summaries = badgeuse_service.get_company_period_summary(
        company_id=company_id,
        start=start,
        end=end,
        employee_ids=employee_ids,
    )

    resolution_rows = preflight_repository.list_resolutions(company_id, year, month)
    resolutions_by_key = {
        _resolution_key(str(r["employee_id"]), str(r["anomaly_type"])): r
        for r in resolution_rows
    }

    from app.modules.schedules.infrastructure import punch_accounting_repository as par

    pending_punch_reviews = par.list_overtime_reviews(
        company_id, year=year, month=month, status="pending"
    )
    pending_by_emp: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in pending_punch_reviews:
        pending_by_emp[str(row["employee_id"])].append(row)

    anomalies: List[PreflightAnomaly] = []

    for emp in employees:
        eid = str(emp["id"])
        name = _employee_name(emp.get("first_name"), emp.get("last_name"))
        team_id = str(emp["team_id"]) if emp.get("team_id") else None
        forfait = is_forfait_jour(emp.get("statut"))

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

        heures_prevues = sum_hours([d.get("heures_prevues") for d in planned_days])
        heures_faites = sum_hours([d.get("heures_faites") for d in actual_days])
        ecart = heures_faites - heures_prevues
        row_status = compute_row_status(planned_days, actual_days, year, month, forfait)

        if row_status == "a_saisir":
            anomaly = PreflightAnomaly(
                id=_anomaly_id(eid, "heures_non_saisies"),
                employee_id=eid,
                employee_name=name,
                team_id=team_id,
                type="heures_non_saisies",
                severity="bloquant",
                status="a_traiter",
                heures_prevues=heures_prevues,
                heures_faites=heures_faites,
                ecart=ecart,
                is_forfait_jour=forfait,
                message="Calendrier du mois incomplet — heures planifiées manquantes.",
            )
            anomalies.append(
                _merge_resolution(
                    anomaly,
                    resolutions_by_key.get(_resolution_key(eid, "heures_non_saisies")),
                )
            )

        if row_status == "saisi_avec_ecart":
            day_details = compute_day_ecarts(
                planned_days, actual_days, forfait=forfait
            )
            heures_sup = compute_heures_supplementaires(planned_days, actual_days)
            sub_type = "heures_sup" if heures_sup > 0 else None
            unit = "j" if forfait else "h"
            message = (
                f"Écart significatif entre planifié et réel "
                f"({ecart:+.1f}{unit})."
            )
            if heures_sup > 0:
                message += f" Heures sup. détectées : {heures_sup:.1f}h."

            anomaly = PreflightAnomaly(
                id=_anomaly_id(eid, "ecart_heures"),
                employee_id=eid,
                employee_name=name,
                team_id=team_id,
                type="ecart_heures",
                severity="bloquant",
                status="a_traiter",
                heures_prevues=heures_prevues,
                heures_faites=heures_faites,
                ecart=ecart if not forfait else None,
                is_forfait_jour=forfait,
                sub_type=sub_type,
                detail_jours=[
                    PreflightDayEcartDetail(**d) for d in day_details
                ],
                message=message,
            )
            anomalies.append(
                _merge_resolution(
                    anomaly,
                    resolutions_by_key.get(_resolution_key(eid, "ecart_heures")),
                )
            )

        validated_days = validated_absence_days_in_month(
            absences_by_emp.get(eid, []), year, month
        )
        conflict_days = detect_absence_conflict_days(planned_days, validated_days)
        if conflict_days:
            anomaly = PreflightAnomaly(
                id=_anomaly_id(eid, "conflit_absence"),
                employee_id=eid,
                employee_name=name,
                team_id=team_id,
                type="conflit_absence",
                severity="a_verifier",
                status="a_traiter",
                conflict_days=conflict_days,
                message=(
                    f"Conflit entre absences validées et calendrier "
                    f"({len(conflict_days)} jour(s))."
                ),
            )
            anomalies.append(
                _merge_resolution(
                    anomaly,
                    resolutions_by_key.get(_resolution_key(eid, "conflit_absence")),
                )
            )

        badge_summary = badgeuse_summaries.get(eid)
        if badge_summary and badge_summary.days_with_anomalies > 0:
            anomaly = PreflightAnomaly(
                id=_anomaly_id(eid, "pointage"),
                employee_id=eid,
                employee_name=name,
                team_id=team_id,
                type="pointage",
                severity="a_verifier",
                status="a_traiter",
                days_with_pointage_anomalies=badge_summary.days_with_anomalies,
                message=(
                    f"{badge_summary.days_with_anomalies} jour(s) avec pointage "
                    "incohérent (entrée/sortie)."
                ),
            )
            anomalies.append(
                _merge_resolution(
                    anomaly,
                    resolutions_by_key.get(_resolution_key(eid, "pointage")),
                )
            )

        emp_pending = pending_by_emp.get(eid) or []
        if emp_pending:
            total_hs = round(
                sum(float(r.get("overtime_hours") or 0) for r in emp_pending), 2
            )
            anomaly = PreflightAnomaly(
                id=_anomaly_id(eid, "hs_pointage_a_valider"),
                employee_id=eid,
                employee_name=name,
                team_id=team_id,
                type="hs_pointage_a_valider",
                severity="a_verifier",
                status="a_traiter",
                ecart=total_hs,
                message=(
                    f"{len(emp_pending)} jour(s) avec HS pointage à valider "
                    f"({total_hs:.2f} h)."
                ),
            )
            anomalies.append(
                _merge_resolution(
                    anomaly,
                    resolutions_by_key.get(
                        _resolution_key(eid, "hs_pointage_a_valider")
                    ),
                )
            )

    from app.modules.modulation.application import overtime_routing_queries as otr_q
    from app.modules.modulation.infrastructure import repository as mod_repo

    mod_settings = mod_repo.get_modulation_settings(company_id)
    if mod_settings.hs_routing_policy == "manual":
        routing_rows = otr_q.list_overtime_routing(company_id, year, month)
        for row in routing_rows:
            if row.get("status") == "validated":
                continue
            eid = str(row["employee_id"])
            emp = emp_by_id.get(eid) or {}
            anomaly = PreflightAnomaly(
                id=_anomaly_id(eid, "hs_routing_pending"),
                employee_id=eid,
                employee_name=str(row.get("employee_name") or _employee_name(
                    emp.get("first_name"), emp.get("last_name")
                )),
                team_id=str(emp["team_id"]) if emp.get("team_id") else None,
                type="hs_routing_pending",
                severity="bloquant",
                status="a_traiter",
                message=(
                    f"{float(row.get('total_hs_hours') or 0):.1f} h sup. — "
                    "décision payer / compteur requise."
                ),
            )
            anomalies.append(anomaly)

    counts = _build_counts(anomalies)
    total_open = sum(1 for a in anomalies if a.status in OPEN_STATUSES)
    total_treated = len(anomalies) - total_open

    return PreflightAnomaliesResponse(
        year=year,
        month=month,
        total=len(anomalies),
        total_open=total_open,
        total_treated=total_treated,
        counts=counts,
        anomalies=anomalies,
    )


def justify_anomaly(
    *,
    company_id: str,
    employee_id: str,
    year: int,
    month: int,
    anomaly_type: str,
    motif: str,
    commentaire: Optional[str],
    resolved_by: str,
) -> Dict[str, Any]:
    if motif == "autre" and not (commentaire or "").strip():
        raise ValueError("Un commentaire est obligatoire pour le motif « Autre ».")
    return preflight_repository.upsert_resolution(
        company_id=company_id,
        employee_id=employee_id,
        year=year,
        month=month,
        anomaly_type=anomaly_type,
        status="justifie",
        motif=motif,
        commentaire=commentaire,
        resolved_by=resolved_by,
    )


def remove_anomaly_justification(
    *,
    company_id: str,
    employee_id: str,
    year: int,
    month: int,
    anomaly_type: str,
) -> None:
    preflight_repository.delete_resolution(
        company_id=company_id,
        employee_id=employee_id,
        year=year,
        month=month,
        anomaly_type=anomaly_type,
    )


def acknowledge_preflight_launch(
    *,
    company_id: str,
    year: int,
    month: int,
    open_anomalies_count: int,
    anomaly_types_summary: List[str],
    commentaire: Optional[str],
    acknowledged_by: str,
) -> Dict[str, Any]:
    return preflight_repository.insert_acknowledgement(
        company_id=company_id,
        year=year,
        month=month,
        open_anomalies_count=open_anomalies_count,
        anomaly_types_summary=anomaly_types_summary,
        commentaire=commentaire,
        acknowledged_by=acknowledged_by,
    )
