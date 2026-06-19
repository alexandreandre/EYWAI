"""Traçabilité des imports de pointages (audit paie)."""

from __future__ import annotations

import hashlib
import logging
import os
from typing import Any

from app.core.database import supabase
from app.modules.schedules.application.timesheet_quality import average_coverage
from app.modules.schedules.schemas.ai import AiCalendarProposalResponse

logger = logging.getLogger(__name__)

_OCR_DEBUG = os.getenv("TIMESHEET_OCR_DEBUG", "").strip() in ("1", "true", "yes")
_OCR_EXCERPT_MAX = 20_000


def record_schedule_import_run(
    *,
    company_id: str,
    user_id: str | None,
    filename: str,
    proposal: AiCalendarProposalResponse,
    file_content: bytes | None = None,
    extraction_method: str | None = None,
    raw_ocr_text: str | None = None,
    import_job_id: str | None = None,
    batch_id: str | None = None,
    extraction_mode: str | None = None,
    page_count: int | None = None,
    consensus_conflicts: int | None = None,
    days_written: int = 0,
) -> None:
    try:
        employees_matched = sum(
            1 for e in proposal.employees if e.employee_id and e.review_status != "error"
        )
        file_hash = None
        if file_content:
            file_hash = hashlib.sha256(file_content).hexdigest()

        raw_excerpt = None
        if _OCR_DEBUG and raw_ocr_text:
            raw_excerpt = raw_ocr_text[:_OCR_EXCERPT_MAX]

        coverage_avg = average_coverage(proposal.employees)

        payload: dict[str, Any] = {
            "company_id": company_id,
            "user_id": user_id,
            "filename": filename or "",
            "detected_format": proposal.detected_format or "unknown",
            "period_start": (
                proposal.detected_period_start.isoformat()
                if proposal.detected_period_start
                else None
            ),
            "period_end": (
                proposal.detected_period_end.isoformat()
                if proposal.detected_period_end
                else None
            ),
            "employees_matched": employees_matched,
            "days_written": days_written,
            "warnings_json": [c.model_dump() for c in proposal.quality_checks]
            + proposal.warnings,
            "proposal_json": proposal.model_dump(mode="json"),
            "extraction_method": extraction_method or proposal.extraction_method,
            "raw_ocr_excerpt": raw_excerpt,
            "file_hash": file_hash,
            "parse_confidence": proposal.parse_confidence,
            "coverage_avg": coverage_avg,
            "import_job_id": import_job_id,
            "batch_id": batch_id,
            "extraction_mode": extraction_mode,
            "page_count": page_count,
            "consensus_conflicts": consensus_conflicts,
        }
        supabase.table("schedule_import_runs").insert(payload).execute()
    except Exception:
        logger.exception("Échec enregistrement schedule_import_runs")


def update_import_run_days_written(run_id: str, days_written: int) -> None:
    try:
        supabase.table("schedule_import_runs").update(
            {"days_written": days_written}
        ).eq("id", run_id).execute()
    except Exception:
        logger.exception("Échec mise à jour schedule_import_runs")


__all__ = ["record_schedule_import_run", "update_import_run_days_written"]
