"""Tableau de bord, pointage collaborateur, validation."""
from __future__ import annotations

from app.shared.domain.temps_local import aujourd_hui_local

from app.modules.badgeuse.application.deps import deps
from app.modules.badgeuse.application._internals import *  # noqa: F403
from app.modules.badgeuse.application.qr_service import get_qr_for_employee


def get_dashboard_today(*, company_id: str) -> Dict[str, Any]:
    today = aujourd_hui_local()
    start_dt = datetime.combine(today, datetime.min.time())
    end_dt = datetime.combine(today, datetime.max.time())

    from app.core.database import supabase

    emp_result = (
        supabase.table("employees")
        .select("id, first_name, last_name, statut, is_forfait_jour, job_title")
        .eq("company_id", company_id)
        .eq("employment_status", "actif")
        .execute()
    )
    employees = emp_result.data or []
    eligible_ids = [
        str(e["id"])
        for e in employees
        if not deps._employee_is_forfait_jour(e)
    ]

    rows = deps.time_entry_repository.get_entries_for_company_between(
        company_id=company_id,
        start=start_dt,
        end=end_dt,
        employee_ids=eligible_ids if eligible_ids else None,
    )
    by_employee: Dict[str, List[TimeEntry]] = {}
    for row in rows:
        entry = deps.time_entry_repository._row_to_entry(row)  # type: ignore[attr-defined]
        by_employee.setdefault(entry.employee_id, []).append(entry)

    present_count = 0
    anomaly_count = 0
    badged_ids: Set[str] = set()

    for emp_id in eligible_ids:
        day_entries = by_employee.get(emp_id, [])
        if day_entries:
            badged_ids.add(emp_id)
            summary = deps.compute_day_summary(day_entries)
            if summary.anomalies:
                anomaly_count += 1
            if day_entries[-1].event_type == TimeEntryType.ENTREE:
                present_count += 1

    not_badged_count = len(eligible_ids) - len(badged_ids)

    last_scans: List[Dict[str, Any]] = []
    all_entries = sorted(
        [deps.time_entry_repository._row_to_entry(r) for r in rows],  # type: ignore[attr-defined]
        key=lambda e: e.timestamp,
        reverse=True,
    )[:8]
    names_by_id = {
        str(e["id"]): f"{e.get('first_name', '')} {e.get('last_name', '')}".strip()
        for e in employees
    }
    for entry in all_entries:
        last_scans.append(
            {
                "id": entry.id,
                "employee_id": entry.employee_id,
                "employee_name": names_by_id.get(entry.employee_id, entry.employee_id),
                "event_type": entry.event_type.value,
                "timestamp": entry.timestamp.isoformat(),
                "source": entry.source.value,
            }
        )

    return {
        "date": today.isoformat(),
        "present_count": present_count,
        "not_badged_count": not_badged_count,
        "anomaly_count": anomaly_count,
        "eligible_count": len(eligible_ids),
        "last_scans": last_scans,
    }


def get_today_status_for_me(
    current_user: User, day: date | None = None
) -> Dict[str, Any]:
    if deps._user_is_forfait_jour(current_user):
        return {
            "is_eligible_for_badgeuse": False,
            "reason": "Employé au forfait jours, badgeuse non applicable",
        }

    company_id = deps.get_company_id_from_user(current_user)
    employee_id = deps.resolve_my_employee_id_for_user(current_user)
    if not employee_id:
        return {
            "is_eligible_for_badgeuse": False,
            "reason": "Aucune fiche employé n'est reliée à votre compte.",
        }
    target_day = day or date.today()
    entries = deps.time_entry_repository.get_entries_for_employee_on_day(
        employee_id=employee_id,
        company_id=company_id,
        day=target_day,
    )
    summary = deps.compute_day_summary(entries)

    row = deps._employee_repository.get_by_id(employee_id, company_id)
    display_name = (
        f"{row.get('first_name', '')} {row.get('last_name', '')}".strip()
        if row
        else ""
    )
    badge_username = row.get("username") if row else None

    qr_payload = None
    settings = deps.get_badgeuse_settings(company_id)
    if target_day == date.today():
        try:
            qr_data = get_qr_for_employee(
                employee_id=employee_id, company_id=company_id
            )
            qr_payload = qr_data.get("qr_payload")
        except PermissionError:
            pass

    payload = deps._status_response_payload(
        summary=summary,
        entries=entries,
        employee_display_name=display_name,
        qr_payload=qr_payload,
        badge_username=badge_username,
    )
    payload["allow_self_toggle"] = settings.get("allow_self_toggle", True)
    return payload


