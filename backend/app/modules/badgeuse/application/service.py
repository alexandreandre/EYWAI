from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date
from io import StringIO
from typing import List, Dict, Any, Iterable, Set, Tuple, Optional
import csv

from app.modules.badgeuse.application.badge_tokens import (
    build_qr_payload,
    verify_qr_payload,
)
from app.modules.badgeuse.domain.time_tracking import (
    TimeEntry,
    TimeEntryType,
    TimeEntrySource,
    compute_day_summary,
    compute_period_summaries,
    group_entries_by_day,
)
from app.modules.badgeuse.infrastructure.badge_credentials_repository import (
    badge_credentials_repository,
)
from app.modules.badgeuse.infrastructure.repository import (
    time_entry_repository,
    time_entry_validation_repository,
)
from app.modules.companies.infrastructure.repository import company_repository
from app.modules.employees.infrastructure.repository import EmployeeRepository
from app.modules.payroll.application.payslip_commands import is_forfait_jour
from app.modules.users.schemas.responses import User
from app.shared.utils.text import remove_accents

_employee_repository = EmployeeRepository()

DEBOUNCE_SECONDS = 4


@dataclass
class DayStatusDTO:
    date: date
    status: str
    total_seconds: int
    sequences_count: int
    has_anomalies: bool
    validated: bool = False


def get_company_id_from_user(current_user: User) -> str:
    if not current_user.company_id:
        raise ValueError("Utilisateur sans entreprise active")
    return str(current_user.company_id)


def _get_company_id_from_user(current_user: User) -> str:
    return get_company_id_from_user(current_user)


def _user_is_forfait_jour(current_user: User) -> bool:
    # On réutilise la règle métier centrale is_forfait_jour à partir du statut
    statut = getattr(current_user, "statut", None)
    if not statut and hasattr(current_user, "job_title"):
        statut = getattr(current_user, "job_title")
    return is_forfait_jour(statut)


def _employee_is_forfait_jour(employee_row: Dict[str, Any]) -> bool:
    statut = employee_row.get("statut") or employee_row.get("job_title")
    return is_forfait_jour(statut)


def get_badgeuse_settings(company_id: str) -> Dict[str, bool]:
    settings = company_repository.get_settings(company_id) or {}
    badgeuse = settings.get("badgeuse") or {}
    return {
        "allow_self_toggle": bool(badgeuse.get("allow_self_toggle", True)),
        "scan_mode_enabled": bool(badgeuse.get("scan_mode_enabled", True)),
    }


def update_badgeuse_settings(
    company_id: str,
    *,
    allow_self_toggle: Optional[bool] = None,
    scan_mode_enabled: Optional[bool] = None,
) -> Dict[str, bool]:
    settings = dict(company_repository.get_settings(company_id) or {})
    badgeuse = dict(settings.get("badgeuse") or {})
    if allow_self_toggle is not None:
        badgeuse["allow_self_toggle"] = allow_self_toggle
    if scan_mode_enabled is not None:
        badgeuse["scan_mode_enabled"] = scan_mode_enabled
    settings["badgeuse"] = badgeuse
    company_repository.update_settings(company_id, settings)
    return get_badgeuse_settings(company_id)


def _status_response_payload(
    *,
    summary,
    entries: List[TimeEntry],
    employee_display_name: str,
    qr_payload: Optional[str] = None,
    badge_username: Optional[str] = None,
) -> Dict[str, Any]:
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
        "employee_display_name": employee_display_name,
        "badge_username": badge_username,
        "qr_payload": qr_payload,
        "anomalies": [a.message for a in summary.anomalies],
        "sequences": [
            {
                "start": s.start.isoformat(),
                "end": s.end.isoformat(),
                "duration_seconds": int(s.duration.total_seconds()),
            }
            for s in summary.sequences
        ],
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


def _resolve_next_event_type(entries: List[TimeEntry]) -> TimeEntryType:
    if not entries or entries[-1].event_type == TimeEntryType.SORTIE:
        return TimeEntryType.ENTREE
    return TimeEntryType.SORTIE


def _check_debounce(entries: List[TimeEntry], now: datetime) -> None:
    if not entries:
        return
    last = entries[-1]
    delta = (now - last.timestamp).total_seconds()
    if delta < DEBOUNCE_SECONDS:
        raise ValueError(
            f"Pointage trop rapide. Attendez {DEBOUNCE_SECONDS} secondes."
        )


