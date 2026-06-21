"""Service async pour jobs d'extraction de relevés de pointages."""

from __future__ import annotations

import hashlib
import logging
from datetime import date as date_type, datetime, timezone
from typing import Any, List

from app.core.database import get_supabase_admin_client
from app.modules.schedules.application.exceptions import ScheduleAppError
from app.modules.schedules.application.schedule_import_audit import record_schedule_import_run
from app.modules.schedules.application.timesheet_extract_config import timesheet_extract_mode
from app.modules.schedules.application.timesheet_import.batch_service import (
    create_batch_from_proposal,
    proposal_to_items,
)
from app.modules.schedules.infrastructure.schedule_import_storage import (
    upload_schedule_import_file,
)
from app.modules.schedules.schemas.ai import AiCalendarProposalResponse, RosterEmployee

logger = logging.getLogger(__name__)


def _db():
    return get_supabase_admin_client()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _update_job(job_id: str, payload: dict[str, Any]) -> None:
    payload = {**payload, "updated_at": _now_iso()}
    _db().table("schedule_import_jobs").update(payload).eq("id", job_id).execute()


def cancel_active_import_jobs(company_id: str) -> list[str]:
    """Annule tous les jobs d'import en cours pour une entreprise."""
    active = (
        _db().table("schedule_import_jobs")
        .select("id")
        .eq("company_id", company_id)
        .in_("status", ["queued", "extracting"])
        .execute()
    )
    cancelled: list[str] = []
    for row in active.data or []:
        job_id = str(row["id"])
        cancel_import_job(job_id, company_id=company_id)
        cancelled.append(job_id)
    return cancelled


def _raise_if_job_cancelled(job_id: str) -> None:
    job = get_import_job(job_id)
    if job and job.get("status") == "cancelled":
        raise ScheduleAppError("cancelled", "Import annulé.", status_code=499)


def create_import_job(
    *,
    company_id: str,
    user_id: str | None,
    filename: str,
    file_content: bytes,
    request_json: dict[str, Any],
) -> dict[str, Any]:
    file_hash = hashlib.sha256(file_content).hexdigest()
    cancel_active_import_jobs(company_id)

    insert_payload = {
        "company_id": company_id,
        "user_id": user_id,
        "status": "queued",
        "filename": filename,
        "file_hash": file_hash,
        "request_json": request_json,
        "extraction_mode": timesheet_extract_mode(),
        "progress_json": {"phase": "queued", "pages_total": 0, "pages_done": 0},
    }
    result = _db().table("schedule_import_jobs").insert(insert_payload).execute()
    if not result.data:
        raise ScheduleAppError("error", "Impossible de créer le job d'import.", status_code=500)

    job = result.data[0]
    job_id = str(job["id"])

    storage_path: str | None = None
    try:
        storage_path = upload_schedule_import_file(
            file_content,
            "application/pdf" if filename.lower().endswith(".pdf") else "application/octet-stream",
            filename,
            company_id,
            job_id,
        )
        _update_job(job_id, {"file_storage_path": storage_path, "status": "extracting"})
    except Exception as exc:
        logger.warning("Stockage PDF import échoué (job %s): %s", job_id, exc)

    return {**job, "id": job_id, "file_storage_path": storage_path}


def get_import_job(job_id: str, *, company_id: str | None = None) -> dict[str, Any] | None:
    query = _db().table("schedule_import_jobs").select("*").eq("id", job_id)
    if company_id:
        query = query.eq("company_id", company_id)
    result = query.maybe_single().execute()
    return result.data


def cancel_import_job(job_id: str, *, company_id: str) -> bool:
    job = get_import_job(job_id, company_id=company_id)
    if not job:
        return False
    if job.get("status") in ("completed", "failed", "cancelled"):
        return True
    _update_job(job_id, {"status": "cancelled", "completed_at": _now_iso()})
    return True


def _merge_proposals(proposals: List[AiCalendarProposalResponse]) -> AiCalendarProposalResponse:
    if len(proposals) == 1:
        return proposals[0]
    base = proposals[-1]
    by_key: dict[str, Any] = {}
    warnings: set[str] = set()

    for p in proposals:
        for emp in p.employees:
            key = emp.time_tracking_id or emp.employee_id or emp.raw_name
            prev = by_key.get(key)
            if not prev:
                by_key[key] = emp.model_copy(deep=True)
                continue
            day_map = {d.jour: d for d in prev.days}
            for d in emp.days:
                day_map[d.jour] = d
            prev.days = sorted(day_map.values(), key=lambda x: x.jour)
            prev.warnings = list(set(prev.warnings + emp.warnings))
            by_key[key] = prev
        warnings.update(p.warnings)

    merged = base.model_copy(
        update={
            "employees": list(by_key.values()),
            "warnings": list(warnings),
            "source": f"{len(proposals)} relevé(s) fusionné(s)",
        }
    )
    return merged


