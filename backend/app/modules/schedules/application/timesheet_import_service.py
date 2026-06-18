"""Service async pour jobs d'extraction de relevés de pointages."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

from app.core.database import get_supabase_admin_client
from app.modules.schedules.application import ai_fill
from app.modules.schedules.application.exceptions import ScheduleAppError
from app.modules.schedules.application.timesheet_extract_config import (
    timesheet_extract_mode,
)
from app.modules.schedules.infrastructure.schedule_import_storage import (
    upload_schedule_import_file,
)

logger = logging.getLogger(__name__)

_JOB_TIMEOUT_MINUTES = 10


def _db():
    return get_supabase_admin_client()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _update_job(job_id: str, payload: dict[str, Any]) -> None:
    payload = {**payload, "updated_at": _now_iso()}
    _db().table("schedule_import_jobs").update(payload).eq("id", job_id).execute()


def create_import_job(
    *,
    company_id: str,
    user_id: str | None,
    filename: str,
    file_content: bytes,
    request_json: dict[str, Any],
) -> dict[str, Any]:
    file_hash = hashlib.sha256(file_content).hexdigest()
    active = (
        _db().table("schedule_import_jobs")
        .select("id")
        .eq("company_id", company_id)
        .in_("status", ["queued", "extracting"])
        .limit(1)
        .execute()
    )
    if active.data:
        raise ScheduleAppError(
            "validation",
            "Un import de pointages est déjà en cours pour cette entreprise.",
            status_code=409,
        )

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
        _update_job(job_id, {"progress_json": progress, "status": "extracting"})

    try:
        from app.modules.schedules.schemas.ai import RosterEmployee

        roster = [RosterEmployee(**item) for item in request.get("employees") or []]
        week_anchor = request.get("week_anchor_date")
        parsed_anchor = None
        if week_anchor:
            from datetime import date as date_type

            try:
                parsed_anchor = date_type.fromisoformat(str(week_anchor))
            except ValueError:
                parsed_anchor = None

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
            skip_audit=False,
        )

        page_audit = None
        _update_job(
            job_id,
            {
                "status": "completed",
                "proposal_json": proposal.model_dump(mode="json"),
                "page_audit_json": page_audit,
                "completed_at": _now_iso(),
                "progress_json": {
                    "phase": "completed",
                    "pages_total": proposal.extraction_pages_total or 0,
                    "pages_done": proposal.extraction_pages_processed or 0,
                },
            },
        )
    except ScheduleAppError as exc:
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


__all__ = [
    "cancel_import_job",
    "create_import_job",
    "get_import_job",
    "run_timesheet_extraction_job",
]