def _insert_toggle_entry(
    *,
    employee_id: str,
    company_id: str,
    entries: List[TimeEntry],
    source: TimeEntrySource,
    created_by: str,
    now: Optional[datetime] = None,
) -> TimeEntryType:
    # Use local runtime clock to stay consistent with date.today() windows.
    now = now or datetime.now()
    _check_debounce(entries, now)
    event_type = _resolve_next_event_type(entries)
    time_entry_repository.insert_entry(
        employee_id=employee_id,
        company_id=company_id,
        timestamp=now,
        event_type=event_type,
        source=source,
        created_by=created_by,
    )
    return event_type


def get_qr_for_employee(
    *, employee_id: str, company_id: str
) -> Dict[str, Any]:
    row = _employee_repository.get_by_id(employee_id, company_id)
    if not row:
        raise ValueError("Employé introuvable")
    if _employee_is_forfait_jour(row):
        raise PermissionError("Employé au forfait jours, badgeuse non applicable")
    creds = badge_credentials_repository.ensure_credentials(
        employee_id=employee_id, company_id=company_id
    )
    payload = build_qr_payload(
        company_id=company_id,
        employee_id=employee_id,
        token_version=int(creds["token_version"]),
        secret_salt=str(creds["secret_salt"]),
    )
    return {
        "qr_payload": payload,
        "employee_display_name": f"{row.get('first_name', '')} {row.get('last_name', '')}".strip(),
        "badge_username": row.get("username"),
        "token_version": int(creds["token_version"]),
    }


def regenerate_badge_for_employee(
    *, employee_id: str, company_id: str
) -> Dict[str, Any]:
    creds = badge_credentials_repository.regenerate_credentials(
        employee_id=employee_id, company_id=company_id
    )
    row = _employee_repository.get_by_id(employee_id, company_id)
    if not row:
        raise ValueError("Employé introuvable")
    payload = build_qr_payload(
        company_id=company_id,
        employee_id=employee_id,
        token_version=int(creds["token_version"]),
        secret_salt=str(creds["secret_salt"]),
    )
    return {
        "qr_payload": payload,
        "token_version": int(creds["token_version"]),
        "employee_display_name": f"{row.get('first_name', '')} {row.get('last_name', '')}".strip(),
    }


def _normalize_search_text(value: str) -> str:
    return remove_accents(value or "").lower().strip()


def punch_from_qr(
    *,
    qr_payload: Optional[str],
    employee_id: Optional[str],
    company_id: str,
    actor_user_id: str,
    source: TimeEntrySource = TimeEntrySource.QR_SCAN,
) -> Dict[str, Any]:
    if not get_badgeuse_settings(company_id).get("scan_mode_enabled", True):
        raise PermissionError("Le mode scan est désactivé pour cette entreprise")

    from app.modules.badgeuse.application.badge_tokens import parse_qr_payload

    resolved_employee_id: Optional[str] = employee_id
    if qr_payload:
        parsed = parse_qr_payload(qr_payload)
        if not parsed:
            raise ValueError("QR code invalide")
        if parsed.company_id != company_id:
            raise ValueError("QR code non valide pour cette entreprise")
        creds = badge_credentials_repository.get_credentials(
            employee_id=parsed.employee_id, company_id=company_id
        )
        if not creds or creds.get("revoked_at"):
            raise ValueError("Badge révoqué ou introuvable")
        verified = verify_qr_payload(
            qr_payload,
            secret_salt=str(creds["secret_salt"]),
            expected_version=int(creds["token_version"]),
        )
        if not verified:
            raise ValueError("QR code invalide ou expiré")
        resolved_employee_id = parsed.employee_id

    if not resolved_employee_id:
        raise ValueError("Employé non identifié")

    row = _employee_repository.get_by_id(resolved_employee_id, company_id)
    if not row:
        raise ValueError("Employé introuvable")
    if _employee_is_forfait_jour(row):
        raise PermissionError("Employé au forfait jours, badgeuse non applicable")

    today = date.today()
    entries = time_entry_repository.get_entries_for_employee_on_day(
        employee_id=resolved_employee_id,
        company_id=company_id,
        day=today,
    )
    now = datetime.now()
    event_type = _insert_toggle_entry(
        employee_id=resolved_employee_id,
        company_id=company_id,
        entries=entries,
        source=source,
        created_by=actor_user_id,
        now=now,
    )

    return _build_punch_response(
        employee_id=resolved_employee_id,
        company_id=company_id,
        employee_row=row,
        event_type=event_type,
        punched_at=now,
    )


