"""Tests unitaires des règles de relance échéances RH."""

from __future__ import annotations

from datetime import date, timedelta

from app.modules.employees.domain.deadline_reminders import (
    CDD_REMINDER_DAYS,
    REMINDER_TYPE_CDD,
    REMINDER_TYPE_RESIDENCE,
    REMINDER_TYPE_TRIAL,
    RESIDENCE_REMINDER_DAYS,
    compute_trial_period_end,
    count_ending_trial_periods,
    count_expiring_cdds,
    is_active_for_reminder,
    is_in_reminder_window,
    list_hr_deadline_candidates,
)


class TestComputeTrialPeriodEnd:
    def test_mois(self):
        end = compute_trial_period_end("2025-01-15", {"duree_initiale": 2, "unite": "mois"})
        assert end == date(2025, 3, 15)

    def test_jours(self):
        end = compute_trial_period_end("2025-01-15", {"duree": 10, "unite": "jours"})
        assert end == date(2025, 1, 25)

    def test_semaines(self):
        end = compute_trial_period_end("2025-01-15", {"duree": 2, "unite": "semaines"})
        assert end == date(2025, 1, 29)

    def test_missing_data(self):
        assert compute_trial_period_end(None, {"duree_initiale": 2}) is None
        assert compute_trial_period_end("2025-01-15", None) is None


class TestReminderWindow:
    def test_in_window(self):
        ref = date(2025, 6, 1)
        deadline = ref + timedelta(days=10)
        assert is_in_reminder_window(deadline, 15, ref) is True

    def test_outside_window(self):
        ref = date(2025, 6, 1)
        deadline = ref + timedelta(days=20)
        assert is_in_reminder_window(deadline, 15, ref) is False

    def test_past_deadline_excluded(self):
        ref = date(2025, 6, 1)
        deadline = ref - timedelta(days=1)
        assert is_in_reminder_window(deadline, 15, ref) is False


class TestIsActiveForReminder:
    def test_actif(self):
        assert is_active_for_reminder("actif") is True

    def test_en_sortie(self):
        assert is_active_for_reminder("en_sortie") is False


class TestCountExpiringCdds:
    def test_counts_cdd_in_window(self):
        ref = date(2025, 6, 1)
        employees = [
            {
                "id": "e1",
                "employment_status": "actif",
                "contract_type": "CDD",
                "contract_end_date": (ref + timedelta(days=10)).isoformat(),
            },
            {
                "id": "e2",
                "employment_status": "actif",
                "contract_type": "CDI",
                "contract_end_date": (ref + timedelta(days=5)).isoformat(),
            },
            {
                "id": "e3",
                "employment_status": "en_sortie",
                "contract_type": "CDD",
                "contract_end_date": (ref + timedelta(days=5)).isoformat(),
            },
        ]
        assert count_expiring_cdds(employees, ref) == 1


class TestCountEndingTrialPeriods:
    def test_counts_trial_in_window(self):
        ref = date(2025, 6, 1)
        employees = [
            {
                "id": "e1",
                "employment_status": "actif",
                "hire_date": "2025-04-01",
                "periode_essai": {"duree_initiale": 2, "unite": "mois"},
            }
        ]
        assert count_ending_trial_periods(employees, ref) == 1


class TestListHrDeadlineCandidates:
    def test_returns_all_types(self):
        ref = date(2025, 6, 1)
        employees = [
            {
                "id": "e1",
                "first_name": "Alice",
                "last_name": "Martin",
                "employment_status": "actif",
                "contract_type": "CDD",
                "contract_end_date": (ref + timedelta(days=CDD_REMINDER_DAYS)).isoformat(),
                "hire_date": "2025-04-01",
                "periode_essai": {"duree_initiale": 2, "unite": "mois"},
                "is_subject_to_residence_permit": True,
                "residence_permit_expiry_date": (
                    ref + timedelta(days=RESIDENCE_REMINDER_DAYS)
                ).isoformat(),
            }
        ]
        candidates = list_hr_deadline_candidates(employees, ref)
        types = {c.reminder_type for c in candidates}
        assert REMINDER_TYPE_CDD in types
        assert REMINDER_TYPE_TRIAL in types
        assert REMINDER_TYPE_RESIDENCE in types

    def test_excludes_inactive(self):
        ref = date(2025, 6, 1)
        employees = [
            {
                "id": "e1",
                "employment_status": "parti",
                "contract_type": "CDD",
                "contract_end_date": (ref + timedelta(days=5)).isoformat(),
            }
        ]
        assert list_hr_deadline_candidates(employees, ref) == []
