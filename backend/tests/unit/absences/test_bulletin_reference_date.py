"""Tests — date de référence import CP depuis bulletin."""

from datetime import date
from unittest.mock import patch

from app.modules.absences.application.leave_settings_commands import bulletin_reference_date


class TestBulletinReferenceDate:
    @patch("app.modules.absences.application.leave_settings_commands.date")
    def test_uses_end_of_bulletin_month(self, mock_date):
        mock_date.today.return_value = date(2026, 6, 23)
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)

        ref = bulletin_reference_date(2026, 5)
        assert ref == date(2026, 5, 31)

    @patch("app.modules.absences.application.leave_settings_commands.date")
    def test_caps_at_today_for_current_month(self, mock_date):
        mock_date.today.return_value = date(2026, 6, 23)
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)

        ref = bulletin_reference_date(2026, 6)
        assert ref == date(2026, 6, 23)

    @patch("app.modules.absences.application.leave_settings_commands.date")
    def test_without_month_uses_today_for_current_year(self, mock_date):
        mock_date.today.return_value = date(2026, 6, 23)
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)

        ref = bulletin_reference_date(2026)
        assert ref == date(2026, 6, 23)

    @patch("app.modules.absences.application.leave_settings_commands.date")
    def test_without_month_uses_year_end_for_past_year(self, mock_date):
        mock_date.today.return_value = date(2026, 6, 23)
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)

        ref = bulletin_reference_date(2025)
        assert ref == date(2025, 12, 31)