def _build_punch_response(
    *,
    employee_id: str,
    company_id: str,
    employee_row: Dict[str, Any],
    event_type: TimeEntryType,
    punched_at: datetime,
) -> Dict[str, Any]:
    today = punched_at.date()
    updated_entries = time_entry_repository.get_entries_for_employee_on_day(
        employee_id=employee_id,
        company_id=company_id,
        day=today,
    )
    summary = compute_day_summary(updated_entries)
    display_name = (
        f"{employee_row.get('first_name', '')} {employee_row.get('last_name', '')}".strip()
    )
    return {
        "employee_id": employee_id,
        "employee_name": display_name,
        "event_type": event_type.value,
        "timestamp": punched_at.isoformat(),
        "total_seconds_today": int(summary.total_duration.total_seconds()),
        "status_label": (
            "Entrée enregistrée"
            if event_type == TimeEntryType.ENTREE
            else "Sortie enregistrée"
        ),
    }


def punch_by_username(
    *,
    username: str,
    company_id: str,
    actor_user_id: str,
) -> Dict[str, Any]:
    """Fallback scan : identification par nom d'utilisateur (matricule)."""
    from app.core.database import supabase

    result = (
        supabase.table("employees")
        .select("id")
        .eq("company_id", company_id)
        .eq("username", username.strip())
        .eq("employment_status", "actif")
        .maybe_single()
        .execute()
    )
    if not result.data:
        raise ValueError("Aucun employé actif avec cet identifiant")
    return punch_from_qr(
        qr_payload=None,
        employee_id=str(result.data["id"]),
        company_id=company_id,
        actor_user_id=actor_user_id,
        source=TimeEntrySource.RH,
    )


def list_punch_candidates(
    *,
    company_id: str,
    search: Optional[str] = None,
    only_not_badged_today: bool = False,
    limit: int = 24,
) -> List[Dict[str, Any]]:
    """
    Liste les employés éligibles au badgeage (recherche RH sans QR).
    """
    if not get_badgeuse_settings(company_id).get("scan_mode_enabled", True):
        raise PermissionError("Le mode scan est désactivé pour cette entreprise")

    from app.core.database import supabase

    today = date.today()
    start_dt = datetime.combine(today, datetime.min.time())
    end_dt = datetime.combine(today, datetime.max.time())

    emp_result = (
        supabase.table("employees")
        .select("id, first_name, last_name, username, statut, job_title")
        .eq("company_id", company_id)
        .eq("employment_status", "actif")
        .order("last_name")
        .execute()
    )
    employees = [
        e for e in (emp_result.data or []) if not _employee_is_forfait_jour(e)
    ]

    rows = time_entry_repository.get_entries_for_company_between(
        company_id=company_id,
        start=start_dt,
        end=end_dt,
        employee_ids=[str(e["id"]) for e in employees] if employees else None,
    )
    by_employee: Dict[str, List[TimeEntry]] = {}
    for row in rows:
        entry = time_entry_repository._row_to_entry(row)  # type: ignore[attr-defined]
        by_employee.setdefault(entry.employee_id, []).append(entry)

    query = _normalize_search_text(search) if search else ""

    candidates: List[Dict[str, Any]] = []
    for emp in employees:
        emp_id = str(emp["id"])
        day_entries = by_employee.get(emp_id, [])
        badged_today = bool(day_entries)
        if only_not_badged_today and badged_today:
            continue

        first = str(emp.get("first_name") or "").strip()
        last = str(emp.get("last_name") or "").strip()
        username = str(emp.get("username") or "").strip()
        display_name = f"{first} {last}".strip() or username or emp_id

        if query:
            haystack = _normalize_search_text(
                f"{first} {last} {username} {display_name}"
            )
            if query not in haystack and not any(
                part in haystack for part in query.split() if len(part) >= 2
            ):
                continue

        next_action = (
            _resolve_next_event_type(day_entries).value
            if day_entries
            else TimeEntryType.ENTREE.value
        )
        candidates.append(
            {
                "employee_id": emp_id,
                "display_name": display_name,
                "username": username or None,
                "badged_today": badged_today,
                "next_action": next_action,
            }
        )

    candidates.sort(
        key=lambda c: (
            c["badged_today"],
            c["display_name"].lower(),
        )
    )
    return candidates[: max(1, min(limit, 50))]


