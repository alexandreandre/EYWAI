"""Queries compte d'heures modulation."""

from __future__ import annotations

from datetime import date

from app.modules.modulation.domain.hour_account_rules import (
    compute_acquired_and_taken,
    compute_balance_from_movements,
    solde_au,
)
from app.modules.modulation.infrastructure import repository as repo
from app.modules.modulation.schemas.requests import (
    ModulationBalanceResponse,
    ModulationMovementSchema,
)


def get_employee_account_balance(
    company_id: str,
    employee_id: str,
    year: int | None = None,
    *,
    month: int | None = None,
) -> ModulationBalanceResponse:
    ref_year = year or date.today().year
    # Le solde se reporte d'une année sur l'autre (repos non pris = dû) ;
    # acquis et pris restent ceux de l'année demandée.
    tous = repo.list_movements_for_employee(employee_id)
    balance = compute_balance_from_movements(tous)
    acquired, taken = compute_acquired_and_taken(
        [m for m in tous if int(m.get("year") or 0) == ref_year]
    )

    settings = repo.get_modulation_settings(company_id)
    franchise = float(settings.hs_franchise_hours_per_period or 0)
    franchise_consumed = 0.0
    if month is not None and franchise > 0:
        franchise_consumed = repo.get_franchise_consumed_in_period(
            employee_id, ref_year, month
        )
    franchise_remaining = max(0.0, round(franchise - franchise_consumed, 2))

    return ModulationBalanceResponse(
        employee_id=employee_id,
        year=ref_year,
        account_balance_hours=balance,
        acquired_hours=acquired,
        taken_hours=taken,
        franchise_remaining_hours=franchise_remaining,
    )


def list_employee_movements(
    employee_id: str,
    year: int | None = None,
    *,
    limit: int = 100,
    offset: int = 0,
) -> list[ModulationMovementSchema]:
    rows = repo.list_movements(employee_id, year, limit=limit, offset=offset)
    return [_movement_row_to_schema(r) for r in rows]


def _movement_row_to_schema(row: dict) -> ModulationMovementSchema:
    return ModulationMovementSchema(
        id=str(row["id"]),
        employee_id=str(row["employee_id"]),
        year=int(row["year"]),
        month=int(row["month"]) if row.get("month") is not None else None,
        movement_type=str(row.get("movement_type") or ""),
        hours=float(row.get("hours") or 0),
        status=str(row.get("status") or ""),
        source=str(row.get("source") or ""),
        reference_id=str(row["reference_id"]) if row.get("reference_id") else None,
        metadata=row.get("metadata") or {},
        note=row.get("note"),
        created_at=row.get("created_at"),
    )


def sync_account_balance_cache(
    company_id: str,
    employee_id: str,
    year: int,
) -> float:
    """Recalcule le solde compte depuis les mouvements et met à jour le cache compteur.

    Solde à la fin de l'année `year`, reports des années précédentes compris."""
    balance = solde_au(repo.list_movements_for_employee(employee_id), year, 12)
    counters = repo.list_employee_counters(company_id, year)
    existing = next(
        (c for c in counters if str(c.get("employee_id")) == employee_id),
        None,
    )
    if existing:
        repo.upsert_employee_counter(
            company_id,
            employee_id,
            year,
            float(existing.get("theoretical_hours") or 0),
            float(existing.get("actual_hours") or 0),
            float(existing.get("balance_hours") or 0),
            account_balance_hours=balance,
        )
    else:
        repo.upsert_employee_counter(
            company_id,
            employee_id,
            year,
            0.0,
            0.0,
            0.0,
            account_balance_hours=balance,
        )
    return balance


def _bulletin_du_mois(employee_id: str, year: int, month: int) -> dict | None:
    """Le bulletin du contrat de la fiche pour ce mois (sans ses données)."""
    from app.core.database import supabase

    resp = (
        supabase.table("payslips")
        .select("id, company_id, status, origine, year, month")
        .eq("employee_id", employee_id)
        .eq("year", year)
        .eq("month", month)
        .is_("contract_period_id", "null")
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


def raison_bulletin_fige(
    employee_id: str, year: int, month: int, *, bypass_lock: bool = False
) -> str | None:
    """Pourquoi on ne peut plus changer le compteur sur le bulletin de ce mois ;
    None si on peut. Sans ce refus, le compteur serait débité alors que le
    bulletin, qui ne se recalcule plus, ne porterait jamais le paiement."""
    from app.modules.payslips.application.period_edit_lock import (
        enrich_payslip_detail_with_edit_lock,
    )

    bulletin = _bulletin_du_mois(employee_id, year, month)
    if not bulletin:
        return None
    periode = f"{int(bulletin['month']):02d}/{bulletin['year']}"
    if str(bulletin.get("origine") or "") == "importe":
        return f"Le bulletin de {periode} est repris de l'ancien logiciel : il ne se recalcule pas."
    if str(bulletin.get("status") or "") == "valide":
        return (
            f"Le bulletin de {periode} est validé : ce choix se fait sur un bulletin "
            "pas encore validé."
        )
    detail = enrich_payslip_detail_with_edit_lock(bulletin, bypass_lock=bypass_lock)
    if detail.get("manual_edit_locked"):
        return str(detail.get("manual_edit_lock_reason") or f"Le bulletin de {periode} est verrouillé.")
    return None
