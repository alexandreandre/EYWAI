"""Tests finalisation période imports tabulaires."""

from datetime import date

from app.modules.schedules.application.timesheet_import.tabular_period import (
    collect_dates_from_proposal,
    finalize_tabular_proposal,
)
from app.modules.schedules.schemas.ai import (
    AiCalendarProposalResponse,
    AiDayEntry,
    AiEmployeeProposal,
)


def _sample_proposal() -> AiCalendarProposalResponse:
    return AiCalendarProposalResponse(
        year=2026,
        month=6,
        source="relevé tabulaire (fichier)",
        employees=[
            AiEmployeeProposal(
                raw_name="Francine BOURMAULT",
                time_tracking_id="000005",
                days=[
                    AiDayEntry(jour=8, heures=7.05, type="travail", nature="reel"),
                    AiDayEntry(jour=9, heures=0.0, type="travail", nature="reel"),
                    AiDayEntry(jour=11, heures=7.02, type="travail", nature="reel"),
                ],
            ),
        ],
        detected_format="tabular_punch_pairs",
    )


class TestFinalizeTabularProposal:
    def test_weekly_period_from_employee_days(self):
        proposal = _sample_proposal()
        dates = collect_dates_from_proposal(proposal)
        assert dates == [date(2026, 6, 8), date(2026, 6, 9), date(2026, 6, 11)]

        finalized = finalize_tabular_proposal(
            proposal,
            dates=dates,
            requested_year=2026,
            requested_month=6,
            roster=[],
            company_id=None,
            parser_key="tabular_punch_pairs",
            parse_confidence=0.95,
            extraction_warnings=[],
        )
        assert finalized.detected_period_start == date(2026, 6, 8)
        assert finalized.detected_period_end == date(2026, 6, 11)
        assert finalized.detected_scope == "weekly"
        assert finalized.focus_week_index is not None
