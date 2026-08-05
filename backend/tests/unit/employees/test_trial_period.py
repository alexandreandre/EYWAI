"""Tests unitaires du statut calculé période d'essai.

La source est la table trial_periods : le statut reçoit la ligne active
(end_date, status, renewal_allowed), plus le jsonb historique.
"""

from __future__ import annotations

from datetime import date

from app.modules.employees.domain.deadline_reminders import count_ending_trial_periods
from app.modules.employees.domain.trial_period import (
    TRIAL_STATUS_CONFIRMED,
    TRIAL_STATUS_ENDED,
    TRIAL_STATUS_ENDING_SOON,
    TRIAL_STATUS_IN_PROGRESS,
    TRIAL_STATUS_TO_COMPLETE,
    calculate_trial_period_status,
)


class TestCalculateTrialPeriodStatus:
    def test_in_progress(self):
        result = calculate_trial_period_status(
            "2025-01-15",
            {"end_date": "2025-03-14", "status": "en_cours", "renewal_allowed": True},
            "actif",
            reference_date=date(2025, 2, 1),
        )
        assert result["trial_period_applicable"] is True
        assert result["trial_period_status"] == TRIAL_STATUS_IN_PROGRESS
        assert result["trial_period_end_date"] == "2025-03-14"
        assert result["trial_period_days_remaining"] == 41
        assert result["trial_period_renewal_possible"] is True

    def test_ending_soon(self):
        result = calculate_trial_period_status(
            "2025-01-15",
            {"end_date": "2025-03-14", "status": "en_cours"},
            "actif",
            reference_date=date(2025, 3, 10),
        )
        assert result["trial_period_status"] == TRIAL_STATUS_ENDING_SOON
        assert result["trial_period_days_remaining"] == 4

    def test_ended(self):
        result = calculate_trial_period_status(
            "2025-01-15",
            {"end_date": "2025-03-14", "status": "en_cours"},
            "actif",
            reference_date=date(2025, 4, 1),
        )
        assert result["trial_period_status"] == TRIAL_STATUS_ENDED
        assert result["trial_period_days_remaining"] == -18

    def test_confirmed(self):
        result = calculate_trial_period_status(
            "2025-01-15",
            {"end_date": "2025-03-14", "status": "confirmee"},
            "actif",
            reference_date=date(2025, 3, 10),
        )
        assert result["trial_period_status"] == TRIAL_STATUS_CONFIRMED
        assert result["trial_period_days_remaining"] is None

    def test_to_complete_recent_hire(self):
        result = calculate_trial_period_status(
            "2025-01-15",
            None,
            "actif",
            reference_date=date(2025, 1, 20),
        )
        assert result["trial_period_status"] == TRIAL_STATUS_TO_COMPLETE

    def test_ancien_salarie_sans_periode_reste_muet(self):
        result = calculate_trial_period_status(
            "2020-01-01", None, "actif", reference_date=date(2026, 8, 5)
        )
        assert result["trial_period_applicable"] is False

    def test_not_applicable_when_parti(self):
        result = calculate_trial_period_status(
            "2025-01-15",
            {"end_date": "2025-03-14", "status": "en_cours"},
            "parti",
        )
        assert result["trial_period_applicable"] is False
        assert result["trial_period_status"] is None

    def test_delai_d_alerte_parametrable(self):
        result = calculate_trial_period_status(
            "2026-06-01",
            {"end_date": "2026-08-25", "status": "en_cours"},
            "actif",
            reference_date=date(2026, 8, 5),
            alert_days=30,
        )
        assert result["trial_period_status"] == TRIAL_STATUS_ENDING_SOON

    def test_periode_rompue_n_est_plus_suivie(self):
        result = calculate_trial_period_status(
            "2026-06-01",
            {"end_date": "2026-08-25", "status": "rompue"},
            "actif",
            reference_date=date(2026, 8, 5),
        )
        assert result["trial_period_applicable"] is False


class TestTrialCountsInAlerts:
    def test_confirmed_not_counted_in_alerts(self):
        employees = [
            {
                "id": "e1",
                "employment_status": "actif",
                "hire_date": "2025-04-01",
                "trial_period": {"end_date": "2025-06-01", "status": "confirmee"},
            }
        ]
        assert count_ending_trial_periods(employees, date(2025, 6, 1)) == 0

    def test_unconfirmed_still_counted(self):
        employees = [
            {
                "id": "e1",
                "employment_status": "actif",
                "hire_date": "2025-04-02",
                "trial_period": {"end_date": "2025-06-01", "status": "en_cours"},
            }
        ]
        assert count_ending_trial_periods(employees, date(2025, 6, 1)) == 1
