from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date
from io import StringIO
from typing import List, Dict, Any, Iterable, Set, Tuple
import csv

from app.modules.badgeuse.domain.time_tracking import (
    TimeEntry,
    TimeEntryType,
    TimeEntrySource,
    compute_day_summary,
    compute_period_summaries,
    group_entries_by_day,
)
from app.modules.badgeuse.infrastructure.repository import (
    time_entry_repository,
    time_entry_validation_repository,
)
from app.modules.payroll.application.payslip_commands import is_forfait_jour
from app.modules.users.schemas.responses import User


@dataclass
class DayStatusDTO:
    date: date
    status: str
    total_seconds: int
    sequences_count: int
    has_anomalies: bool
    validated: bool = False


def _get_company_id_from_user(current_user: User) -> str:
    if not current_user.company_id:
        raise ValueError("Utilisateur sans entreprise active")
    return str(current_user.company_id)


def _user_is_forfait_jour(current_user: User) -> bool:
    # On réutilise la règle métier centrale is_forfait_jour à partir du statut
    statut = getattr(current_user, "statut", None)
    if not statut and hasattr(current_user, "job_title"):
        statut = getattr(current_user, "job_title")
    return is_forfait_jour(statut)


def get_today_status_for_me(
    current_user: User, day: date | None = None
) -> Dict[str, Any]:
    if _user_is_forfait_jour(current_user):
        return {
            "is_eligible_for_badgeuse": False,
            "reason": "Employé au forfait jours, badgeuse non applicable",
        }

    company_id = _get_company_id_from_user(current_user)
    target_day = day or date.today()
    entries = time_entry_repository.get_entries_for_employee_on_day(
        employee_id=str(current_user.id),
        company_id=company_id,
        day=target_day,
    )
    summary = compute_day_summary(entries)

    last_event_type = entries[-1].event_type.value if entries else None
    if not entries:
        status_label = "Vous n'avez pas encore badgé aujourd'hui."
        next_action = "ENTREE"
        since = None
    elif last_event_type == TimeEntryType.ENTREE.value:
        status_label = "Vous êtes actuellement pointé en présence."
        next_action = "SORTIE"
        since = entries[-1].timestamp.isoformat()
    else:
        status_label = "Votre dernière action est une sortie."
        next_action = "ENTREE"
        since = None

    return {
        "is_eligible_for_badgeuse": True,
        "date": summary.date.isoformat(),
        "status_label": status_label,
        "current_open_since": since,
        "next_action": next_action,
        "total_seconds": int(summary.total_duration.total_seconds()),
        "events": [
            {
                "id": e.id,
                "timestamp": e.timestamp.isoformat(),
                "event_type": e.event_type.value,
                "source": e.source.value,
            }
            for e in entries
        ],
    }


def toggle_badge_for_me(current_user: User) -> Dict[str, Any]:
    if _user_is_forfait_jour(current_user):
        raise PermissionError("Employé au forfait jours, badgeuse non applicable")

    company_id = _get_company_id_from_user(current_user)
    today = date.today()
    entries = time_entry_repository.get_entries_for_employee_on_day(
        employee_id=str(current_user.id),
        company_id=company_id,
        day=today,
    )
    now = datetime.utcnow()

    if not entries or entries[-1].event_type == TimeEntryType.SORTIE:
        event_type = TimeEntryType.ENTREE
    else:
        event_type = TimeEntryType.SORTIE

    time_entry_repository.insert_entry(
        employee_id=str(current_user.id),
        company_id=company_id,
        timestamp=now,
        event_type=event_type,
        source=TimeEntrySource.EMPLOYE,
        created_by=str(current_user.id),
    )

    return get_today_status_for_me(current_user)


