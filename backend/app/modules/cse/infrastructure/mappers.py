# app/modules/cse/infrastructure/mappers.py
"""
Mappers CSE — ligne DB (dict) vers schémas de lecture.
"""
from typing import Any, Dict

from app.modules.cse.schemas import DelegationQuotaRead


def map_delegation_quota_row_to_read(row: Dict[str, Any]) -> DelegationQuotaRead:
    """Construit DelegationQuotaRead depuis une ligne cse_delegation_quotas (avec join catalog)."""
    cc = row.get("collective_agreements_catalog") or {}
    return DelegationQuotaRead(
        id=row["id"],
        company_id=row["company_id"],
        collective_agreement_id=row.get("collective_agreement_id"),
        quota_hours_per_month=float(row["quota_hours_per_month"]),
        notes=row.get("notes"),
        collective_agreement_name=cc.get("name"),
    )
