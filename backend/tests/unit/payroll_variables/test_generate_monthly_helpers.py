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
