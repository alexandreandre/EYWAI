"""Écriture des périodes d'essai."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict, Optional

from app.modules.employees.domain.trial_period_dates import compute_trial_end
from app.modules.employees.domain.trial_period_shared import parse_date
from app.modules.trial_periods.domain.constants import (
    STATUS_CONFIRMEE,
    STATUS_EN_COURS,
)
from app.modules.trial_periods.infrastructure.repository import repository


def build_create_payload(
    company_id: str,
    employee_id: str,
    start_date: date,
    duration_value: int,
    duration_unit: str,
    renewal_allowed: bool,
    created_by: Optional[str],
) -> Dict[str, Any]:
    end = compute_trial_end(start_date, duration_value, duration_unit)
    if end is None:
        raise ValueError("durée de période d'essai inexploitable")

    return {
        "company_id": company_id,
        "employee_id": employee_id,
        "start_date": start_date.isoformat(),
        "duration_value": int(duration_value),
        "duration_unit": duration_unit,
        "renewal_allowed": bool(renewal_allowed),
        "end_date": end.isoformat(),
        "status": STATUS_EN_COURS,
        "created_by": created_by,
    }


def build_renewal_payload(
    trial_period: Dict[str, Any],
    renewed_at: date,
    renewal_duration_value: int,
    renewal_duration_unit: str,
    renewed_by: Optional[str],
) -> Dict[str, Any]:
    if not trial_period.get("renewal_allowed"):
        raise ValueError("le renouvellement n'est pas ouvert pour cette période")
    if trial_period.get("renewed_at"):
        raise ValueError("période déjà renouvelée : la loi n'en autorise qu'un")

    start = parse_date(trial_period.get("start_date"))
    if start is None:
        raise ValueError("date de début illisible")

    initial_end = compute_trial_end(
        start,
        trial_period.get("duration_value"),
        trial_period.get("duration_unit"),
    )
    if initial_end is None:
        raise ValueError("durée de période d'essai inexploitable")

    # Le renouvellement doit être notifié avant le terme initial, sans quoi il
    # est inopposable et le contrat est définitivement conclu.
    if renewed_at > initial_end:
        raise ValueError("renouvellement notifié après le terme de la période")

    end = compute_trial_end(
        start,
        trial_period.get("duration_value"),
        trial_period.get("duration_unit"),
        renewal_value=renewal_duration_value,
        renewal_unit=renewal_duration_unit,
    )
    if end is None:
        raise ValueError("durée de renouvellement inexploitable")

    return {
        "renewed_at": renewed_at.isoformat(),
        "renewal_duration_value": int(renewal_duration_value),
        "renewal_duration_unit": renewal_duration_unit,
        "renewed_by": renewed_by,
        "end_date": end.isoformat(),
    }


def build_confirm_payload(confirmed_by: Optional[str]) -> Dict[str, Any]:
    return {
        "status": STATUS_CONFIRMEE,
        "confirmed_at": datetime.now(timezone.utc).isoformat(),
        "confirmed_by": confirmed_by,
    }


def build_update_payload(
    trial_period: Dict[str, Any],
    start_date: Optional[date],
    duration_value: Optional[int],
    duration_unit: Optional[str],
    renewal_allowed: Optional[bool],
) -> Dict[str, Any]:
    start = start_date or parse_date(trial_period.get("start_date"))
    if start is None:
        raise ValueError("date de début illisible")
    value = (
        duration_value if duration_value is not None else trial_period.get("duration_value")
    )
    unit = duration_unit or trial_period.get("duration_unit")

    end = compute_trial_end(
        start,
        value,
        unit,
        renewal_value=trial_period.get("renewal_duration_value"),
        renewal_unit=trial_period.get("renewal_duration_unit"),
    )
    if end is None:
        raise ValueError("durée de période d'essai inexploitable")

    payload: Dict[str, Any] = {
        "start_date": start.isoformat(),
        "duration_value": int(value),
        "duration_unit": unit,
        "end_date": end.isoformat(),
    }
    if renewal_allowed is not None:
        payload["renewal_allowed"] = bool(renewal_allowed)
    return payload


def create_trial_period(**kwargs: Any) -> Dict[str, Any]:
    return repository.create(build_create_payload(**kwargs))


def update_trial_period(
    trial_period_id: str,
    start_date: Optional[date] = None,
    duration_value: Optional[int] = None,
    duration_unit: Optional[str] = None,
    renewal_allowed: Optional[bool] = None,
) -> Dict[str, Any]:
    current = repository.get_by_id(trial_period_id)
    if current is None:
        raise ValueError("période d'essai introuvable")
    payload = build_update_payload(
        current, start_date, duration_value, duration_unit, renewal_allowed
    )
    return repository.update(trial_period_id, payload)


def confirm_trial_period(
    trial_period_id: str, confirmed_by: Optional[str]
) -> Dict[str, Any]:
    return repository.update(trial_period_id, build_confirm_payload(confirmed_by))


def renew_trial_period(
    trial_period_id: str,
    renewed_at: date,
    renewal_duration_value: int,
    renewal_duration_unit: str,
    renewed_by: Optional[str],
) -> Dict[str, Any]:
    current = repository.get_by_id(trial_period_id)
    if current is None:
        raise ValueError("période d'essai introuvable")
    payload = build_renewal_payload(
        current, renewed_at, renewal_duration_value, renewal_duration_unit, renewed_by
    )
    return repository.update(trial_period_id, payload)


__all__ = [
    "build_confirm_payload",
    "build_create_payload",
    "build_renewal_payload",
    "build_update_payload",
    "confirm_trial_period",
    "create_trial_period",
    "renew_trial_period",
    "update_trial_period",
]
