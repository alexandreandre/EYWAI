"""Orchestration parse synchrone (CSV/XLSX/PDF déterministe)."""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional

from app.modules.schedules.application.ai_fill import extract_timesheet
from app.modules.schedules.application.exceptions import ScheduleAppError
from app.modules.schedules.application.roster_enrichment import enrich_roster_time_tracking_ids
from app.modules.schedules.application.timesheet_import.batch_service import (
    create_batch_from_proposal,
)
from app.modules.schedules.application.timesheet_import.cache_service import (
    assert_not_committed_duplicate,
    find_cached_preview,
)
from app.modules.schedules.application.timesheet_import.proposal_builder import (
    build_proposal_from_attempt,
)
from app.modules.schedules.application.timesheet_import.registry import (
    detect_source_type,
    parse_document,
)
from app.modules.schedules.application.timesheet_import.tabular_period import (
    ImportPeriodConfig,
    apply_import_period_to_rows,
    collect_dates_from_proposal,
    collect_dates_from_rows,
    finalize_tabular_proposal,
)
from app.modules.schedules.application.timesheet_import.structured_parser import (
    read_tabular_preview_with_status,
)
from app.modules.schedules.infrastructure.schedule_import_storage import (
    upload_schedule_import_file,
)
from app.modules.schedules.infrastructure.timesheet_import_repository import (
    timesheet_import_repository,
)
from app.modules.schedules.schemas.ai import AiCalendarProposalResponse, RosterEmployee
from app.modules.schedules.schemas.timesheet_import import (
    ColumnDetectionResponse,
    TimesheetImportParseResponse,
)


def detect_columns(
    content: bytes,
    filename: str,
    *,
    options: Optional[Dict[str, Any]] = None,
) -> ColumnDetectionResponse:
    headers, sample_rows, mapping, mapping_complete = read_tabular_preview_with_status(
        content, filename, options=options
    )
    source = detect_source_type(filename)
    serializable_rows = [
        {k: (str(v) if v is not None else None) for k, v in row.items()}
        for row in sample_rows
    ]
    return ColumnDetectionResponse(
        headers=headers,
        sample_rows=serializable_rows,
        suggested_mapping=mapping,
        mapping_complete=mapping_complete,
        source_type=source if source in ("csv", "xlsx") else "csv",
    )


