"""Tests hook paie CET."""

from app.modules.cet.application.payroll_hook import apply_cet_deposits_to_calendar


def test_apply_cet_reduces_work_hours_from_end_of_calendar():
    calendrier = [
        {"jour": 1, "type": "travail", "heures": 8},
        {"jour": 2, "type": "travail", "heures": 8},
        {"jour": 3, "type": "conges_payes", "heures": 0},
    ]

    class FakeRepo:
        @staticmethod
        def get_validated_deposit_hours_for_payroll(employee_id, year, month):
            return 3.0, ["mvt-1"]

    import app.modules.cet.application.payroll_hook as hook

    original = hook.cet_repo.get_validated_deposit_hours_for_payroll
    hook.cet_repo.get_validated_deposit_hours_for_payroll = (
        FakeRepo.get_validated_deposit_hours_for_payroll
    )
    try:
        updated, ids = apply_cet_deposits_to_calendar("emp", 2025, 11, calendrier)
    finally:
        hook.cet_repo.get_validated_deposit_hours_for_payroll = original

    assert ids == ["mvt-1"]
    travail_hours = [j["heures"] for j in updated if j["type"] == "travail"]
    assert sum(travail_hours) == 13.0
