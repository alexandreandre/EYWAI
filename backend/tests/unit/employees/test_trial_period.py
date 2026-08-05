"""Tests unitaires du statut calculé période d'essai."""

from __future__ import annotations

from datetime import date

from app.modules.employees.domain.deadline_reminders import count_ending_trial_periods
from app.modules.employees.domain.trial_period import (
    TRIAL_JSON_STATUT_CONFIRMED,
    TRIAL_STATUS_CONFIRMED,
    TRIAL_STATUS_ENDED,
    TRIAL_STATUS_ENDING_SOON,
    TRIAL_STATUS_IN_PROGRESS,
    TRIAL_STATUS_TO_COMPLETE,
    calculate_trial_period_status,
    is_trial_eligible_for_reminder,
)


class TestCalculateTrialPeriodStatus:
    def test_in_progress(self):
        ref = date(2025, 2, 1)
        result = calculate_trial_period_status(
            "2025-01-15",
            {"duree_initiale": 2, "unite": "mois", "renouvellement_possible": True},
            "actif",
            "CDI",
            reference_date=ref,
        )
        assert result["trial_period_applicable"] is True
        assert result["trial_period_status"] == TRIAL_STATUS_IN_PROGRESS
        assert result["trial_period_end_date"] == "2025-03-14"
        assert result["trial_period_days_remaining"] == 41
        assert result["trial_period_renewal_possible"] is True

    def test_ending_soon(self):
        ref = date(2025, 3, 10)
        result = calculate_trial_period_status(
            "2025-01-15",
            {"duree_initiale": 2, "unite": "mois"},
            "actif",
            reference_date=ref,
        )
        assert result["trial_period_status"] == TRIAL_STATUS_ENDING_SOON
        assert result["trial_period_days_remaining"] == 4

    def test_ended(self):
        ref = date(2025, 4, 1)
        result = calculate_trial_period_status(
            "2025-01-15",
            {"duree_initiale": 2, "unite": "mois"},
            "actif",
            reference_date=ref,
        )
        assert result["trial_period_status"] == TRIAL_STATUS_ENDED
        assert result["trial_period_days_remaining"] == -18

    def test_confirmed(self):
        ref = date(2025, 3, 10)
        result = calculate_trial_period_status(
            "2025-01-15",
            {
                "duree_initiale": 2,
                "unite": "mois",
                "statut": TRIAL_JSON_STATUT_CONFIRMED,
            },
            "actif",
            reference_date=ref,
        )
        assert result["trial_period_status"] == TRIAL_STATUS_CONFIRMED
        assert result["trial_period_days_remaining"] is None

    def test_to_complete_recent_hire(self):
        ref = date(2025, 1, 20)
        result = calculate_trial_period_status(
            "2025-01-15",
            None,
            "actif",
            reference_date=ref,
        )
        assert result["trial_period_status"] == TRIAL_STATUS_TO_COMPLETE

    def test_not_applicable_when_parti(self):
        result = calculate_trial_period_status(
            "2025-01-15",
            {"duree_initiale": 2, "unite": "mois"},
            "parti",
        )
        assert result["trial_period_applicable"] is False
        assert result["trial_period_status"] is None


class TestTrialReminderEligibility:
    def test_confirmed_excluded_from_reminders(self):
        pe = {"duree_initiale": 2, "unite": "mois", "statut": TRIAL_JSON_STATUT_CONFIRMED}
        assert is_trial_eligible_for_reminder(pe) is False

    def test_in_progress_eligible(self):
        pe = {"duree_initiale": 2, "unite": "mois", "statut": "en_cours"}
        assert is_trial_eligible_for_reminder(pe) is True

    def test_confirmed_not_counted_in_alerts(self):
        ref = date(2025, 6, 1)
        employees = [
            {
                "id": "e1",
                "employment_status": "actif",
                "hire_date": "2025-04-01",
                "trial_period": {"end_date": "2025-06-01", "status": "confirmee"},
            }
        ]
        assert count_ending_trial_periods(employees, ref) == 0

    def test_unconfirmed_still_counted(self):
        ref = date(2025, 6, 1)
        employees = [
            {
                "id": "e1",
                "employment_status": "actif",
                "hire_date": "2025-04-02",
                "trial_period": {"end_date": "2025-06-01", "status": "en_cours"},
            }
        ]
        assert count_ending_trial_periods(employees, ref) == 1


class TestUpdateEmployeeSchema:
    def test_update_employee_schema_accepts_periode_essai(self):
        from app.modules.employees.schemas.requests import UpdateEmployee

        periode_essai = {
            "duree_initiale": 2,
            "unite": "mois",
            "renouvellement_possible": True,
            "statut": "en_cours",
        }
        payload = UpdateEmployee(periode_essai=periode_essai)
        dumped = payload.model_dump(exclude_unset=True)
        assert dumped["periode_essai"] == periode_essai
