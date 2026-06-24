"""Orchestration parse / batch pour import calendrier prévu."""

from __future__ import annotations

import hashlib
from datetime import date
from typing import Any, Dict, List, Optional

from app.modules.schedules.application.exceptions import ScheduleAppError
from app.modules.schedules.application.timesheet_import.cache_service import (
    check_file_hash_committed,
)
from app.modules.schedules.application.timesheet_import.batch_service import (
    create_batch_from_proposal,
)
from app.modules.schedules.application.timesheet_import.parse_service import (
    parse_structured_file,
)
from app.modules.schedules.application.timesheet_import.tabular_period import (
    ImportPeriodConfig,
)
from app.modules.schedules.application.planning_import.quadra_calendar import (
    is_quadra_planning_workbook,
    parse_quadra_planning_workbook,
)
from app.modules.schedules.infrastructure.schedule_import_storage import (
    upload_schedule_import_file,
)
from app.modules.schedules.schemas.ai import (
    AffectedMonth,
    AiCalendarProposalResponse,
    AiDayEntry,
    AiEmployeeProposal,
    RosterEmployee,
)
from app.modules.schedules.schemas.timesheet_import import TimesheetImportParseResponse


def build_proposal_from_month_groups(
    month_groups: List[Dict[str, Any]],
    *,
    year: int,
    month: int,
    filename: str,
    warnings: List[str] | None = None,
) -> AiCalendarProposalResponse:
    employees_out: List[AiEmployeeProposal] = []
    seen: set[tuple[str, int, int]] = set()
    for group in month_groups:
        gy, gm = int(group["year"]), int(group["month"])
        for emp in group.get("employees") or []:
            days = [AiDayEntry(**day) for day in emp.get("days") or []]
            key = (str(emp.get("employee_id") or emp.get("raw_name")), gy, gm)
            if key in seen:
                continue
            seen.add(key)
            employees_out.append(
                AiEmployeeProposal(
                    raw_name=str(emp.get("raw_name") or ""),
                    employee_id=emp.get("employee_id"),
                    matched_name=emp.get("matched_name"),
                    review_status=emp.get("review_status") or "ok",
                    match_method=emp.get("match_method") or "none",
                    match_confidence=emp.get("match_confidence") or "none",
                    time_tracking_id=emp.get("time_tracking_id"),
                    days=days,
                    days_imported_count=len(days),
                    days_expected_count=len(days),
                    coverage_ratio=1.0 if days else 0.0,
                )
            )

    affected = [
        AffectedMonth(
            year=int(g["year"]),
            month=int(g["month"]),
            days=sorted(
                {
                    int(d["jour"])
                    for emp in g.get("employees") or []
                    for d in emp.get("days") or []
                }
            ),
        )
        for g in month_groups
    ]
    start_dates = [date(g["year"], g["month"], 1) for g in month_groups]
    end_dates = [
        date(g["year"], g["month"], max(int(d["jour"]) for d in emp.get("days") or []))
        for g in month_groups
        for emp in g.get("employees") or []
        if emp.get("days")
    ]

    return AiCalendarProposalResponse(
        year=year,
        month=month,
        source=f"Calendrier prévu Excel ({filename})",
        employees=employees_out,
        warnings=list(warnings or []),
        detected_scope="monthly",
        detected_period_start=min(start_dates) if start_dates else None,
        detected_period_end=max(end_dates) if end_dates else None,
        period_confidence="high",
        affected_months=affected,
        detected_format="quadra_planning_calendar",
        parse_confidence=0.95,
        extraction_mode="structured",
    )


def parse_planning_calendar_file(
    *,
    company_id: str,
    user_id: str | None,
    content: bytes,
    filename: str,
    year: int,
    month: int,
    roster: List[RosterEmployee],
    period_config: ImportPeriodConfig,
) -> TimesheetImportParseResponse:
    file_hash = hashlib.sha256(content).hexdigest()
    previous_committed_batch_id = check_file_hash_committed(company_id, file_hash)
    reimport_extra_summary: Dict[str, Any] | None = (
        {"reimport": True, "previous_committed_batch_id": previous_committed_batch_id}
        if previous_committed_batch_id
        else None
    )

    if is_quadra_planning_workbook(content, filename):
        parsed = parse_quadra_planning_workbook(
            content,
            filename,
            year=year,
            period_config=period_config,
            roster=roster,
        )
        if parsed.sheets_unmatched and not any(
            emp.get("employee_id")
            for group in parsed.month_groups
            for emp in group.get("employees") or []
        ):
            raise ScheduleAppError(
                "validation",
                "Aucun salarié rapproché — vérifiez que les noms de feuilles "
                "correspondent aux employés de l'entreprise.",
                status_code=422,
            )

        proposal = build_proposal_from_month_groups(
            parsed.month_groups,
            year=parsed.year,
            month=parsed.month,
            filename=filename,
            warnings=list(parsed.warnings),
        )
        extra_summary = {
            "multi_month": True,
            "import_kind": "planning",
            "period_mode": period_config.mode,
            "month_groups": parsed.month_groups,
            "months_count": len(parsed.month_groups),
            "sheets_parsed": parsed.sheets_parsed,
            "sheets_unmatched": parsed.sheets_unmatched,
        }
        if reimport_extra_summary:
            extra_summary = {**extra_summary, **reimport_extra_summary}
        parser_key = "quadra_planning_calendar"
    else:
        result = parse_structured_file(
            company_id=company_id,
            user_id=user_id,
            content=content,
            filename=filename,
            year=year,
            month=month,
            roster=roster,
            period_config=period_config,
            allow_reimport=True,
        )
        proposal = result.preview
        if proposal:
            for emp in proposal.employees:
                for day in emp.days:
                    day.nature = "prevu"
            proposal = proposal.model_copy(
                update={
                    "detected_format": proposal.detected_format or "tabular_generic",
                    "source": proposal.source.replace("pointage", "calendrier")
                    if "pointage" in proposal.source.lower()
                    else proposal.source,
                }
            )
        parser_key = result.parser_key
        extra_summary = reimport_extra_summary
        batch = create_batch_from_proposal(
            company_id=company_id,
            user_id=user_id,
            proposal=proposal,
            source_type="xlsx" if filename.lower().endswith((".xlsx", ".xls")) else "csv",
            parser_key=parser_key,
            filename=filename,
            file_hash=file_hash,
            file_content=content,
            extra_summary=extra_summary,
        )
        return TimesheetImportParseResponse(
            batch_id=str(batch["id"]),
            preview=proposal,
            parser_key=parser_key,
            file_hash=file_hash,
        )

    storage_path = None
    try:
        storage_path = upload_schedule_import_file(
            content,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename,
            company_id,
            file_hash[:12],
        )
    except Exception:
        pass

    batch = create_batch_from_proposal(
        company_id=company_id,
        user_id=user_id,
        proposal=proposal,
        source_type="xlsx",
        parser_key=parser_key,
        filename=filename,
        file_hash=file_hash,
        file_storage_path=storage_path,
        file_content=content,
        extra_summary=extra_summary,
    )

    return TimesheetImportParseResponse(
        batch_id=str(batch["id"]),
        preview=proposal,
        parser_key=parser_key,
        file_hash=file_hash,
    )


__all__ = ["build_proposal_from_month_groups", "parse_planning_calendar_file"]
