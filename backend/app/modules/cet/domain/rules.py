"""Règles métier CET — logique pure."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


HOURS_PER_REST_DAY_DEFAULT = 7.0
OUVRES_TO_OUVRABLES_DEFAULT = 1.2

CP_COMMIT_STATUSES = ("pending", "validated", "applied_payroll")
CET_BALANCE_STATUSES = ("validated", "applied_payroll")


@dataclass(frozen=True)
class CetMovementRow:
    movement_type: str
    hours: float
    status: str
    days: float = 0.0
    year: int = 0


@dataclass(frozen=True)
class CetSettingsSnapshot:
    allow_deposit_hs: bool = True
    allow_deposit_cp: bool = False
    max_cp_days_per_year: float | None = None
    max_account_balance_days: float | None = None
    cp_unit: str = "ouvrables"
    ouvres_to_ouvrables_ratio: float = OUVRES_TO_OUVRABLES_DEFAULT
    hours_per_rest_day: float = HOURS_PER_REST_DAY_DEFAULT


def ouvrables_to_ouvres(ouvrables: float, ratio: float = OUVRES_TO_OUVRABLES_DEFAULT) -> float:
    if ratio <= 0:
        return 0.0
    return round(float(ouvrables) / ratio, 2)


def ouvres_to_ouvrables(ouvres: float, ratio: float = OUVRES_TO_OUVRABLES_DEFAULT) -> float:
    return round(float(ouvres) * ratio, 2)


def convert_cp_days_between_units(
    days: float,
    from_unit: str,
    to_unit: str,
    ratio: float = OUVRES_TO_OUVRABLES_DEFAULT,
) -> float:
    if from_unit == to_unit:
        return round(float(days), 2)
    if from_unit == "ouvres" and to_unit == "ouvrables":
        return ouvres_to_ouvrables(days, ratio)
    if from_unit == "ouvrables" and to_unit == "ouvres":
        return ouvrables_to_ouvres(days, ratio)
    return round(float(days), 2)


def compute_cet_balance_hours(
    movements: Sequence[CetMovementRow],
    *,
    hours_per_rest_day: float = HOURS_PER_REST_DAY_DEFAULT,
) -> float:
    """Solde CET en heures (HS + CP convertis en heures)."""
    balance = 0.0
    for m in movements:
        if m.status not in CET_BALANCE_STATUSES:
            continue
        if m.movement_type == "deposit_hs":
            balance += float(m.hours)
        elif m.movement_type == "deposit_cp":
            balance += float(m.days) * hours_per_rest_day
        elif m.movement_type == "withdraw_rest":
            balance -= abs(float(m.hours))
        elif m.movement_type == "adjustment":
            balance += float(m.hours)
    return round(max(0.0, balance), 2)


def compute_cet_balance_days(
    movements: Sequence[CetMovementRow],
    *,
    hours_per_rest_day: float = HOURS_PER_REST_DAY_DEFAULT,
) -> float:
    """Solde CET en jours équivalents."""
    hours = compute_cet_balance_hours(movements, hours_per_rest_day=hours_per_rest_day)
    if hours_per_rest_day <= 0:
        return 0.0
    return round(hours / hours_per_rest_day, 2)


def compute_cp_transferred_days_year(
    movements: Sequence[CetMovementRow],
    year: int,
) -> float:
    """Jours CP engagés sur l'année (pending + validés + appliqués paie)."""
    total = 0.0
    for m in movements:
        if m.movement_type != "deposit_cp":
            continue
        if m.year != year:
            continue
        if m.status not in CP_COMMIT_STATUSES:
            continue
        total += float(m.days)
    return round(total, 2)


def remaining_cp_transfer_quota(
    max_cp_days_per_year: float | None,
    transferred_days: float,
) -> float | None:
    """Reste transférable ; None = pas de plafond."""
    if max_cp_days_per_year is None:
        return None
    return round(max(0.0, float(max_cp_days_per_year) - transferred_days), 2)


def compute_cp_days_committed_for_absences(
    movements: Sequence[CetMovementRow],
    year: int,
    *,
    cp_debit_timing: str,
) -> float:
    """
    Jours CP à compter dans le solde CP disponible (absences).
    on_validation : pending + validated + applied_payroll
    on_payroll : seulement applied_payroll (validated en attente de paie)
    """
    total = 0.0
    for m in movements:
        if m.movement_type != "deposit_cp" or m.year != year:
            continue
        if m.status == "rejected":
            continue
        if cp_debit_timing == "on_payroll":
            if m.status != "applied_payroll":
                continue
        else:
            if m.status not in CP_COMMIT_STATUSES:
                continue
        total += float(m.days)
    return round(total, 2)


def compute_spareable_overtime_hours(
    overtime_hours_month: float,
    movements: Sequence[CetMovementRow],
) -> float:
    committed = sum(
        float(m.hours)
        for m in movements
        if m.movement_type == "deposit_hs"
        and m.status in CP_COMMIT_STATUSES
    )
    return round(max(0.0, overtime_hours_month - committed), 2)


def validate_deposit_hours(hours: float, spareable: float) -> None:
    if hours <= 0:
        raise ValueError("Le nombre d'heures à épargner doit être strictement positif.")
    if hours > spareable + 0.001:
        raise ValueError(
            f"Heures sup épargables insuffisantes : {spareable:.2f} h disponible(s), "
            f"{hours:.2f} h demandée(s)."
        )


def validate_deposit_cp(
    days: float,
    *,
    quota_remaining: float | None,
    cp_balance_available: float,
) -> None:
    if days <= 0:
        raise ValueError("Le nombre de jours à transférer doit être strictement positif.")
    if quota_remaining is not None and days > quota_remaining + 0.001:
        raise ValueError(
            f"Plafond annuel CET dépassé : il reste {quota_remaining:.2f} j "
            f"transférable(s), {days:.2f} j demandé(s)."
        )
    if days > cp_balance_available + 0.001:
        raise ValueError(
            f"Solde congés payés insuffisant : {cp_balance_available:.2f} j disponible(s), "
            f"{days:.2f} j demandé(s)."
        )


def validate_withdraw_hours(hours: float, balance: float) -> None:
    if hours <= 0:
        raise ValueError("Le nombre d'heures à retirer doit être strictement positif.")
    if hours > balance + 0.001:
        raise ValueError(
            f"Solde CET insuffisant : {balance:.2f} h disponible(s), "
            f"{hours:.2f} h demandée(s)."
        )


def validate_account_balance_cap(
    additional_days: float,
    current_balance_days: float,
    max_account_balance_days: float | None,
) -> None:
    if max_account_balance_days is None:
        return
    projected = current_balance_days + additional_days
    if projected > float(max_account_balance_days) + 0.001:
        raise ValueError(
            f"Plafond du compte CET dépassé : maximum {max_account_balance_days:.2f} j, "
            f"solde après opération {projected:.2f} j."
        )


def hours_to_rest_days(hours: float, hours_per_rest_day: float) -> float:
    if hours_per_rest_day <= 0:
        return 0.0
    return round(hours / hours_per_rest_day, 2)
