"""Réinitialisation onboarding entreprise après purge des salariés."""

from __future__ import annotations

from typing import Any, Dict, List

from app.core.database import get_supabase_admin_client
from app.core.logging import get_logger
from app.modules.dsn_import.application.coverage import compute_coverage
from app.modules.dsn_import.infrastructure import repository as dsn_repo

logger = get_logger("modules.employees.company_onboarding_reset")


def reset_company_onboarding_after_employee_purge(
    company_id: str,
    *,
    revoked_by: str | None = None,
) -> Dict[str, Any]:
    """
    Après suppression de tous les salariés :
    - révoque les périodes DSN couvertes (matrice + parcours guidé)
    - supprime plannings et soldes CP orphelins au niveau entreprise
    """
    company = dsn_repo.find_company_by_id(company_id)
    if not company:
        raise LookupError("Entreprise introuvable")

    batches = dsn_repo.list_committed_batches(limit=500)
    already_revoked = set(dsn_repo.list_revoked_periods(company_id))
    coverage = compute_coverage(
        company,
        batches=batches,
        revoked_periods=list(already_revoked),
    )
    months_covered = sorted(set(coverage.get("months_covered") or []))

    revoked: List[str] = []
    for period in months_covered:
        if period in already_revoked:
            continue
        dsn_repo.upsert_period_revocation(company_id, period, revoked_by=revoked_by)
        revoked.append(period)

    client = get_supabase_admin_client()
    schedules_resp = (
        client.table("employee_schedules").delete().eq("company_id", company_id).execute()
    )
    cp_resp = (
        client.table("employee_leave_adjustments")
        .delete()
        .eq("company_id", company_id)
        .execute()
    )

    schedules_deleted = len(schedules_resp.data or [])
    cp_adjustments_deleted = len(cp_resp.data or [])

    logger.info(
        "Onboarding reset company=%s revoked=%s schedules=%s cp_adjustments=%s",
        company_id,
        len(revoked),
        schedules_deleted,
        cp_adjustments_deleted,
    )

    return {
        "company_id": company_id,
        "revoked_periods": revoked,
        "schedules_deleted": schedules_deleted,
        "cp_adjustments_deleted": cp_adjustments_deleted,
    }