def get_summary_for_employee_period(
    *,
    employee_id: str,
    company_id: str,
    start: date,
    end: date,
) -> Dict[date, DayStatusDTO]:
    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(end, datetime.max.time())
    entries = time_entry_repository.get_entries_for_employee_between(
        employee_id=employee_id,
        company_id=company_id,
        start=start_dt,
        end=end_dt,
    )
    summaries = compute_period_summaries(entries)

    validated_days: Set[date] = (
        time_entry_validation_repository.get_validated_days_for_employee_between(
            employee_id=employee_id,
            company_id=company_id,
            start=start,
            end=end,
        )
    )

    result: Dict[date, DayStatusDTO] = {}
    for d, summary in summaries.items():
        result[d] = DayStatusDTO(
            date=d,
            status=summary.status,
            total_seconds=int(summary.total_duration.total_seconds()),
            sequences_count=len(summary.sequences),
            has_anomalies=bool(summary.anomalies),
            validated=d in validated_days,
        )
    return result


def get_day_detail_for_employee(
    *,
    employee_id: str,
    company_id: str,
    day: date,
) -> Dict[str, Any]:
    entries = time_entry_repository.get_entries_for_employee_on_day(
        employee_id=employee_id,
        company_id=company_id,
        day=day,
    )
    summary = compute_day_summary(entries)
    return {
        "date": summary.date.isoformat(),
        "status": summary.status,
        "total_seconds": int(summary.total_duration.total_seconds()),
        "sequences_count": len(summary.sequences),
        "anomalies": [a.message for a in summary.anomalies],
        "validated": time_entry_validation_repository.is_day_validated(
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
    }


@dataclass
class EmployeePeriodSummary:
    employee_id: str
    total_seconds: int
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
    rows = time_entry_repository.get_entries_for_company_between(
        company_id=company_id,
        start=start_dt,
        end=end_dt,
        employee_ids=list(employee_ids) if employee_ids else None,
    )
    entries: List[TimeEntry] = [time_entry_repository._row_to_entry(r) for r in rows]  # type: ignore[attr-defined]

    by_employee: Dict[str, List[TimeEntry]] = {}
    for entry in entries:
        by_employee.setdefault(entry.employee_id, []).append(entry)

    result: Dict[str, EmployeePeriodSummary] = {}
    for emp_id, emp_entries in by_employee.items():
        by_day = group_entries_by_day(emp_entries)
        total = 0
        days_anomalies = 0
        for _, day_entries in by_day.items():
            summary = compute_day_summary(day_entries)
            total += int(summary.total_duration.total_seconds())
            if summary.anomalies:
                days_anomalies += 1
        result[emp_id] = EmployeePeriodSummary(
            employee_id=emp_id,
            total_seconds=total,
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
    time_entry_validation_repository.set_day_validated(
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
    time_entry_repository.insert_entry(
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
    updated = time_entry_repository.update_entry(
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
    time_entry_repository.delete_entry(event_id)


def build_company_summary_csv(
    *,
    company_id: str,
    start: date,
    end: date,
    employee_ids: Iterable[str] | None = None,
) -> Tuple[str, str]:
    """
    Construit le CSV de synthèse badgeuse pour une entreprise sur une période.
    Retourne (filename, contenu_csv).
    """
    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(end, datetime.max.time())
    rows = time_entry_repository.get_entries_for_company_between(
        company_id=company_id,
        start=start_dt,
        end=end_dt,
        employee_ids=list(employee_ids) if employee_ids else None,
    )

    grouped: Dict[str, Dict[date, List[TimeEntry]]] = {}
    for row in rows:
        emp_id = str(row["employee_id"])
        ts = datetime.fromisoformat(row["timestamp"])
        d = ts.date()
        grouped.setdefault(emp_id, {}).setdefault(d, []).append(
            time_entry_repository._row_to_entry(row)  # type: ignore[attr-defined]
        )

    output = StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(
        [
            "employe_id",
            "date",
            "total_heures",
            "nombre_sequences",
            "anomalie",
        ]
    )

    for emp_id, days in grouped.items():
        for d, entries in sorted(days.items(), key=lambda x: x[0]):
            summary = compute_day_summary(entries)
            total_hours = summary.total_duration.total_seconds() / 3600.0
            writer.writerow(
                [
                    emp_id,
                    d.isoformat(),
                    f"{total_hours:.2f}",
                    len(summary.sequences),
                    "oui" if summary.anomalies else "non",
                ]
            )

    output.seek(0)
    filename = f"badgeuse_{company_id}_{start.isoformat()}_{end.isoformat()}.csv"
    return filename, output.read()
