"""Déduplication et cache preview par file_hash."""

from __future__ import annotations

from typing import Optional

from app.core.database import get_supabase_admin_client
from app.modules.schedules.application.exceptions import ScheduleAppError
from app.modules.schedules.infrastructure.timesheet_import_repository import (
    timesheet_import_repository,
)
from app.modules.schedules.schemas.ai import AiCalendarProposalResponse


def check_file_hash_committed(company_id: str, file_hash: str) -> Optional[str]:
    if not file_hash:
        return None
    if not timesheet_import_repository.batch_exists_by_hash_committed(company_id, file_hash):
        return None
    row = (
        get_supabase_admin_client()
        .table("schedule_import_batches")
        .select("id")
        .eq("company_id", company_id)
        .eq("file_hash", file_hash)
        .eq("status", "committed")
        .limit(1)
        .execute()
    )
    if row.data:
        return str(row.data[0]["id"])
    return None


def assert_not_committed_duplicate(company_id: str, file_hash: str) -> None:
    if check_file_hash_committed(company_id, file_hash):
        raise ScheduleAppError(
            "validation",
            "Ce fichier a déjà été importé (hash identique).",
            status_code=409,
        )


def find_cached_preview(
    company_id: str,
    file_hash: str,
    *,
    year: int,
    month: int,
) -> Optional[AiCalendarProposalResponse]:
    row = timesheet_import_repository.find_recent_preview_by_hash(
        company_id,
        file_hash,
        period_year=year,
        period_month=month,
    )
    if not row or not row.get("preview_json"):
        return None
    return AiCalendarProposalResponse.model_validate(row["preview_json"])


__all__ = [
    "assert_not_committed_duplicate",
    "check_file_hash_committed",
    "find_cached_preview",
]
