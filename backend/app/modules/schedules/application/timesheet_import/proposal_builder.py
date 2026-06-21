"""Construction proposition à partir des parseurs déterministes."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from app.modules.schedules.application.employee_match import resolve_employee_for_timesheet
from app.modules.schedules.application.timesheet_import.registry import ParseAttempt
from app.modules.schedules.application.timesheet_import.structured_parser import (
    TabularDayRow,
    TabularParseResult,
)
from app.modules.schedules.schemas.ai import (
    AiCalendarProposalResponse,
    AiDayEntry,
    AiEmployeeProposal,
    RosterEmployee,
)


def build_proposal_from_tabular(
    parsed: TabularParseResult,
    *,
    year: int,
    month: int,
    roster: List[RosterEmployee],
    source: str = "relevé tabulaire",
) -> AiCalendarProposalResponse:
    by_key: Dict[str, List[TabularDayRow]] = defaultdict(list)
    for row in parsed.rows:
        key = row.matricule or row.raw_name or f"row_{row.jour}"
        by_key[key].append(row)

    employees_out: List[AiEmployeeProposal] = []
    for key, rows in by_key.items():
        sample = rows[0]
        raw_name = sample.raw_name or key
        proposal = resolve_employee_for_timesheet(
            raw_name=raw_name,
            matricule=sample.matricule,
            roster=roster,
        )
        days = [
            AiDayEntry(
                jour=r.jour,
                heures=r.heures,
                type="travail",
                nature="reel",
                punch_entry_raw=str(r.entry_raw) if r.entry_raw is not None else None,
                punch_exit_raw=str(r.exit_raw) if r.exit_raw is not None else None,
                shift_code=r.shift_code,
            )
            for r in rows
        ]
        proposal.days = days
        proposal.days_imported_count = len(days)
        proposal.days_expected_count = len(days)
        proposal.coverage_ratio = 1.0 if days else 0.0
        employees_out.append(proposal)

    has_punch_pairs = any(
        r.entry_raw is not None or r.exit_raw is not None for r in parsed.rows
    )
    fmt = "tabular_punch_pairs" if has_punch_pairs else "tabular_generic"

    return AiCalendarProposalResponse(
        year=year,
        month=month,
        source=source,
        employees=employees_out,
        warnings=list(parsed.warnings),
        detected_format=fmt,
        parse_confidence=parsed.confidence,
    )


def build_proposal_from_attempt(
    attempt: ParseAttempt,
    *,
    year: int,
    month: int,
    roster: List[RosterEmployee],
) -> AiCalendarProposalResponse | None:
    if attempt.parser_key in ("tabular_generic", "tabular_punch_pairs") and attempt.parse_result:
        return build_proposal_from_tabular(
            attempt.parse_result,
            year=year,
            month=month,
            roster=roster,
            source=f"relevé tabulaire ({attempt.extraction_method or 'fichier'})",
        )
    if attempt.parser_key == "cegid_weekly" and attempt.parse_result:
        from app.modules.schedules.application.ai_fill import _build_proposal_from_cegid

        return _build_proposal_from_cegid(
            year=year,
            month=month,
            source=f"relevé Cegid ({attempt.extraction_method or 'ocr'})",
            parse_result=attempt.parse_result,
            roster=roster,
            default_nature="reel",
        )
    if attempt.parser_key == "kelio_weekly" and attempt.parse_result:
        from app.modules.schedules.application.ai_fill import _build_proposal_from_cegid

        return _build_proposal_from_cegid(
            year=year,
            month=month,
            source=f"relevé Kelio ({attempt.extraction_method or 'ocr'})",
            parse_result=attempt.parse_result,
            roster=roster,
            default_nature="reel",
        )
    return None


__all__ = ["build_proposal_from_attempt", "build_proposal_from_tabular"]
