"""Helpers partagés badgeuse (privés aux sous-services)."""
from __future__ import annotations

from app.shared.domain.temps_local import maintenant_utc

from dataclasses import dataclass
from datetime import datetime, date
from typing import List, Dict, Any, Optional

from app.modules.badgeuse.application.badge_tokens import (
    build_qr_payload,  # noqa: F401 (ré-exporté via application.service)
    verify_qr_payload,  # noqa: F401 (ré-exporté via application.service)
)
from app.modules.badgeuse.domain.time_tracking import (
    TimeEntry,
    TimeEntryType,
    TimeEntrySource,
    compute_day_summary,
    compute_period_summaries,  # noqa: F401 (ré-exporté via application.service)
    group_entries_by_day,  # noqa: F401 (ré-exporté via application.service)
)
from app.modules.badgeuse.infrastructure.badge_credentials_repository import (
    badge_credentials_repository,  # noqa: F401 (ré-exporté via application.service)
)
from app.modules.badgeuse.infrastructure.repository import (
    time_entry_repository,
    time_entry_validation_repository,  # noqa: F401 (ré-exporté via application.service)
    day_accounting_repository,  # noqa: F401 (ré-exporté via application.service)
)
from app.modules.badgeuse.domain.day_accounting import (
    resolve_effective_seconds,
    has_accounting_override,
    override_differs_from_computed,
)
from app.modules.companies.infrastructure.repository import company_repository
from app.modules.employees.infrastructure.repository import EmployeeRepository
from app.modules.payroll.application.payslip_commands import is_forfait_jour
from app.modules.users.schemas.responses import User
from app.shared.utils.text import remove_accents  # noqa: F401 (ré-exporté via application.service)

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
    computed_seconds: int = 0
    accounted_seconds: int | None = None
    effective_seconds: int = 0
    has_override: bool = False
    override_differs_from_computed: bool = False


def _build_accounting_fields(
    computed_seconds: int, accounted_seconds: int | None
) -> dict[str, Any]:
    effective = resolve_effective_seconds(computed_seconds, accounted_seconds)
    return {
        "computed_seconds": computed_seconds,
        "accounted_seconds": accounted_seconds,
        "effective_seconds": effective,
        "has_override": has_accounting_override(accounted_seconds),
        "override_differs_from_computed": override_differs_from_computed(
            computed_seconds, accounted_seconds
        ),
        "total_seconds": computed_seconds,
    }


def get_company_id_from_user(current_user: User) -> str:
    if not current_user.company_id:
        raise ValueError("Utilisateur sans entreprise active")
    return str(current_user.company_id)


def _get_company_id_from_user(current_user: User) -> str:
    return get_company_id_from_user(current_user)


def resolve_my_employee_id_for_user(current_user: User) -> Optional[str]:
    """Résout employees.id pour le compte connecté (user_id, id ou e-mail)."""
    from app.shared.employee_resolution import resolve_employee_id_for_user_account

    company_id = _get_company_id_from_user(current_user)
    return resolve_employee_id_for_user_account(str(current_user.id), company_id)


def _user_is_forfait_jour(current_user: User) -> bool:
    # On réutilise la règle métier centrale is_forfait_jour à partir du statut
    explicit = getattr(current_user, "is_forfait_jour", None)
    statut = getattr(current_user, "statut", None)
    if not statut and hasattr(current_user, "job_title"):
        statut = getattr(current_user, "job_title")
    return is_forfait_jour(statut, explicit)


def _employee_is_forfait_jour(employee_row: Dict[str, Any]) -> bool:
    statut = employee_row.get("statut") or employee_row.get("job_title")
    return is_forfait_jour(statut, employee_row.get("is_forfait_jour"))


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
    terminal_device_id: Optional[str] = None,
) -> TimeEntryType:
    # Instant aware UTC : plus jamais d'horodatage naïf dépendant de
    # l'horloge du conteneur (les fenêtres de jour sont en heure locale
    # entreprise, voir app.shared.domain.temps_local).
    now = now or maintenant_utc()
    _check_debounce(entries, now)
    event_type = _resolve_next_event_type(entries)
    time_entry_repository.insert_entry(
        employee_id=employee_id,
        company_id=company_id,
        timestamp=now,
        event_type=event_type,
        source=source,
        created_by=created_by,
        terminal_device_id=terminal_device_id,
    )
    return event_type

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
