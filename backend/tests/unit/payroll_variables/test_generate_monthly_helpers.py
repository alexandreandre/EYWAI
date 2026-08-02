"""Tests helpers génération variables paie (comptage planning)."""

from app.modules.payroll_variables.application.generate_monthly import (
    _count_planning_shift_entries,
)
from app.modules.payroll_variables.domain.rules import compute_rule_amount


def test_per_shift_type_amount():
    amount = compute_rule_amount("per_shift_type", 5.0, None, 18.0)
    assert amount == 90.0


def test_count_planning_shift_entries_filters_codes(monkeypatch):
    events = {
        "planning_hours": [
            {"shift_type_code": "MATIN"},
            {"shift_type_code": "APREM"},
            {"shift_type_code": "NUIT"},
            {"shift_type_code": "MATIN"},
        ]
    }

    class FakeResp:
        data = [{"payroll_events": events}]

    class FakeQuery:
        def select(self, *_a, **_k):
            return self

        def eq(self, *_a, **_k):
            return self

        def limit(self, *_a, **_k):
            return self

        def execute(self):
            return FakeResp()

    class FakeTable:
        def select(self, *_a, **_k):
            return FakeQuery()

    class FakeSupabase:
        def table(self, _name):
            return FakeTable()

    monkeypatch.setattr(
        "app.modules.payroll_variables.application.generate_monthly.supabase",
        FakeSupabase(),
    )

    count = _count_planning_shift_entries(
        "emp-1", 2026, 5, ["MATIN", "NUIT"]
    )
    assert count == 3.0


def test_jours_absence_lit_selected_days_et_borne_au_mois():
    """Les absences sont une liste de jours explicites, pas un intervalle."""
    from datetime import date

    from app.modules.payroll_variables.application.generate_monthly import _jours_absence

    rows = [
        {"selected_days": ["2026-06-01", "2026-06-02", "2026-07-15"]},
        {"selected_days": ["2026-05-29", "2026-06-30"]},
    ]
    jours = _jours_absence(rows, date(2026, 6, 1), date(2026, 6, 30))
    assert jours == {date(2026, 6, 1), date(2026, 6, 2), date(2026, 6, 30)}


def test_jours_absence_ignore_les_valeurs_invalides():
    from datetime import date

    from app.modules.payroll_variables.application.generate_monthly import _jours_absence

    rows = [{"selected_days": [None, "", "pas-une-date", "2026-06-03"]}]
    assert _jours_absence(rows, date(2026, 6, 1), date(2026, 6, 30)) == {date(2026, 6, 3)}


def test_parse_date_iso_tolere_un_horodatage():
    from datetime import date

    from app.modules.payroll_variables.application.generate_monthly import _parse_date_iso

    assert _parse_date_iso("2026-06-15T00:00:00+00:00") == date(2026, 6, 15)
    assert _parse_date_iso(None) is None
    assert _parse_date_iso("n'importe quoi") is None
