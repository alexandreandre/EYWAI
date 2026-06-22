"""Tests unitaires — contrôles qualité import pointages."""

from app.modules.schedules.application.timesheet_quality import (
    COVERAGE_INCOMPLETE_THRESHOLD,
    run_quality_checks,
)
from app.modules.schedules.schemas.ai import AiDayEntry, AiEmployeeProposal


def _emp(**kwargs) -> AiEmployeeProposal:
    base = AiEmployeeProposal(raw_name="TEST", employee_id="e1", review_status="ok")
    for k, v in kwargs.items():
        setattr(base, k, v)
    return base


class TestTimesheetQuality:
    def test_extraction_incomplete_when_missing_workdays(self):
        emp = _emp(
            days=[AiDayEntry(jour=26, heures=7.0, type="travail", nature="reel")],
            weekly_total_pdf=37.0,
            days_expected_count=5,
            days_imported_count=1,
            coverage_ratio=0.2,
        )
        updated, checks, _ = run_quality_checks([emp], [])
        assert updated[0].quality_issue == "extraction_incomplete"
        assert any(c.code == "extraction_incomplete" for c in checks)

    def test_extraction_incomplete_when_low_coverage_and_high_gap(self):
        emp = _emp(
            days=[AiDayEntry(jour=26, heures=7.0, type="travail", nature="reel")],
            weekly_total_pdf=37.0,
            days_expected_count=5,
            days_imported_count=2,
            coverage_ratio=0.4,
        )
        updated, checks, _ = run_quality_checks([emp], [])
        assert updated[0].quality_issue == "extraction_incomplete"
        assert any(c.code == "extraction_incomplete" for c in checks)

    def test_weekly_gap_when_coverage_ok(self):
        emp = _emp(
            days=[
                AiDayEntry(jour=26, heures=7.0, type="travail", nature="reel"),
                AiDayEntry(jour=27, heures=7.0, type="travail", nature="reel"),
            ],
            weekly_total_pdf=20.0,
            days_expected_count=5,
            days_imported_count=5,
            coverage_ratio=1.0,
        )
        updated, checks, _ = run_quality_checks([emp], [])
        assert updated[0].quality_issue == "weekly_total_gap"
        assert any(c.code.startswith("weekly_total_gap") for c in checks)

    def test_ready_when_gap_within_tolerance(self):
        emp = _emp(
            days=[AiDayEntry(jour=26, heures=7.0, type="travail", nature="reel")],
            weekly_total_pdf=7.1,
            days_expected_count=1,
            days_imported_count=1,
            coverage_ratio=1.0,
        )
        updated, _, _ = run_quality_checks([emp], [])
        assert updated[0].review_status == "ok"
        assert updated[0].quality_issue is None

    def test_match_doubtful_blocks_ready(self):
        emp = _emp(
            match_confidence="medium",
            match_method="name_fuzzy",
            review_status="warning",
            days=[AiDayEntry(jour=26, heures=7.0, type="travail", nature="reel")],
        )
        updated, checks, _ = run_quality_checks([emp], [])
        assert updated[0].quality_issue == "match_doubtful"
        assert any(c.code == "match_doubtful" for c in checks)

    def test_coverage_threshold_constant(self):
        assert COVERAGE_INCOMPLETE_THRESHOLD == 0.6