def run_timesheet_extraction_job(job_id: str, file_content: bytes) -> None:
    """Exécuté en BackgroundTasks après POST /extract-timesheet/start."""
    job = get_import_job(job_id)
    if not job:
        logger.error("Job import introuvable: %s", job_id)
        return
    if job.get("status") == "cancelled":
        return

    request = job.get("request_json") or {}
    company_id = str(job.get("company_id") or "")
    user_id = job.get("user_id")
    filename = str(job.get("filename") or "document.pdf")

    def on_progress(progress: dict[str, Any]) -> None:
        _raise_if_job_cancelled(job_id)
        _update_job(job_id, {"progress_json": progress, "status": "extracting"})

    try:
        roster = [RosterEmployee(**item) for item in request.get("employees") or []]
        week_anchor = request.get("week_anchor_date")
        parsed_anchor = None
        if week_anchor:
            try:
                parsed_anchor = date_type.fromisoformat(str(week_anchor))
            except ValueError:
                parsed_anchor = None

        from app.modules.schedules.application import ai_fill

        proposal = ai_fill.extract_timesheet(
            year=int(request.get("year")),
            month=int(request.get("month")),
            file_content=file_content,
            filename=filename,
            roster=roster,
            single_employee=bool(request.get("single_employee")),
            document_scope=str(request.get("document_scope") or "auto"),
            week_anchor_date=parsed_anchor,
            company_id=company_id,
            user_id=str(user_id) if user_id else None,
            import_job_id=job_id,
            on_progress=on_progress,
            skip_audit=True,
        )

        from app.modules.schedules.application.timesheet_import.registry import (
            detect_source_type,
        )

        batch = create_batch_from_proposal(
            company_id=company_id,
            user_id=str(user_id) if user_id else None,
            proposal=proposal,
            source_type=detect_source_type(filename),
            parser_key=proposal.detected_format or proposal.extraction_mode or "hybrid",
            filename=filename,
            file_hash=job.get("file_hash"),
            file_storage_path=job.get("file_storage_path"),
            import_job_id=job_id,
            file_content=file_content,
        )
        batch_id = str(batch["id"])

        record_schedule_import_run(
            company_id=company_id,
            user_id=str(user_id) if user_id else None,
            filename=filename,
            proposal=proposal,
            file_content=file_content,
            import_job_id=job_id,
            batch_id=batch_id,
            extraction_mode=proposal.extraction_mode,
            page_count=proposal.extraction_pages_processed,
            consensus_conflicts=proposal.consensus_conflicts,
        )

        _update_job(
            job_id,
            {
                "status": "completed",
                "proposal_json": proposal.model_dump(mode="json"),
                "page_audit_json": None,
                "completed_at": _now_iso(),
                "progress_json": {
                    "phase": "completed",
                    "pages_total": proposal.extraction_pages_total or 0,
                    "pages_done": proposal.extraction_pages_processed or 0,
                    "batch_id": batch_id,
                },
            },
        )
    except ScheduleAppError as exc:
        if exc.code == "cancelled":
            return
        _update_job(
            job_id,
            {
                "status": "failed",
                "error_message": exc.message,
                "completed_at": _now_iso(),
            },
        )
    except Exception as exc:
        logger.exception("Job import %s échoué", job_id)
        _update_job(
            job_id,
            {
                "status": "failed",
                "error_message": str(exc) or "Erreur inattendue lors de l'extraction.",
                "completed_at": _now_iso(),
            },
        )


def run_multi_timesheet_extraction_job(
    job_id: str,
    files: List[tuple[str, bytes]],
) -> None:
    """Fusionne plusieurs fichiers en un batch unique."""
    job = get_import_job(job_id)
    if not job or job.get("status") == "cancelled":
        return

    request = job.get("request_json") or {}
    company_id = str(job.get("company_id") or "")
    user_id = job.get("user_id")
    roster = [RosterEmployee(**item) for item in request.get("employees") or []]
    year, month = int(request.get("year")), int(request.get("month"))

    proposals: List[AiCalendarProposalResponse] = []
    batch_ids: List[str] = []
    try:
        for i, (filename, content) in enumerate(files):
            _raise_if_job_cancelled(job_id)
            _update_job(
                job_id,
                {
                    "progress_json": {
                        "phase": "extracting",
                        "files_total": len(files),
                        "files_done": i,
                        "current_file": filename,
                    },
                },
            )
            proposal, batch_id = parse_with_llm_fallback(
                company_id=company_id,
                user_id=str(user_id) if user_id else None,
                content=content,
                filename=filename,
                year=year,
                month=month,
                roster=roster,
                single_employee=bool(request.get("single_employee")),
                document_scope=str(request.get("document_scope") or "auto"),
                import_job_id=job_id,
            )
            proposals.append(proposal)
            batch_ids.append(batch_id)

        merged = _merge_proposals(proposals)
        master_batch = create_batch_from_proposal(
            company_id=company_id,
            user_id=str(user_id) if user_id else None,
            proposal=merged,
            source_type="document_pdf",
            parser_key="multi_file_merge",
            filename=f"{len(files)} fichiers",
            import_job_id=job_id,
        )
        master_id = str(master_batch["id"])

        _update_job(
            job_id,
            {
                "status": "completed",
                "proposal_json": merged.model_dump(mode="json"),
                "completed_at": _now_iso(),
                "progress_json": {
                    "phase": "completed",
                    "files_total": len(files),
                    "files_done": len(files),
                    "batch_id": master_id,
                    "source_batch_ids": batch_ids,
                },
            },
        )
    except ScheduleAppError as exc:
        if exc.code == "cancelled":
            return
        _update_job(
            job_id,
            {
                "status": "failed",
                "error_message": exc.message,
                "completed_at": _now_iso(),
            },
        )
    except Exception as exc:
        logger.exception("Job multi-import %s échoué", job_id)
        _update_job(
            job_id,
            {
                "status": "failed",
                "error_message": str(exc),
                "completed_at": _now_iso(),
            },
        )


__all__ = [
    "cancel_active_import_jobs",
    "cancel_import_job",
    "create_import_job",
    "get_import_job",
    "run_multi_timesheet_extraction_job",
    "run_timesheet_extraction_job",
]