def parse_structured_file(
    *,
    company_id: str,
    user_id: str | None,
    content: bytes,
    filename: str,
    year: int,
    month: int,
    roster: List[RosterEmployee],
    column_mapping: Optional[Dict[str, str]] = None,
    options: Optional[Dict[str, Any]] = None,
    profile_name: str | None = None,
    period_config: ImportPeriodConfig | None = None,
    allow_reimport: bool = False,
) -> TimesheetImportParseResponse:
    period_config = period_config or ImportPeriodConfig(
        mode="month", year=year, month=month
    )
    file_hash = hashlib.sha256(content).hexdigest()
    if not allow_reimport:
        assert_not_committed_duplicate(company_id, file_hash)

    cached = find_cached_preview(company_id, file_hash, year=year, month=month)
    source_type = detect_source_type(filename)
    if cached and source_type in ("csv", "xlsx"):
        roster = enrich_roster_time_tracking_ids(roster, company_id)
        dates = collect_dates_from_proposal(cached)
        parser_key = cached.detected_format or "tabular_generic"
        cached = finalize_tabular_proposal(
            cached,
            dates=dates,
            requested_year=year,
            requested_month=month,
            roster=roster,
            company_id=company_id,
            parser_key=parser_key,
            parse_confidence=cached.parse_confidence,
            extraction_warnings=cached.extraction_warnings,
        )
        batch = create_batch_from_proposal(
            company_id=company_id,
            user_id=user_id,
            proposal=cached,
            source_type=source_type,
            parser_key=parser_key,
            filename=filename,
            file_hash=file_hash,
            file_content=content,
        )
        return TimesheetImportParseResponse(
            batch_id=str(batch["id"]),
            preview=cached,
            parser_key=parser_key,
            file_hash=file_hash,
        )

    if profile_name:
        prof = timesheet_import_repository.get_profile(
            company_id, profile_name, source_type
        )
        if prof:
            column_mapping = column_mapping or prof.get("column_mapping") or {}
            options = {**(prof.get("options") or {}), **(options or {})}

    roster = enrich_roster_time_tracking_ids(roster, company_id)
    parse_options = {**(options or {}), "skip_period_filter": True}
    attempt = parse_document(
        content,
        filename,
        company_id=company_id,
        year=year,
        month=month,
        column_mapping=column_mapping,
        options=parse_options,
        skip_llm=True,
    )

    parsed = attempt.parse_result
    month_groups: List[Dict[str, Any]] | None = None
    period_resolution = None
    full_period_rows = None
    if (
        attempt.parser_key in ("tabular_generic", "tabular_punch_pairs")
        and parsed is not None
    ):
        rows_before = list(parsed.rows)
        period_resolution = apply_import_period_to_rows(parsed.rows, config=period_config)
        full_period_rows = list(period_resolution.rows)
        parsed.rows = full_period_rows
        if not parsed.rows:
            from app.modules.schedules.application.timesheet_import.tabular_period import (
                period_filter_empty_message,
            )

            raise ScheduleAppError(
                "validation",
                period_filter_empty_message(rows_before=rows_before, config=period_config),
                status_code=422,
            )
        year, month = period_resolution.year, period_resolution.month

        from app.modules.schedules.application.timesheet_import.multi_month import (
            build_month_groups_from_rows,
            unique_months_in_rows,
        )

        months_in_file = unique_months_in_rows(full_period_rows)
        is_multi = period_config.mode != "month" or len(months_in_file) > 1
        if is_multi:
            month_groups = build_month_groups_from_rows(full_period_rows, roster)
            anchor_rows = [
                r for r in full_period_rows if r.year == year and r.month == month
            ]
            from dataclasses import replace

            parsed = replace(parsed, rows=anchor_rows or full_period_rows)
        attempt.parse_result = parsed

    proposal = build_proposal_from_attempt(
        attempt, year=year, month=month, roster=roster
    )
    if proposal is None:
        raise ScheduleAppError(
            "validation",
            "Impossible d'extraire les pointages de ce fichier.",
            status_code=422,
        )

    if (
        attempt.parser_key in ("tabular_generic", "tabular_punch_pairs")
        and parsed is not None
        and period_resolution is not None
    ):
        dates = (
            collect_dates_from_rows(full_period_rows or [])
            if month_groups
            else collect_dates_from_proposal(proposal)
        )
        proposal = finalize_tabular_proposal(
            proposal,
            dates=dates,
            requested_year=period_resolution.requested_year,
            requested_month=period_resolution.requested_month,
            roster=roster,
            company_id=company_id,
            parser_key=attempt.parser_key,
            parse_confidence=attempt.confidence,
            extraction_warnings=attempt.warnings,
        )
        if month_groups:
            from app.modules.schedules.schemas.ai import AffectedMonth

            proposal = proposal.model_copy(
                update={
                    "affected_months": [
                        AffectedMonth(
                            year=g["year"],
                            month=g["month"],
                            days=sorted(
                                {
                                    d["jour"]
                                    for emp in g["employees"]
                                    for d in emp["days"]
                                }
                            ),
                        )
                        for g in month_groups
                    ],
                }
            )
    else:
        from calendar import monthrange
        from datetime import date

        from app.modules.schedules.application.ai_fill import _finalize_timesheet_proposal
        from app.modules.schedules.application.timesheet_period import (
            TimesheetPeriodDetection,
        )

        last_day = monthrange(year, month)[1]
        period_detection = TimesheetPeriodDetection(
            scope="monthly",
            start_date=date(year, month, 1),
            end_date=date(year, month, last_day),
            confidence="high",
        )
        proposal = _finalize_timesheet_proposal(
            proposal,
            roster=roster,
            company_id=company_id,
            period_detection=period_detection,
            detected_format=attempt.parser_key,
            parse_confidence=attempt.confidence,
            extraction_method=attempt.extraction_method or "structured",
            extraction_warnings=attempt.warnings,
        )

    storage_path = None
    try:
        storage_path = upload_schedule_import_file(
            content,
            "application/octet-stream",
            filename,
            company_id,
            file_hash[:12],
        )
    except Exception:
        pass

    extra_summary: Dict[str, Any] | None = None
    if month_groups:
        extra_summary = {
            "multi_month": True,
            "period_mode": period_config.mode,
            "month_groups": month_groups,
            "months_count": len(month_groups),
        }

    batch = create_batch_from_proposal(
        company_id=company_id,
        user_id=user_id,
        proposal=proposal,
        source_type=source_type,
        parser_key=attempt.parser_key,
        filename=filename,
        file_hash=file_hash,
        file_storage_path=storage_path,
        file_content=content,
        extra_summary=extra_summary,
    )

    if column_mapping and source_type in ("csv", "xlsx"):
        timesheet_import_repository.upsert_profile(
            company_id,
            {
                "profile_name": profile_name or "default",
                "source_type": source_type,
                "parser_key": "tabular_generic",
                "column_mapping": column_mapping,
                "options": options or {},
            },
        )

    return TimesheetImportParseResponse(
        batch_id=str(batch["id"]),
        preview=proposal,
        parser_key=attempt.parser_key,
        file_hash=file_hash,
    )


