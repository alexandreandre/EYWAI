"""Import des participations depuis des saisies mensuelles existantes.

Reconstruit rétroactivement une campagne bulletin d'option clôturée (choix
déjà fait, participation déjà versée) à partir des `monthly_inputs`
existantes — pour les sociétés dont la participation a été saisie directement
en paie, hors du workflow normal `create_campaign` → publication → réponse
salarié.

Voir docs/superpowers/specs/2026-07-22-import-participations-saisies-existantes-design.md.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.database import supabase
from app.modules.participation.domain.import_reconstruction import (
    reconstruct_bulletins_from_inputs,
)
from app.modules.participation.infrastructure.campaign_repository import (
    campaign_repository,
)


@dataclass(frozen=True)
class ImportResult:
    campaign_id: Optional[str]
    bulletins: int
    full_cash: int
    partial_cash: int
    full_pee: int
    linked_inputs: int
    skipped: bool
    dry_run: bool
    detail: str


def _fetch_company_monthly_inputs(
    company_id: str, payroll_year: int, payroll_month: int
) -> List[Dict[str, Any]]:
    result = (
        supabase.table("monthly_inputs")
        .select("id, employee_id, name, amount")
        .eq("company_id", company_id)
        .eq("year", payroll_year)
        .eq("month", payroll_month)
        .execute()
    )
    return list(result.data or [])


def _unlink_monthly_inputs(campaign_id: str) -> None:
    supabase.table("monthly_inputs").update(
        {"participation_campaign_id": None, "participation_bulletin_id": None}
    ).eq("participation_campaign_id", campaign_id).execute()


def delete_imported_campaign(campaign_id: str, company_id: str) -> None:
    """Supprime une campagne (cascade DB vers bulletins/avances) et délie les
    saisies mensuelles qui y étaient rattachées."""
    _unlink_monthly_inputs(campaign_id)
    campaign_repository.delete_campaign(campaign_id, company_id)


def import_campaign_from_inputs(
    company_id: str,
    year: int,
    payroll_year: int,
    payroll_month: int,
    *,
    created_by: Optional[str] = None,
    dry_run: bool = False,
    force: bool = False,
) -> ImportResult:
    """Reconstruit une campagne participation clôturée pour `year` depuis les
    saisies de paie `(payroll_year, payroll_month)` de `company_id`.

    Idempotent : si une campagne `(company_id, year)` avec bulletins existe
    déjà, elle est conservée (résultat `skipped=True`) sauf `force=True`. Un
    brouillon vide (sans bulletin) est toujours remplacé silencieusement.
    `dry_run=True` calcule et retourne le résultat sans rien écrire.
    """
    replaced_empty_draft = False
    for campaign in campaign_repository.list_campaigns(company_id, year):
        campaign_id = str(campaign["id"])
        counts = campaign_repository.count_bulletins_by_status(campaign_id)
        total_existing = sum(counts.values())
        if total_existing == 0:
            replaced_empty_draft = True
            if not dry_run:
                campaign_repository.delete_campaign(campaign_id, company_id)
            continue
        if not force:
            return ImportResult(
                campaign_id=campaign_id,
                bulletins=total_existing,
                full_cash=0,
                partial_cash=0,
                full_pee=0,
                linked_inputs=0,
                skipped=True,
                dry_run=dry_run,
                detail=(
                    f"Campagne {year} déjà importée ({total_existing} "
                    "bulletin(s)) — utilisez force=true pour la remplacer."
                ),
            )
        if not dry_run:
            delete_imported_campaign(campaign_id, company_id)

    rows = _fetch_company_monthly_inputs(company_id, payroll_year, payroll_month)
    bulletins = reconstruct_bulletins_from_inputs(rows)
    if not bulletins:
        return ImportResult(
            campaign_id=None,
            bulletins=0,
            full_cash=0,
            partial_cash=0,
            full_pee=0,
            linked_inputs=0,
            skipped=False,
            dry_run=dry_run,
            detail="Aucune saisie participation trouvée pour cette période.",
        )

    counts_by_choice = Counter(b.choice_type for b in bulletins)
    suffix = " (remplace un brouillon vide existant)" if replaced_empty_draft else ""

    if dry_run:
        return ImportResult(
            campaign_id=None,
            bulletins=len(bulletins),
            full_cash=counts_by_choice.get("full_cash", 0),
            partial_cash=counts_by_choice.get("partial_cash", 0),
            full_pee=counts_by_choice.get("full_pee", 0),
            linked_inputs=sum(len(b.source_input_ids) for b in bulletins),
            skipped=False,
            dry_run=True,
            detail=f"Aperçu : {len(bulletins)} bulletin(s) seraient créés{suffix}.",
        )

    campaign = campaign_repository.create_campaign(
        {
            "company_id": company_id,
            "simulation_id": None,
            "year": year,
            "exercise_label": f"PARTICIPATION {year}",
            "status": "closed",
            "payroll_year": payroll_year,
            "payroll_month": payroll_month,
            "created_by": created_by,
        }
    )
    campaign_id = str(campaign["id"])

    advances = [
        {
            "employee_id": b.employee_id,
            "amount": float(b.advance_amount),
            "label": b.advance_label,
        }
        for b in bulletins
        if b.advance_amount > 0
    ]
    campaign_repository.upsert_advances(campaign_id, advances)

    now = datetime.now(timezone.utc).isoformat()
    bulletin_rows = [
        {
            "campaign_id": campaign_id,
            "company_id": company_id,
            "employee_id": b.employee_id,
            "dispositif_type": b.dispositif_type,
            "gross_amount": float(b.gross_amount),
            "csg_non_deductible": float(b.csg_non_deductible),
            "csg_deductible": float(b.csg_deductible),
            "advance_amount": float(b.advance_amount),
            "advance_label": b.advance_label,
            "net_amount": float(b.net_amount),
            "status": "responded",
            "choice_type": b.choice_type,
            "choice_cash_amount": float(b.cash_amount)
            if b.choice_type == "partial_cash"
            else None,
            "pee_amount": float(b.pee_amount),
            "cash_amount": float(b.cash_amount),
            "responded_at": now,
        }
        for b in bulletins
    ]
    created_rows = campaign_repository.insert_bulletins(bulletin_rows)
    bulletin_id_by_employee = {
        str(row["employee_id"]): str(row["id"]) for row in created_rows
    }

    linked = 0
    for b in bulletins:
        bulletin_id = bulletin_id_by_employee.get(b.employee_id)
        if not bulletin_id or not b.source_input_ids:
            continue
        supabase.table("monthly_inputs").update(
            {
                "participation_campaign_id": campaign_id,
                "participation_bulletin_id": bulletin_id,
            }
        ).in_("id", b.source_input_ids).execute()
        linked += len(b.source_input_ids)

    return ImportResult(
        campaign_id=campaign_id,
        bulletins=len(bulletins),
        full_cash=counts_by_choice.get("full_cash", 0),
        partial_cash=counts_by_choice.get("partial_cash", 0),
        full_pee=counts_by_choice.get("full_pee", 0),
        linked_inputs=linked,
        skipped=False,
        dry_run=False,
        detail=(
            f"{len(bulletins)} bulletin(s) importé(s), {linked} saisie(s) "
            f"rattachée(s){suffix}."
        ),
    )
