"""Tests unitaires — enrichissement import pointages."""

from app.modules.schedules.application.timesheet_enrichment import enrich_employee_days
from app.modules.schedules.schemas.ai import AiDayEntry, AiEmployeeProposal


class TestTimesheetEnrichment:
    def test_holiday_hours_kept_with_warning(self, monkeypatch):
        monkeypatch.setattr(
            "app.modules.schedules.application.timesheet_enrichment.day_numbers_observed_holidays",
            lambda y, m, c: {25},
        )
        emp = AiEmployeeProposal(
            raw_name="ADAM",
            days=[AiDayEntry(jour=25, heures=7.23, type="travail", nature="reel")],
        )
        result = enrich_employee_days(emp, year=2026, month=5, company_id="co1")
        assert result.days[0].type == "travail"
        assert result.days[0].heures == 7.23
        assert any("férié" in w and "à confirmer" in w for w in result.warnings)

    def test_holiday_without_hours_marked_ferie(self, monkeypatch):
        monkeypatch.setattr(
            "app.modules.schedules.application.timesheet_enrichment.day_numbers_observed_holidays",
            lambda y, m, c: {25},
        )
        emp = AiEmployeeProposal(
            raw_name="ADAM",
            days=[AiDayEntry(jour=25, heures=None, type="travail", nature="reel")],
        )
        result = enrich_employee_days(emp, year=2026, month=5, company_id="co1")
        assert result.days[0].type == "ferie"
        assert result.days[0].heures is None

    def test_max_hours_warning(self, monkeypatch):
        monkeypatch.setattr(
            "app.modules.schedules.application.timesheet_enrichment.day_numbers_observed_holidays",
            lambda y, m, c: set(),
        )
        emp = AiEmployeeProposal(
            raw_name="X",
            days=[AiDayEntry(jour=10, heures=14.0, type="travail", nature="reel")],
        )
        result = enrich_employee_days(emp, year=2026, month=5, company_id=None)
        assert any("plafond" in w for w in result.warnings)
