"""Tests hook retraits CET."""

from app.modules.cet.application.payroll_hook import apply_cet_withdrawals_to_calendar


def test_apply_withdrawals_marks_rest_days():
    cal = [
        {"type": "travail", "heures": 7},
        {"type": "travail", "heures": 7},
    ]

    def fake_get(employee_id, year, month):
        return 7.0, ["m1"]

    import app.modules.cet.application.payroll_hook as hook

    orig = hook.cet_repo.get_validated_withdrawals_for_payroll
    hook.cet_repo.get_validated_withdrawals_for_payroll = fake_get
    try:
        updated, ids = apply_cet_withdrawals_to_calendar("e1", 2026, 6, cal, hours_per_rest_day=7)
        assert ids == ["m1"]
        assert any(j.get("type") == "cet_repos" for j in updated)
    finally:
        hook.cet_repo.get_validated_withdrawals_for_payroll = orig
