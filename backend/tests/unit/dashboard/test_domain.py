"""
Tests unitaires du domaine dashboard : règles métier et enums.

Aucune dépendance DB ni HTTP. Couvre :
- domain/rules.py : count_working_days_between, compute_absenteeism_rate,
  get_previous_month, get_last_n_past_months, build_upcoming_events_raw,
  aggregate_contract_distribution, count_absence_days_in_range
- domain/enums.py : TeamPulseEventType

Le module n'a pas d'entités ni de value objects définis (placeholders vides).
"""
from datetime import date

import pytest

from app.modules.dashboard.domain.enums import TeamPulseEventType
from app.modules.dashboard.domain.rules import (
    aggregate_contract_distribution,
    build_upcoming_events_raw,
    compute_absenteeism_rate,
    count_absence_days_in_range,
    count_working_days_between,
    get_last_n_past_months,
    get_previous_month,
)


# --- Enums ---


class TestTeamPulseEventType:
    """Tests de l'enum TeamPulseEventType."""

    def test_birthday_value(self):
        assert TeamPulseEventType.BIRTHDAY == "birthday"

    def test_work_anniversary_value(self):
        assert TeamPulseEventType.WORK_ANNIVERSARY == "work_anniversary"


# --- count_working_days_between ---


class TestCountWorkingDaysBetween:
    """Tests de count_working_days_between (jours ouvrés lun–ven)."""

    def test_same_day_weekday(self):
        """Un seul jour un jour ouvré compte 1."""
        assert count_working_days_between(date(2025, 3, 17), date(2025, 3, 17)) == 1

    def test_same_day_weekend(self):
        """Un seul jour un samedi compte 0."""
        assert count_working_days_between(date(2025, 3, 15), date(2025, 3, 15)) == 0

    def test_range_includes_weekend(self):
        """Lun–ven = 5 jours."""
        assert count_working_days_between(date(2025, 3, 17), date(2025, 3, 21)) == 5

    def test_range_with_weekend(self):
        """Lun 17 -> dim 23 : 5 jours ouvrés."""
        assert count_working_days_between(date(2025, 3, 17), date(2025, 3, 23)) == 5

    def test_start_after_end_returns_zero(self):
        """Si start > end, retourne 0."""
        assert count_working_days_between(date(2025, 3, 20), date(2025, 3, 10)) == 0

    def test_two_weeks(self):
        """Deux semaines complètes = 10 jours ouvrés."""
        assert count_working_days_between(date(2025, 3, 3), date(2025, 3, 14)) == 10


# --- compute_absenteeism_rate ---


class TestComputeAbsenteeismRate:
    """Tests du taux d'absentéisme (jours absence / jours ouvrés théoriques * 100)."""

    def test_zero_theoretical_returns_zero(self):
        """Si jours théoriques = 0, taux = 0."""
        assert compute_absenteeism_rate(5, 0) == 0.0

    def test_zero_absence(self):
        assert compute_absenteeism_rate(0, 100) == 0.0

    def test_half_absence(self):
        """50 jours sur 100 = 50%."""
        assert compute_absenteeism_rate(50, 100) == 50.0

    def test_rounded_one_decimal(self):
        """Arrondi à 1 décimale."""
        assert compute_absenteeism_rate(1, 3) == 33.3
        assert compute_absenteeism_rate(1, 7) == 14.3


# --- get_previous_month ---


class TestGetPreviousMonth:
    """Tests du mois précédent (numéro, année)."""

    def test_january_returns_december_previous_year(self):
        assert get_previous_month(date(2025, 1, 15)) == (12, 2024)

    def test_march_returns_february_same_year(self):
        assert get_previous_month(date(2025, 3, 10)) == (2, 2025)

    def test_december_returns_november(self):
        assert get_previous_month(date(2025, 12, 31)) == (11, 2025)


# --- get_last_n_past_months ---


class TestGetLastNPastMonths:
    """Tests des n derniers mois strictement antérieurs à current_month."""

    def test_empty_set_returns_empty(self):
        assert get_last_n_past_months(set(), 6, n=12) == []

    def test_only_future_months_returns_empty(self):
        """Mois >= current_month exclus."""
        assert get_last_n_past_months({7, 8, 9}, 6, n=12) == []

    def test_returns_sorted_past_months(self):
        assert get_last_n_past_months({1, 3, 5}, 6, n=12) == [1, 3, 5]

    def test_respects_n_limit(self):
        """Au plus n mois."""
        assert get_last_n_past_months({1, 2, 3, 4, 5}, 6, n=3) == [3, 4, 5]

    def test_current_month_excluded(self):
        """current_month ne doit pas être dans le résultat."""
        assert get_last_n_past_months({4, 5, 6}, 6, n=12) == [4, 5]


# --- build_upcoming_events_raw ---