def parse_with_llm_fallback(
    *,
    company_id: str,
    user_id: str | None,
    content: bytes,
    filename: str,
    year: int,
    month: int,
    roster: List[RosterEmployee],
    single_employee: bool = False,
    document_scope: str = "auto",
    week_anchor_date=None,
    import_job_id: str | None = None,
) -> tuple[AiCalendarProposalResponse, str]:
    file_hash = hashlib.sha256(content).hexdigest()
    cached = find_cached_preview(company_id, file_hash, year=year, month=month)
    if cached:
        batch = create_batch_from_proposal(
            company_id=company_id,
            user_id=user_id,
            proposal=cached,
            source_type=detect_source_type(filename),
            parser_key=cached.detected_format or "cache_preview",
            filename=filename,
            file_hash=file_hash,
            import_job_id=import_job_id,
            file_content=content,
        )
        return cached, str(batch["id"])

    roster = enrich_roster_time_tracking_ids(roster, company_id)
    proposal = extract_timesheet(
        year=year,
        month=month,
        file_content=content,
        filename=filename,
        roster=roster,
        single_employee=single_employee,
        document_scope=document_scope,
        week_anchor_date=week_anchor_date,
        company_id=company_id,
        user_id=user_id,
        import_job_id=import_job_id,
        skip_audit=True,
    )
    batch = create_batch_from_proposal(
        company_id=company_id,
        user_id=user_id,
        proposal=proposal,
        source_type=detect_source_type(filename),
        parser_key=proposal.detected_format or proposal.extraction_mode or "hybrid",
        filename=filename,
        file_hash=file_hash,
        import_job_id=import_job_id,
        file_content=content,
    )
    return proposal, str(batch["id"])


def list_import_profiles(company_id: str) -> List[Dict[str, Any]]:
    return timesheet_import_repository.list_profiles(company_id)


def save_import_profile(
    company_id: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    return timesheet_import_repository.upsert_profile(company_id, payload)


def get_batch_response(batch_id: str, *, company_id: str) -> Dict[str, Any]:
    batch = timesheet_import_repository.get_batch(batch_id, company_id=company_id)
    if not batch:
        raise ScheduleAppError("validation", "Batch introuvable.", status_code=404)
    preview = None
    if batch.get("preview_json"):
        preview = AiCalendarProposalResponse.model_validate(batch["preview_json"])
    return {
        "batch_id": batch_id,
        "status": batch.get("status"),
        "preview": preview,
        "summary": batch.get("summary_json") or {},
        "parser_key": batch.get("parser_key"),
        "source_type": batch.get("source_type"),
        "filename": batch.get("filename"),
        "period_year": batch.get("period_year"),
        "period_month": batch.get("period_month"),
        "error_message": batch.get("error_message"),
        "import_job_id": batch.get("import_job_id"),
    }


__all__ = [
    "detect_columns",
    "get_batch_response",
    "list_import_profiles",
    "parse_structured_file",
    "parse_with_llm_fallback",
    "save_import_profile",
]
