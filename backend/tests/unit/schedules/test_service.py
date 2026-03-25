"""
Tests unitaires du service applicatif du module schedules (application/service.py).

Dépendances (employee_company_reader) mockées. Pas de DB ni HTTP.
"""

from unittest.mock import patch

import pytest

from app.modules.schedules.application import service
from app.modules.schedules.application.exceptions import ScheduleAppError


# --- get_employee_company_and_statut ---


class TestGetEmployeeCompanyAndStatut:
    """Service get_employee_company_and_statut."""

    def test_returns_company_id_and_statut(self):
        """Reader retourne (company_id, statut) → même tuple retourné."""
        with patch(
            "app.modules.schedules.application.service.employee_company_reader",
        ) as reader:
            reader.get_company_and_statut.return_value = (
                "comp-1",
                "cadre forfait jour",
            )

            company_id, statut = service.get_employee_company_and_statut("emp-1")

        assert company_id == "comp-1"
        assert statut == "cadre forfait jour"
        reader.get_company_and_statut.assert_called_once_with("emp-1")

    def test_returns_statut_none_when_not_set(self):
        """Statut non renseigné → None."""
        with patch(
            "app.modules.schedules.application.service.employee_company_reader",
        ) as reader:
            reader.get_company_and_statut.return_value = ("comp-1", None)

            company_id, statut = service.get_employee_company_and_statut("emp-1")

        assert statut is None

    def test_raises_schedule_app_error_not_found_when_employee_absent(self):
        """Employé non trouvé → ScheduleAppError not_found."""
        from app.modules.schedules.domain.exceptions import ScheduleNotFoundError

        with patch(
            "app.modules.schedules.application.service.employee_company_reader",
        ) as reader:
            reader.get_company_and_statut.side_effect = ScheduleNotFoundError(
                "Employé non trouvé ou sans entreprise associée"
            )

            with pytest.raises(ScheduleAppError) as exc_info:
                service.get_employee_company_and_statut("emp-unknown")

        assert exc_info.value.code == "not_found"
        assert exc_info.value.status_code == 404

    def test_raises_schedule_app_error_database_when_db_error(self):
        """Erreur DB → ScheduleAppError database_error."""
        from app.modules.schedules.domain.exceptions import ScheduleDatabaseError

        with patch(
            "app.modules.schedules.application.service.employee_company_reader",
        ) as reader:
            reader.get_company_and_statut.side_effect = ScheduleDatabaseError(
                "Erreur de connexion"
            )

            with pytest.raises(ScheduleAppError) as exc_info:
                service.get_employee_company_and_statut("emp-1")

        assert exc_info.value.code == "database_error"
        assert exc_info.value.status_code == 500


# --- normalize_planned_calendar_for_employee ---


class TestNormalizePlannedCalendarForEmployee:
    """Service normalize_planned_calendar_for_employee."""

    def test_delegates_to_domain_rules(self):
        """Délègue à domain.rules.normalize_planned_calendar_for_forfait_jour."""
        calendrier = [{"jour": 1, "type": "work", "heures_prevues": 8}]
        normalized = [{"jour": 1, "type": "work", "heures_prevues": 1}]
        with patch(
            "app.modules.schedules.application.service.domain_rules.normalize_planned_calendar_for_forfait_jour",
            return_value=normalized,
        ) as domain_fn:
            result = service.normalize_planned_calendar_for_employee(
                calendrier, "cadre forfait jour"
            )

        assert result == normalized
        domain_fn.assert_called_once_with(calendrier, "cadre forfait jour")


# --- normalize_actual_hours_for_employee ---


class TestNormalizeActualHoursForEmployee:
    """Service normalize_actual_hours_for_employee."""

    def test_delegates_to_domain_rules(self):
        """Délègue à domain.rules.normalize_actual_hours_for_forfait_jour."""
        calendrier = [{"jour": 1, "heures_faites": 7.5}]
        normalized = [{"jour": 1, "heures_faites": 1}]
        with patch(
            "app.modules.schedules.application.service.domain_rules.normalize_actual_hours_for_forfait_jour",
            return_value=normalized,
        ) as domain_fn:
            result = service.normalize_actual_hours_for_employee(
                calendrier, "cadre forfait jour"
            )

        assert result == normalized
        domain_fn.assert_called_once_with(calendrier, "cadre forfait jour")