class TestBuildUpcomingEventsRaw:
    """Tests des événements à venir (anniversaire, ancienneté) dans une fenêtre."""

    def test_empty_employees_returns_empty(self):
        assert build_upcoming_events_raw([], date(2025, 3, 17), 7) == []

    def test_birthday_in_window(self):
        """Anniversaire dans la fenêtre [ref, ref+7]."""
        employees = [
            {
                "id": "e1",
                "first_name": "Jean",
                "last_name": "Dupont",
                "date_naissance": "1990-03-20",
                "hire_date": None,
            },
        ]
        events = build_upcoming_events_raw(
            employees, date(2025, 3, 17), window_days=7
        )
        assert len(events) == 1
        assert events[0]["type"] == "birthday"
        assert events[0]["employee_name"] == "Jean Dupont"
        assert events[0]["date"] == date(2025, 3, 20)
        assert "ans" in events[0]["detail"]

    def test_work_anniversary_in_window(self):
        """Ancienneté dans la fenêtre (hire_date avant ref.year)."""
        employees = [
            {
                "id": "e2",
                "first_name": "Marie",
                "last_name": "Martin",
                "date_naissance": None,
                "hire_date": "2020-03-19",
            },
        ]
        events = build_upcoming_events_raw(
            employees, date(2025, 3, 17), window_days=7
        )
        assert len(events) >= 1
        work = next(e for e in events if e["type"] == "work_anniversary")
        assert work["employee_name"] == "Marie Martin"
        assert work["date"] == date(2025, 3, 19)
        assert "ancienneté" in work["detail"]

    def test_events_sorted_by_date(self):
        """Les événements sont triés par date."""
        employees = [
            {"id": "e1", "first_name": "A", "last_name": "A", "date_naissance": "1990-03-22", "hire_date": None},
            {"id": "e2", "first_name": "B", "last_name": "B", "date_naissance": "1985-03-18", "hire_date": None},
        ]
        events = build_upcoming_events_raw(employees, date(2025, 3, 17), 10)
        assert len(events) == 2
        assert events[0]["date"] <= events[1]["date"]
        assert events[0]["date"] == date(2025, 3, 18)
        assert events[1]["date"] == date(2025, 3, 22)

    def test_skips_invalid_employee_data(self):
        """Employé sans date_naissance ni hire_date ou données invalides ne fait pas planter."""
        employees = [
            {"id": "e1", "first_name": "X", "last_name": "Y"},  # pas de dates
            {"id": "e2", "first_name": "Z", "last_name": "W", "date_naissance": "invalid"},
        ]
        events = build_upcoming_events_raw(employees, date(2025, 3, 17), 30)
        assert isinstance(events, list)


# --- aggregate_contract_distribution ---


class TestAggregateContractDistribution:
    """Tests de la répartition par type de contrat."""

    def test_empty_returns_empty_dict(self):
        assert aggregate_contract_distribution([]) == {}

    def test_counts_by_contract_type(self):
        employees = [
            {"id": "1", "contract_type": "CDI"},
            {"id": "2", "contract_type": "CDI"},
            {"id": "3", "contract_type": "CDD"},
        ]
        dist = aggregate_contract_distribution(employees)
        assert dist == {"CDI": 2, "CDD": 1}

    def test_missing_contract_type_uses_non_defini(self):
        employees = [
            {"id": "1", "contract_type": None},
            {"id": "2"},  # pas de clé
        ]
        dist = aggregate_contract_distribution(employees)
        assert dist.get("Non défini") == 2


# --- count_absence_days_in_range ---


class TestCountAbsenceDaysInRange:
    """Tests du comptage de jours d'absence (ouvrés) dans [start, end] pour employee_ids."""

    def test_empty_absences_returns_zero(self):
        assert count_absence_days_in_range(
            [], {"e1"}, date(2025, 3, 1), date(2025, 3, 31)
        ) == 0

    def test_filters_by_employee_id(self):
        """Seuls les employés dans employee_ids sont comptés."""
        absences = [
            {"employee_id": "e1", "selected_days": ["2025-03-10", "2025-03-11"]},
            {"employee_id": "e2", "selected_days": ["2025-03-10"]},
        ]
        # seulement e1
        n = count_absence_days_in_range(
            absences, {"e1"}, date(2025, 3, 1), date(2025, 3, 31)
        )
        assert n == 2  # 10 et 11 mars 2025 sont des jours ouvrés (lun, mar)

    def test_excludes_weekend_days(self):
        """Les jours weekend dans selected_days ne sont pas comptés."""
        absences = [
            {"employee_id": "e1", "selected_days": ["2025-03-15", "2025-03-16"]},  # sam, dim
        ]
        n = count_absence_days_in_range(
            absences, {"e1"}, date(2025, 3, 1), date(2025, 3, 31)
        )
        assert n == 0

    def test_excludes_days_outside_range(self):
        absences = [
            {"employee_id": "e1", "selected_days": ["2025-03-05", "2025-03-20"]},
        ]
        n = count_absence_days_in_range(
            absences, {"e1"}, date(2025, 3, 10), date(2025, 3, 15)
        )
        assert n == 0  # 5 et 20 hors fenêtre

    def test_counts_only_weekdays_in_range(self):
        absences = [
            {"employee_id": "e1", "selected_days": ["2025-03-17", "2025-03-18", "2025-03-19"]},
        ]
        n = count_absence_days_in_range(
            absences, {"e1"}, date(2025, 3, 17), date(2025, 3, 19)
        )
        assert n == 3  # lun, mar, mer
