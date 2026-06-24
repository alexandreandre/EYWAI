"""Création batch staging et items depuis une proposition."""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List

from app.modules.schedules.application.timesheet_quality import average_coverage
from app.modules.schedules.infrastructure.timesheet_import_repository import (
    timesheet_import_repository,
)
from app.modules.schedules.schemas.ai import AiCalendarProposalResponse, AiEmployeeProposal


def proposal_to_items(
    batch_id: str,
    proposal: AiCalendarProposalResponse,
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    row_index = 0
    for emp in proposal.employees:
        for day in emp.days:
            match_status = "skipped"
            if emp.review_status == "empty":
                match_status = "skipped"
            elif emp.employee_id:
                match_status = "ambiguous" if emp.review_status == "warning" else "matched"
            elif emp.review_status == "error":
                match_status = "unmatched"

            items.append(
                {
                    "batch_id": batch_id,
                    "row_index": row_index,
                    "employee_id": emp.employee_id,
                    "time_tracking_id": emp.time_tracking_id,
                    "raw_name": emp.raw_name,
                    "jour": day.jour,
                    "heures": day.heures,
                    "type": day.type,
                    "nature": day.nature,
                    "match_status": match_status,
                    "match_method": emp.match_method,
                    "match_confidence": emp.match_confidence,
                    "anomalies": emp.warnings,
                    "raw_payload": {},
                }
            )
            row_index += 1
    return items


def _batch_summary(proposal: AiCalendarProposalResponse) -> Dict[str, Any]:
    employees_matched = sum(
        1 for e in proposal.employees if e.employee_id and e.review_status != "error"
    )
    days_total = sum(len(e.days) for e in proposal.employees)
    return {
        "employees_total": len(proposal.employees),
        "employees_matched": employees_matched,
        "days_total": days_total,
        "coverage_avg": average_coverage(proposal.employees),
        "tokens_used": 0,
    }


def create_batch_from_proposal(
    *,
    company_id: str,
    user_id: str | None,
    proposal: AiCalendarProposalResponse,
    source_type: str,
    parser_key: str | None,
    filename: str | None = None,
    file_hash: str | None = None,
    file_storage_path: str | None = None,
    import_job_id: str | None = None,
    file_content: bytes | None = None,
    extra_summary: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    if file_content and not file_hash:
        file_hash = hashlib.sha256(file_content).hexdigest()

    summary = _batch_summary(proposal)
    if extra_summary:
        summary = {**summary, **extra_summary}

    batch = timesheet_import_repository.insert_batch(
        {
            "company_id": company_id,
            "user_id": user_id,
            "status": "previewed",
            "source_type": source_type,
            "parser_key": parser_key,
            "filename": filename,
            "file_hash": file_hash,
            "file_storage_path": file_storage_path,
            "period_year": proposal.year,
            "period_month": proposal.month,
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
            "preview_json": proposal.model_dump(mode="json"),
            "summary_json": summary,
            "import_job_id": import_job_id,
        }
    )
    batch_id = str(batch["id"])
    items = proposal_to_items(batch_id, proposal)
    timesheet_import_repository.insert_items(items)
    return batch


def update_batch_preview(
    batch_id: str,
    proposal: AiCalendarProposalResponse,
) -> Dict[str, Any]:
    timesheet_import_repository.delete_items(batch_id)
    items = proposal_to_items(batch_id, proposal)
    timesheet_import_repository.insert_items(items)
    return timesheet_import_repository.update_batch(
        batch_id,
        {
            "status": "previewed",
            "preview_json": proposal.model_dump(mode="json"),
            "summary_json": _batch_summary(proposal),
            "period_year": proposal.year,
            "period_month": proposal.month,
        },
    )


def employees_from_proposal(proposal: AiCalendarProposalResponse) -> List[AiEmployeeProposal]:
    return list(proposal.employees)


__all__ = [
    "create_batch_from_proposal",
    "proposal_to_items",
    "update_batch_preview",
]
