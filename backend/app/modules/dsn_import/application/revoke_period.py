"""Révocation d'un import DSN mensuel (sans réimporter)."""

from __future__ import annotations

import re
from typing import Any, Dict

from app.core.logging import get_logger
from app.modules.dsn_import.application.coverage import compute_coverage
from app.modules.dsn_import.application.cumuls import delete_cumuls_file
from app.modules.dsn_import.infrastructure import payroll_totals_repository as totals_repo
from app.modules.dsn_import.infrastructure import repository as repo

logger = get_logger("modules.dsn_import.revoke_period")

_PERIOD_RE = re.compile(r"^\d{4}-\d{2}$")


def revoke_period_import(
    company_id: str,
    period: str,
    *,
    revoked_by: str | None = None,
) -> Dict[str, Any]:
    """
    Retire une période de la couverture DSN et supprime les cumuls du mois
    pour tous les salariés de l'entreprise. Les fiches salariés ne sont pas touchées.
    """
    period = (period or "").strip()
    if not _PERIOD_RE.match(period):
        raise ValueError("Période invalide (attendu YYYY-MM).")

    company = repo.find_company_by_id(company_id)
    if not company:
        raise LookupError("Entreprise introuvable")

    batches = repo.list_committed_batches(limit=500)
    revoked = repo.list_revoked_periods(company_id)
    coverage = compute_coverage(company, batches=batches, revoked_periods=revoked)
    if period not in set(coverage.get("months_covered") or []):
        raise ValueError(f"La période {period} n'est pas couverte par un import DSN.")

    try:
        month = int(period.split("-", 1)[1])
    except (IndexError, ValueError) as exc:
        raise ValueError("Période invalide (attendu YYYY-MM).") from exc
    if month < 1 or month > 12:
        raise ValueError("Période invalide (mois hors plage).")

    repo.upsert_period_revocation(company_id, period, revoked_by=revoked_by)
    totals_repo.delete_period(company_id, period)

    cumuls_deleted = 0
    for emp in repo.list_employees_with_folder(company_id):
        folder = emp.get("employee_folder_name")
        if folder and delete_cumuls_file(str(folder), month):
            cumuls_deleted += 1

    logger.info(
        "Import DSN révoqué company=%s period=%s cumuls_deleted=%s",
        company_id,
        period,
        cumuls_deleted,
    )
    return {
        "company_id": company_id,
        "period": period,
        "cumuls_deleted": cumuls_deleted,
    }
