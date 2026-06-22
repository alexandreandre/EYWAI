"""Orchestration récupération décomptes IJSS Net-Entreprises."""

from __future__ import annotations

from typing import Any, Dict, List

from app.core.logging import get_logger
from app.modules.ijss_tracking.application import service as ijss_service
from app.modules.ijss_tracking.infrastructure import repository as ijss_repo
from app.modules.net_entreprises.application.service import resolve_connector
from app.modules.net_entreprises.infrastructure import repository as ne_repo

logger = get_logger("modules.net_entreprises.ij_decomptes")


def fetch_and_stage_ij_decomptes(
    *,
    company_id: str,
    period_id: str,
    period: str,
    user_id: str,
) -> Dict[str, Any]:
    """Appelle le connecteur NE et stage les lignes CPAM."""
    config = ne_repo.get_config(company_id)
    connector = resolve_connector(config)
    siret = (config or {}).get("siret_declarant") or ""

    company_row = None
    try:
        from app.core.database import get_supabase_admin_client

        resp = (
            get_supabase_admin_client()
            .table("companies")
            .select("siret")
            .eq("id", company_id)
            .limit(1)
            .execute()
        )
        if resp.data:
            company_row = resp.data[0]
    except Exception:
        logger.exception("Lecture SIRET entreprise")

    if not siret and company_row:
        siret = str(company_row.get("siret") or "")

    result = connector.fetch_ij_decomptes(
        config or {}, period=period, siret=siret
    )

    batch_id = ijss_repo.insert_batch(
        {
            "company_id": company_id,
            "period_id": period_id,
            "batch_type": "cpam_api_sync",
            "status": "parsed" if not result.success else "previewed",
            "summary": {"api_status": result.status, "message": result.message},
            "preview": {"lines": [line.__dict__ for line in result.lines]},
            "uploaded_by": user_id,
        }
    )

    if not result.success or not result.lines:
        return {
            "success": False,
            "status": result.status,
            "message": result.message,
            "batch_id": batch_id,
            "fallback": "import_manual",
        }

    items: List[Dict[str, Any]] = []
    employees = ijss_service._fetch_employees(company_id)
    expected = ijss_repo.list_expected_lines(period_id)

    from app.modules.ijss_tracking.domain.reconciliation import match_received_to_employee

    for i, line in enumerate(result.lines):
        match = match_received_to_employee(
            employee_name_raw=line.employee_name or "",
            employee_nir=line.employee_nir,
            amount=line.amount,
            employees=employees,
            expected_lines=expected,
        )
        mapped = {
            "amount": line.amount,
            "payment_date": line.payment_date,
            "employee_nir": line.employee_nir,
            "employee_name_raw": line.employee_name,
            "period_start": line.period_start,
            "period_end": line.period_end,
            "source": "cpam_decompte",
        }
        items.append(
            {
                "batch_id": batch_id,
                "row_index": i,
                "raw_payload": mapped,
                "mapped_payload": mapped,
                "match_status": "matched" if match else "unmatched",
                "employee_id": match.employee_id if match else None,
                "anomalies": [],
            }
        )
    ijss_repo.insert_import_items(items)

    if batch_id:
        ijss_service.commit_import_batch(company_id, batch_id)

    return {
        "success": True,
        "status": "success",
        "message": f"{len(result.lines)} ligne(s) CPAM synchronisée(s).",
        "batch_id": batch_id,
        "line_count": len(result.lines),
    }
