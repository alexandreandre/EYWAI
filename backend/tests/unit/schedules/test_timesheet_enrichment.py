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


class TestLesBadgesSurviventALEnrichissement:
    """La revue d'un tableur de badgeuse montre les badges de chaque jour : l'enrichissement
    (fériés, week-end, plafond) ne doit jamais les effacer."""

    def test_un_jour_ouvre_garde_ses_badges_et_son_code(self, monkeypatch):
        monkeypatch.setattr(
            "app.modules.schedules.application.timesheet_enrichment.day_numbers_observed_holidays",
            lambda y, m, c: set(),
        )
        emp = AiEmployeeProposal(
            raw_name="ADAM",
            days=[
                AiDayEntry(
                    jour=3, heures=7.0, type="travail", nature="reel",
                    punch_entry_raw="07:28", punch_exit_raw="15:55",
                    shift_code="A", punch_break_minutes=45, planned_paid_break_minutes=30,
                )
            ],
        )
        jour = enrich_employee_days(emp, year=2026, month=6, company_id="co1").days[0]
        assert (jour.punch_entry_raw, jour.punch_exit_raw) == ("07:28", "15:55")
        assert jour.shift_code == "A"
        assert jour.punch_break_minutes == 45
        assert jour.planned_paid_break_minutes == 30

    def test_une_entree_sans_sortie_garde_son_badge(self, monkeypatch):
        monkeypatch.setattr(
            "app.modules.schedules.application.timesheet_enrichment.day_numbers_observed_holidays",
            lambda y, m, c: set(),
        )
        emp = AiEmployeeProposal(
            raw_name="ADAM",
            days=[AiDayEntry(jour=9, heures=None, type="travail", nature="reel", punch_entry_raw="04:38")],
        )
        jour = enrich_employee_days(emp, year=2026, month=6, company_id="co1").days[0]
        assert jour.heures is None
        assert jour.punch_entry_raw == "04:38"
        assert jour.punch_exit_raw is None

    def test_un_ferie_change_de_type_et_garde_ses_badges(self, monkeypatch):
        monkeypatch.setattr(
            "app.modules.schedules.application.timesheet_enrichment.day_numbers_observed_holidays",
            lambda y, m, c: {25},
        )
        emp = AiEmployeeProposal(
            raw_name="ADAM",
            days=[AiDayEntry(jour=25, heures=None, type="travail", nature="reel", punch_entry_raw="08:00")],
        )
        jour = enrich_employee_days(emp, year=2026, month=5, company_id="co1").days[0]
        assert jour.type == "ferie"
        assert jour.punch_entry_raw == "08:00"
