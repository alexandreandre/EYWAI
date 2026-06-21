"""Règles métier compte d'heures modulation — domaine pur."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

MovementType = Literal[
    "credit_hs",
    "debit_recovery",
    "debit_payout",
    "adjustment",
    "opening_balance",
]

_CREDIT_TYPES = frozenset({"credit_hs", "opening_balance"})
_DEBIT_TYPES = frozenset({"debit_recovery", "debit_payout"})
_ACTIVE_STATUSES = frozenset({"validated", "applied_payroll"})

_HS_EVENT_TYPES = ("travail_hs25", "travail_hs50")


@dataclass(frozen=True)
class SplitHsResult:
    to_account: float
    to_pay: float


def split_hs_for_period(
    total_hs: float,
    franchise_hours: float,
    franchise_consumed_in_period: float,
    current_balance: float,
    max_balance: float | None = None,
) -> SplitHsResult:
    """
    Répartit les HS d'une période entre compte modulation et paie.

    franchise_hours : plafond de crédit compte sur la période (ex. 14 h/mois).
    """
    total_hs = max(0.0, round(float(total_hs), 2))
    if total_hs <= 0:
        return SplitHsResult(to_account=0.0, to_pay=0.0)

    franchise = max(0.0, float(franchise_hours or 0))
    consumed = max(0.0, float(franchise_consumed_in_period or 0))
    franchise_remaining = max(0.0, round(franchise - consumed, 2))

    to_account_raw = min(total_hs, franchise_remaining)

    if max_balance is not None:
        room = max(0.0, round(float(max_balance) - float(current_balance), 2))
        to_account = min(to_account_raw, room)
    else:
        to_account = to_account_raw

    to_account = round(max(0.0, to_account), 2)
    to_pay = round(max(0.0, total_hs - to_account), 2)
    return SplitHsResult(to_account=to_account, to_pay=to_pay)


def route_hs_for_period(
    total_hs: float,
    policy: str,
    franchise_hours: float,
    franchise_consumed_in_period: float,
    current_balance: float,
    max_balance: float | None = None,
    *,
    manual_to_account: float | None = None,
    manual_to_pay: float | None = None,
) -> SplitHsResult:
    """Routage HS selon politique entreprise."""
    total_hs = max(0.0, round(float(total_hs), 2))
    if total_hs <= 0:
        return SplitHsResult(to_account=0.0, to_pay=0.0)

    if policy == "pay_all":
        return SplitHsResult(to_account=0.0, to_pay=total_hs)

    if policy == "account_all":
        return SplitHsResult(to_account=total_hs, to_pay=0.0)

    if policy == "manual":
        to_account = round(max(0.0, float(manual_to_account or 0)), 2)
        to_pay = round(max(0.0, float(manual_to_pay or 0)), 2)
        if round(to_account + to_pay, 2) != total_hs:
            return SplitHsResult(to_account=0.0, to_pay=total_hs)
        return SplitHsResult(to_account=to_account, to_pay=to_pay)

    cap = None if policy == "account_all" else max_balance
    return split_hs_for_period(
        total_hs,
        franchise_hours,
        franchise_consumed_in_period,
        current_balance,
        cap,
    )


def _movement_signed_hours(movement_type: str, hours: float) -> float:
    h = abs(float(hours))
    if movement_type in _CREDIT_TYPES:
        return h
    if movement_type in _DEBIT_TYPES:
        return -h
    if movement_type == "adjustment":
        return float(hours)
    return 0.0


def compute_balance_from_movements(movements: list[dict[str, Any]]) -> float:
    """Solde compte = somme des mouvements validés ou appliqués en paie."""
    total = 0.0
    for m in movements:
        status = str(m.get("status") or "")
        if status not in _ACTIVE_STATUSES:
            continue
        mtype = str(m.get("movement_type") or "")
        hours = float(m.get("hours") or 0)
        total += _movement_signed_hours(mtype, hours)
    return round(total, 2)


def compute_acquired_and_taken(movements: list[dict[str, Any]]) -> tuple[float, float]:
    """Retourne (heures créditées, heures consommées en récup)."""
    acquired = 0.0
    taken = 0.0
    for m in movements:
        if str(m.get("status") or "") not in _ACTIVE_STATUSES:
            continue
        mtype = str(m.get("movement_type") or "")
        hours = abs(float(m.get("hours") or 0))
        if mtype in _CREDIT_TYPES or (mtype == "adjustment" and float(m.get("hours") or 0) > 0):
            acquired += hours
        elif mtype == "debit_recovery":
            taken += hours
    return round(acquired, 2), round(taken, 2)


def can_debit_recovery(balance: float, hours: float) -> bool:
    return round(float(balance), 2) >= round(max(0.0, float(hours)), 2)


def sum_hs_from_payroll_events(events: list[dict[str, Any]]) -> float:
    total = 0.0
    for ev in events:
        ev_type = str(ev.get("type") or "")
        if ev_type in _HS_EVENT_TYPES or "hs" in ev_type:
            if ev_type.startswith("travail_hs"):
                total += float(ev.get("heures") or 0)
    return round(total, 2)


def reduce_payroll_hs_events(
    events: list[dict[str, Any]],
    hours_to_defer: float,
) -> tuple[list[dict[str, Any]], float]:
    """
    Retire des heures HS des événements de paie (HS25 puis HS50) pour crédit compte.
    Retourne (événements modifiés, heures effectivement différées).
    """
    remaining = round(max(0.0, float(hours_to_defer)), 2)
    if remaining <= 0:
        return events, 0.0

    def _hs_sort_key(ev: dict[str, Any]) -> tuple[int, Any]:
        t = str(ev.get("type") or "")
        order = 0 if t == "travail_hs25" else 1 if t == "travail_hs50" else 2
        return (order, ev.get("jour"), ev.get("mois"))

    sorted_indices = sorted(range(len(events)), key=lambda i: _hs_sort_key(events[i]))
    mutable = [dict(e) for e in events]
    deferred = 0.0

    for idx in sorted_indices:
        if remaining <= 0:
            break
        ev = mutable[idx]
        ev_type = str(ev.get("type") or "")
        if ev_type not in _HS_EVENT_TYPES:
            continue
        heures = float(ev.get("heures") or 0)
        if heures <= 0:
            continue
        take = min(heures, remaining)
        ev["heures"] = round(heures - take, 2)
        remaining = round(remaining - take, 2)
        deferred = round(deferred + take, 2)

    out = [ev for ev in mutable if not (
        str(ev.get("type") or "") in _HS_EVENT_TYPES and float(ev.get("heures") or 0) <= 0
    )]
    return out, deferred


def reduce_hs_in_calendar(
    calendrier: list[dict[str, Any]],
    hours_to_defer: float,
) -> tuple[list[dict[str, Any]], float]:
    """Réduit les heures HS dans le calendrier étendu bulletin (comme hook CET)."""
    remaining = round(max(0.0, float(hours_to_defer)), 2)
    if remaining <= 0:
        return calendrier, 0.0

    deferred = 0.0
    updated: list[dict[str, Any]] = []

    for jour in reversed(calendrier):
        if remaining <= 0:
            updated.append(jour)
            continue
        entry = dict(jour)
        ev_type = str(entry.get("type") or "")
        if ev_type not in _HS_EVENT_TYPES:
            updated.append(entry)
            continue
        heures = float(entry.get("heures") or 0)
        if heures <= 0:
            updated.append(entry)
            continue
        deduct = min(heures, remaining)
        entry["heures"] = round(heures - deduct, 2)
        remaining = round(remaining - deduct, 2)
        deferred = round(deferred + deduct, 2)
        if entry["heures"] > 0:
            updated.append(entry)

    updated.reverse()
    return updated, deferred