def toggle_badge_for_me(current_user: User) -> Dict[str, Any]:
    if deps._user_is_forfait_jour(current_user):
        raise PermissionError("Employé au forfait jours, badgeuse non applicable")

    company_id = deps.get_company_id_from_user(current_user)
    settings = deps.get_badgeuse_settings(company_id)
    if not settings.get("allow_self_toggle", True):
        raise PermissionError(
            "Le badgeage depuis votre téléphone est désactivé. "
            "Présentez votre QR à la borne."
        )

    employee_id = deps.resolve_my_employee_id_for_user(current_user)
    if not employee_id:
        raise PermissionError(
            "Aucune fiche employé n'est reliée à votre compte."
        )

    today = aujourd_hui_local()
    entries = deps.time_entry_repository.get_entries_for_employee_on_day(
        employee_id=employee_id,
        company_id=company_id,
        day=today,
    )
    deps._insert_toggle_entry(
        employee_id=employee_id,
        company_id=company_id,
        entries=entries,
        source=TimeEntrySource.EMPLOYE,
        created_by=str(current_user.id),
    )

    from app.modules.badgeuse.application import service as badgeuse_service

    return badgeuse_service.get_today_status_for_me(current_user)


def get_summary_for_employee_period(
    *,
    employee_id: str,
    company_id: str,
    start: date,
    end: date,
) -> Dict[date, deps.DayStatusDTO]:
    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(end, datetime.max.time())
    entries = deps.time_entry_repository.get_entries_for_employee_between(
        employee_id=employee_id,
        company_id=company_id,
        start=start_dt,
        end=end_dt,
    )
    summaries = deps.compute_period_summaries(entries)

    validated_days: Set[date] = (
        deps.time_entry_validation_repository.get_validated_days_for_employee_between(
            employee_id=employee_id,
            company_id=company_id,
            start=start,
            end=end,
        )
    )
    accounting_by_day = deps.day_accounting_repository.get_for_employee_between(
        employee_id=employee_id,
        company_id=company_id,
        start=start,
        end=end,
    )

    all_days = set(summaries.keys()) | set(accounting_by_day.keys())

    result: Dict[date, deps.DayStatusDTO] = {}
    for d in sorted(all_days):
        summary = summaries.get(d)
        if summary:
            computed = int(summary.total_duration.total_seconds())
            status = summary.status
            sequences_count = len(summary.sequences)
            has_anomalies = bool(summary.anomalies)
        else:
            computed = 0
            status = "Absent"
            sequences_count = 0
            has_anomalies = False

        accounted = accounting_by_day.get(d)
        accounting = deps._build_accounting_fields(computed, accounted)
        result[d] = deps.DayStatusDTO(
            date=d,
            status=status,
            total_seconds=computed,
            sequences_count=sequences_count,
            has_anomalies=has_anomalies,
            validated=d in validated_days,
            computed_seconds=accounting["computed_seconds"],
            accounted_seconds=accounting["accounted_seconds"],
            effective_seconds=accounting["effective_seconds"],
            has_override=accounting["has_override"],
            override_differs_from_computed=accounting["override_differs_from_computed"],
        )
    return result


def get_day_detail_for_employee(
    *,
    employee_id: str,
    company_id: str,
    day: date,
) -> Dict[str, Any]:
    entries = deps.time_entry_repository.get_entries_for_employee_on_day(
        employee_id=employee_id,
        company_id=company_id,
        day=day,
    )
    summary = deps.compute_day_summary(entries)
    computed = int(summary.total_duration.total_seconds())
    accounted = deps.day_accounting_repository.get_accounted_seconds(
        employee_id=employee_id,
        company_id=company_id,
        day=day,
    )
    accounting = deps._build_accounting_fields(computed, accounted)
    return {
        "date": summary.date.isoformat(),
        "status": summary.status,
        "total_seconds": computed,
        "sequences_count": len(summary.sequences),
        "anomalies": [a.message for a in summary.anomalies],
        "validated": deps.time_entry_validation_repository.is_day_validated(
            employee_id=employee_id,
            company_id=company_id,
            day=day,
        ),
        "events": [
            {
                "id": e.id,
                "timestamp": e.timestamp.isoformat(),
                "event_type": e.event_type.value,
                "source": e.source.value,
            }
            for e in entries
        ],
        **accounting,
    }


@dataclass
class EmployeePeriodSummary:
    employee_id: str
    total_seconds: int
    total_effective_seconds: int
    days_with_anomalies: int


