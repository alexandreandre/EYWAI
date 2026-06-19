"""Tests parseur Kelio hebdomadaire."""

from app.modules.schedules.application.parsers.kelio_weekly import (
    is_kelio_weekly_format,
    try_parse_kelio_weekly,
)

KELIO_SAMPLE = """
Kelio Time Management
42 MARTIN Paul
01/05/2026 8:00
02/05/2026 7:30
03/05/2026 8:00
04/05/2026 8:00
05/05/2026 6:00
"""


class TestKelioWeekly:
    def test_detects_format(self):
        assert is_kelio_weekly_format(KELIO_SAMPLE)

    def test_parses_days(self):
        result = try_parse_kelio_weekly(
            KELIO_SAMPLE, target_year=2026, target_month=5
        )
        assert result.format_detected
        assert len(result.employees) == 1
        assert len(result.employees[0].days) == 5