def get_dashboard_today(*, company_id: str) -> Dict[str, Any]:
    today = date.today()
    start_dt = datetime.combine(today, datetime.min.time())
    end_dt = datetime.combine(today, datetime.max.time())

    from app.core.database import supabase

    emp_result = (
        supabase.table("employees")
        .select("id, first_name, last_name, statut, job_title")
        .eq("company_id", company_id)
        .eq("employment_status", "actif")
        .execute()
    )
    employees = emp_result.data or []
    eligible_ids = [
        str(e["id"])
        for e in employees
        if not _employee_is_forfait_jour(e)
    ]

    rows = time_entry_repository.get_entries_for_company_between(
        company_id=company_id,
        start=start_dt,
        end=end_dt,
        employee_ids=eligible_ids if eligible_ids else None,
    )
    by_employee: Dict[str, List[TimeEntry]] = {}
    for row in rows:
        entry = time_entry_repository._row_to_entry(row)  # type: ignore[attr-defined]
        by_employee.setdefault(entry.employee_id, []).append(entry)

    present_count = 0
    anomaly_count = 0
    badged_ids: Set[str] = set()

    for emp_id in eligible_ids:
        day_entries = by_employee.get(emp_id, [])
        if day_entries:
            badged_ids.add(emp_id)
            summary = compute_day_summary(day_entries)
            if summary.anomalies:
                anomaly_count += 1
            if day_entries[-1].event_type == TimeEntryType.ENTREE:
                present_count += 1

    not_badged_count = len(eligible_ids) - len(badged_ids)

    last_scans: List[Dict[str, Any]] = []
    all_entries = sorted(
        [time_entry_repository._row_to_entry(r) for r in rows],  # type: ignore[attr-defined]
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
    if _user_is_forfait_jour(current_user):
        return {
            "is_eligible_for_badgeuse": False,
            "reason": "Employé au forfait jours, badgeuse non applicable",
        }

    company_id = _get_company_id_from_user(current_user)
    employee_id = str(current_user.id)
    target_day = day or date.today()
    entries = time_entry_repository.get_entries_for_employee_on_day(
        employee_id=employee_id,
        company_id=company_id,
        day=target_day,
    )
    summary = compute_day_summary(entries)

    row = _employee_repository.get_by_id(employee_id, company_id)
    display_name = (
        f"{row.get('first_name', '')} {row.get('last_name', '')}".strip()
        if row
        else ""
    )
    badge_username = row.get("username") if row else None

    qr_payload = None
    settings = get_badgeuse_settings(company_id)
    if target_day == date.today():
        try:
            qr_data = get_qr_for_employee(
                employee_id=employee_id, company_id=company_id
            )
            qr_payload = qr_data.get("qr_payload")
        except PermissionError:
            pass

    payload = _status_response_payload(
        summary=summary,
        entries=entries,
        employee_display_name=display_name,
        qr_payload=qr_payload,
        badge_username=badge_username,
    )
    payload["allow_self_toggle"] = settings.get("allow_self_toggle", True)
    return payload


def toggle_badge_for_me(current_user: User) -> Dict[str, Any]:
    if _user_is_forfait_jour(current_user):
        raise PermissionError("Employé au forfait jours, badgeuse non applicable")

    company_id = _get_company_id_from_user(current_user)
    settings = get_badgeuse_settings(company_id)
    if not settings.get("allow_self_toggle", True):
        raise PermissionError(
            "Le badgeage depuis votre téléphone est désactivé. "
            "Présentez votre QR à la borne."
        )

    today = date.today()
    employee_id = str(current_user.id)
    entries = time_entry_repository.get_entries_for_employee_on_day(
        employee_id=employee_id,
        company_id=company_id,
        day=today,
    )
    _insert_toggle_entry(
        employee_id=employee_id,
        company_id=company_id,
        entries=entries,
        source=TimeEntrySource.EMPLOYE,
        created_by=employee_id,
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