def get_company_period_summary(
    *,
    company_id: str,
    start: date,
    end: date,
    employee_ids: Iterable[str] | None = None,
) -> Dict[str, EmployeePeriodSummary]:
    """
    Synthèse par employé sur la période : total d'heures et nombre de jours en anomalie.
    """
    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(end, datetime.max.time())
    rows = deps.time_entry_repository.get_entries_for_company_between(
        company_id=company_id,
        start=start_dt,
        end=end_dt,
        employee_ids=list(employee_ids) if employee_ids else None,
    )
    entries: List[TimeEntry] = [deps.time_entry_repository._row_to_entry(r) for r in rows]  # type: ignore[attr-defined]

    accounting_map = deps.day_accounting_repository.get_for_company_between(
        company_id=company_id,
        start=start,
        end=end,
        employee_ids=list(employee_ids) if employee_ids else None,
    )

    by_employee: Dict[str, List[TimeEntry]] = {}
    for entry in entries:
        by_employee.setdefault(entry.employee_id, []).append(entry)

    employee_id_set: Set[str] = set(by_employee.keys())
    for emp_id, _ in accounting_map:
        employee_id_set.add(emp_id)

    result: Dict[str, EmployeePeriodSummary] = {}
    for emp_id in employee_id_set:
        emp_entries = by_employee.get(emp_id, [])
        by_day = deps.group_entries_by_day(emp_entries)
        total = 0
        total_effective = 0
        days_anomalies = 0
        all_days = set(by_day.keys())
        for (acc_emp_id, acc_day), _ in list(accounting_map.items()):
            if acc_emp_id == emp_id:
                all_days.add(acc_day)
        for d in all_days:
            day_entries = by_day.get(d, [])
            if day_entries:
                summary = deps.compute_day_summary(day_entries)
                computed = int(summary.total_duration.total_seconds())
                if summary.anomalies:
                    days_anomalies += 1
            else:
                computed = 0
            accounted = accounting_map.get((emp_id, d))
            effective = deps.resolve_effective_seconds(computed, accounted)
            total += computed
            total_effective += effective
        result[emp_id] = EmployeePeriodSummary(
            employee_id=emp_id,
            total_seconds=total,
            total_effective_seconds=total_effective,
            days_with_anomalies=days_anomalies,
        )
    return result


def validate_day_for_employee(
    *,
    employee_id: str,
    company_id: str,
    day: date,
    current_user: User,
) -> Dict[str, Any]:
    """
    Marque une journée comme validée par un RH et renvoie le détail de la journée.
    """
    deps.time_entry_validation_repository.set_day_validated(
        employee_id=employee_id,
        company_id=company_id,
        day=day,
        validated_by=str(current_user.id),
    )
    return get_day_detail_for_employee(
        employee_id=employee_id,
        company_id=company_id,
        day=day,
    )


def add_event_for_employee_day(
    *,
    employee_id: str,
    company_id: str,
    timestamp: datetime,
    event_type: TimeEntryType,
    source: TimeEntrySource,
    current_user: User,
) -> Dict[str, Any]:
    """
    Ajoute un évènement de pointage et renvoie le détail de la journée correspondante.
    """
    deps.time_entry_repository.insert_entry(
        employee_id=employee_id,
        company_id=company_id,
        timestamp=timestamp,
        event_type=event_type,
        source=source,
        created_by=str(current_user.id),
    )
    day = timestamp.date()
    return get_day_detail_for_employee(
        employee_id=employee_id,
        company_id=company_id,
        day=day,
    )


def update_event_for_employee_day(
    *,
    event_id: str,
    timestamp: datetime | None,
    event_type: TimeEntryType | None,
    current_user: User,
) -> Dict[str, Any]:
    """
    Met à jour un évènement de pointage et renvoie le détail de la journée correspondante.
    """
    updated = deps.time_entry_repository.update_entry(
        event_id,
        timestamp=timestamp,
        event_type=event_type,
        updated_by=str(current_user.id),
    )
    day = updated.timestamp.date()
    return get_day_detail_for_employee(
        employee_id=updated.employee_id,
        company_id=updated.company_id,
        day=day,
    )


def delete_event_for_employee_day(*, event_id: str) -> None:
    """
    Supprime un évènement de pointage.
    """
    deps.time_entry_repository.delete_entry(event_id)


def set_accounted_hours_for_day(
    *,
    employee_id: str,
    company_id: str,
    day: date,
    accounted_seconds: int,
    current_user: User,
) -> Dict[str, Any]:
    if accounted_seconds < 0 or accounted_seconds > 86400:
        raise ValueError("Durée comptabilisée invalide (0 à 24h)")
    deps.day_accounting_repository.set_accounted_seconds(
        employee_id=employee_id,
        company_id=company_id,
        day=day,
        accounted_seconds=accounted_seconds,
        updated_by=str(current_user.id),
    )
    return get_day_detail_for_employee(
        employee_id=employee_id,
        company_id=company_id,
        day=day,
    )


def clear_accounted_hours_for_day(
    *,
    employee_id: str,
    company_id: str,
    day: date,
) -> Dict[str, Any]:
    deps.day_accounting_repository.clear_accounted_seconds(
        employee_id=employee_id,
        company_id=company_id,
        day=day,
    )
    return get_day_detail_for_employee(
        employee_id=employee_id,
        company_id=company_id,
        day=day,
    )

