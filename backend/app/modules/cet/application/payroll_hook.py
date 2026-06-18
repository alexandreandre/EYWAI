"""Hook paie CET — réduction HS conjoncturelles."""

from __future__ import annotations

from typing import Any

from app.core.database import supabase
from app.modules.cet.infrastructure import repository as cet_repo


def apply_cet_deposits_to_calendar(
    employee_id: str,
    year: int,
    month: int,
    calendrier_etendu: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Réduit les heures de travail sur le calendrier étendu pour refléter
    les dépôts CET validés (heures non payées).
    Retourne (calendrier modifié, ids mouvements à marquer applied_payroll).
    """
    hours_to_deduct, movement_ids = cet_repo.get_validated_deposit_hours_for_payroll(
        employee_id, year, month
    )
    if hours_to_deduct <= 0 or not movement_ids:
        return calendrier_etendu, []

    remaining = hours_to_deduct
    updated: list[dict[str, Any]] = []
    for jour in reversed(calendrier_etendu):
        if remaining <= 0:
            updated.append(jour)
            continue
        entry = dict(jour)
        if entry.get("type") != "travail":
            updated.append(entry)
            continue
        heures = float(entry.get("heures") or 0)
        if heures <= 0:
            updated.append(entry)
            continue
        deduct = min(heures, remaining)
        entry["heures"] = round(heures - deduct, 2)
        remaining = round(remaining - deduct, 2)
        updated.append(entry)

    updated.reverse()
    return updated, movement_ids


def finalize_cet_payroll_application(movement_ids: list[str]) -> None:
    cet_repo.mark_movements_applied_payroll(movement_ids)


def apply_cet_cp_debits_for_payroll(
    employee_id: str, year: int, month: int
) -> list[str]:
    """
    Marque les dépôts CP validés du mois comme appliqués en paie
    (débit solde CP lorsque cp_debit_timing = on_payroll).
    """
    emp_resp = (
        supabase.table("employees")
        .select("company_id")
        .eq("id", employee_id)
        .limit(1)
        .execute()
    )
    rows = emp_resp.data or []
    if not rows:
        return []
    settings = cet_repo.get_cet_settings_row(str(rows[0]["company_id"]))
    if settings.get("cp_debit_timing") != "on_payroll":
        return []

    _, movement_ids = cet_repo.get_validated_deposit_cp_for_payroll(
        employee_id, year, month
    )
    if movement_ids:
        finalize_cet_payroll_application(movement_ids)
    return movement_ids
