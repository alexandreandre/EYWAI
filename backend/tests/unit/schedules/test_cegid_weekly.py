"""Tests unitaires du parseur Cegid hebdomadaire."""

from app.modules.schedules.application.parsers.cegid_weekly import (
    focus_week_index_for_period,
    is_cegid_weekly_format,
    try_parse_cegid_weekly,
)
from datetime import date

from tests.fixtures.timesheets.ocr_samples import CEGID_WEEK_22, CEGID_WEEK_22_OCR_NOISY


class TestCegidWeeklyFormat:
    def test_detects_cegid_format(self):
        assert is_cegid_weekly_format(CEGID_WEEK_22)

    def test_rejects_generic_text(self):
        assert not is_cegid_weekly_format("Relevé inconnu sans structure")


class TestCegidWeeklyParse:
    def test_parses_employees_and_days(self):
        result = try_parse_cegid_weekly(
            CEGID_WEEK_22, target_year=2026, target_month=5
        )
        assert result.format_detected
        assert result.confidence >= 0.75
        assert result.week_number == 22
        assert result.period_start == date(2026, 5, 25)
        assert len(result.employees) == 3

        adam = next(e for e in result.employees if e.matricule == "196")
        assert adam.raw_name == "ADAM YOUSSEF"
        assert len(adam.days) == 5
        assert adam.weekly_total_hours == 37.29 or abs(adam.weekly_total_hours - 37.29) < 0.25

        lika = next(e for e in result.employees if e.matricule == "95")
        assert lika.empty_week is True

    def test_junk_footer_block_excluded(self):
        junk = CEGID_WEEK_22 + """
1616 Édition en heures et minutes
Lundi 25/05/26
# 0:00
Total pour la semaine 22/2026: 0:00
"""
        result = try_parse_cegid_weekly(junk, target_year=2026, target_month=5)
        assert not any(e.raw_name.startswith("Édition") for e in result.employees)

    def test_zero_hour_weekday_counts_in_coverage(self):
        result = try_parse_cegid_weekly(
            CEGID_WEEK_22, target_year=2026, target_month=5
        )
        durand = next(e for e in result.employees if e.matricule == "270")
        assert durand.days_parsed_count == 5

    def test_focus_week_index(self):
        idx = focus_week_index_for_period(2026, 5, date(2026, 5, 25))
        assert idx is not None
        assert idx >= 0


class TestCegidWeeklyOcrNoisy:
    def test_parses_noisy_fixture(self):
        result = try_parse_cegid_weekly(
            CEGID_WEEK_22_OCR_NOISY, target_year=2026, target_month=5
        )
        assert result.format_detected
        assert result.confidence >= 0.75
        adam = next(e for e in result.employees if e.matricule == "196")
        assert len(adam.days) == 5
        assert abs(adam.weekly_total_hours - 37.29) < 0.25
        assert adam.days_parsed_count >= 4

    def test_durand_total(self):
        result = try_parse_cegid_weekly(
            CEGID_WEEK_22_OCR_NOISY, target_year=2026, target_month=5
        )
        durand = next(e for e in result.employees if e.matricule == "270")
        assert durand.weekly_total_hours == 28.0
        assert len(durand.days) == 5
