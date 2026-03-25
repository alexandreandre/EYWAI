"""
Tests unitaires des commandes du module schedules (application/commands.py).

Repositories et providers mockés. Pas de DB ni HTTP.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.schedules.application import commands
from app.modules.schedules.application.exceptions import ScheduleAppError


# --- update_planned_calendar ---


class TestUpdatePlannedCalendar:
    """Commande update_planned_calendar."""

    def test_success_upserts_and_returns_status(self):
        """Données valides → upsert appelé, retourne status success."""
        payload = MagicMock()
        payload.year = 2025
        payload.month = 3
        payload.calendrier_prevu = [
            MagicMock(
                model_dump=MagicMock(
                    return_value={"jour": 1, "type": "work", "heures_prevues": 8}
                )
            ),
        ]

        with (
            patch(
                "app.modules.schedules.application.commands.get_employee_company_and_statut",
                return_value=("company-1", "employé"),
            ),
            patch(
                "app.modules.schedules.application.commands.normalize_planned_calendar_for_employee",
                return_value=[{"jour": 1, "type": "work", "heures_prevues": 8}],
            ),
            patch(
                "app.modules.schedules.application.commands.schedule_repository",
            ) as repo,
        ):
            result = commands.update_planned_calendar("emp-1", payload)

        assert result == {
            "status": "success",
            "message": "Planning prévisionnel enregistré.",
        }
        repo.upsert_schedule.assert_called_once()
        call_kw = repo.upsert_schedule.call_args[1]
        assert call_kw["planned_calendar"] is not None
        assert call_kw["planned_calendar"]["calendrier_prevu"] == [
            {"jour": 1, "type": "work", "heures_prevues": 8}
        ]

    def test_raises_schedule_app_error_when_employee_not_found(self):
        """Employé non trouvé → ScheduleAppError not_found."""
        payload = MagicMock()
        payload.year = 2025
        payload.month = 3
        payload.calendrier_prevu = []

        with patch(
            "app.modules.schedules.application.commands.get_employee_company_and_statut",
            side_effect=ScheduleAppError(
                "not_found", "Employé non trouvé", status_code=404
            ),
        ):
            with pytest.raises(ScheduleAppError) as exc_info:
                commands.update_planned_calendar("emp-unknown", payload)
        assert exc_info.value.status_code == 404
        assert exc_info.value.code == "not_found"


# --- update_actual_hours ---


class TestUpdateActualHours:
    """Commande update_actual_hours."""

    def test_success_upserts_and_returns_status(self):
        """Données valides → upsert appelé, retourne status success."""
        payload = MagicMock()
        payload.year = 2025
        payload.month = 4
        payload.calendrier_reel = [
            MagicMock(
                model_dump=MagicMock(return_value={"jour": 1, "heures_faites": 7.5})
            ),
        ]

        with (
            patch(
                "app.modules.schedules.application.commands.get_employee_company_and_statut",
                return_value=("company-1", None),
            ),
            patch(
                "app.modules.schedules.application.commands.normalize_actual_hours_for_employee",
                return_value=[{"jour": 1, "heures_faites": 7.5}],
            ),
            patch(
                "app.modules.schedules.application.commands.schedule_repository",
            ) as repo,
        ):
            result = commands.update_actual_hours("emp-1", payload)

        assert result == {
            "status": "success",
            "message": "Heures réelles enregistrées.",
        }
        repo.upsert_schedule.assert_called_once()
        call_kw = repo.upsert_schedule.call_args[1]
        assert call_kw["actual_hours"] is not None
        assert call_kw["actual_hours"]["calendrier_reel"] == [
            {"jour": 1, "heures_faites": 7.5}
        ]


# --- calculate_payroll_events ---


class TestCalculatePayrollEvents:
    """Commande calculate_payroll_events."""

    def test_raises_when_duree_hebdo_missing(self):
        """Employé sans durée hebdomadaire → ScheduleAppError validation."""
        with patch(
            "app.modules.schedules.application.commands.employee_company_reader",
        ) as reader:
            reader.get_employee_for_payroll_events.return_value = {
                "employee_folder_name": "Dupont_Jean",
                "duree_hebdomadaire": None,
                "statut": "employé",
                "company_id": "comp-1",
            }
            with pytest.raises(ScheduleAppError) as exc_info:
                commands.calculate_payroll_events("emp-1", 2025, 3)
        assert exc_info.value.status_code == 400
        assert "durée hebdomadaire" in exc_info.value.message.lower()

    def test_success_with_payroll_analyzer_and_updates_events(self):
        """Employé non forfait jour → payroll_analyzer appelé, update_payroll_events appelé."""
        reader = MagicMock()
        reader.get_employee_for_payroll_events.return_value = {
            "employee_folder_name": "Dupont_Jean",
            "duree_hebdomadaire": 35.0,
            "statut": "employé",
            "company_id": "comp-1",
        }
        repo = MagicMock()
        repo.get_schedules_for_months.return_value = []
        analyzer = MagicMock()
        analyzer.analyser_horaires.return_value = [
            {"type": "heures_normales", "heures": 35},
        ]

        with (
            patch(
                "app.modules.schedules.application.commands.domain_rules.is_forfait_jour",
                return_value=False,
            ),
            patch(
                "app.modules.schedules.application.commands.employee_company_reader",
                reader,
            ),
            patch(
                "app.modules.schedules.application.commands.schedule_repository",
                repo,
            ),
            patch(
                "app.modules.schedules.application.commands.payroll_analyzer_provider",
                analyzer,
            ),
        ):
            result = commands.calculate_payroll_events("emp-1", 2025, 3)

        assert result["status"] == "success"
        assert "événements de paie" in result["message"]
        repo.update_payroll_events.assert_called_once()
        call_args = repo.update_payroll_events.call_args[0]
        assert call_args[0] == "emp-1"
        assert call_args[1] == 2025
        assert call_args[2] == 3
        assert "calendrier_analyse" in call_args[3]


# --- apply_schedule_model ---


def _make_week_config(work_hours=8.0, rest_hours=0.0):
    """Helper : une semaine avec lun-ven travail, sam-dim repos."""
    MagicMock()
    work = MagicMock(type="work", hours=work_hours)
    rest = MagicMock(type="rest", hours=rest_hours)
    return MagicMock(
        monday=work,
        tuesday=work,
        wednesday=work,
        thursday=work,
        friday=work,
        saturday=rest,
        sunday=rest,
    )


class TestApplyScheduleModel:
    """Commande apply_schedule_model."""

    def test_raises_when_no_active_company(self):
        """Utilisateur sans active_company_id → ScheduleAppError validation."""
        user = MagicMock()
        user.active_company_id = None
        request = MagicMock()
        request.employee_ids = ["emp-1"]
        request.year = 2025
        request.month = 3
        request.week_configs = {1: _make_week_config()}

        with pytest.raises(ScheduleAppError) as exc_info:
            commands.apply_schedule_model(request, user)
        assert exc_info.value.status_code == 400
        assert "entreprise active" in exc_info.value.message.lower()

    def test_raises_when_no_rh_access(self):
        """Utilisateur sans droit RH → ScheduleAppError forbidden."""
        user = MagicMock()
        user.active_company_id = "comp-1"
        user.has_rh_access_in_company = MagicMock(return_value=False)
        request = MagicMock()
        request.employee_ids = ["emp-1"]
        request.year = 2025
        request.month = 3
        request.week_configs = {1: _make_week_config()}

        with pytest.raises(ScheduleAppError) as exc_info:
            commands.apply_schedule_model(request, user)
        assert exc_info.value.status_code == 403
        assert "RH" in exc_info.value.message

    def test_raises_when_no_employee_ids(self):
        """Liste d'employés vide → ScheduleAppError validation."""
        user = MagicMock()
        user.active_company_id = "comp-1"
        user.has_rh_access_in_company = MagicMock(return_value=True)
        request = MagicMock()
        request.employee_ids = []
        request.year = 2025
        request.month = 3
        request.week_configs = {}

        with pytest.raises(ScheduleAppError) as exc_info:
            commands.apply_schedule_model(request, user)
        assert exc_info.value.status_code == 400
        assert "employé" in exc_info.value.message.lower()

    def test_raises_when_invalid_month(self):
        """Mois invalide (0 ou 13) → ScheduleAppError validation."""
        user = MagicMock()
        user.active_company_id = "comp-1"
        user.has_rh_access_in_company = MagicMock(return_value=True)
        request = MagicMock()
        request.employee_ids = ["emp-1"]
        request.year = 2025
        request.month = 0
        request.week_configs = {1: _make_week_config()}

        with pytest.raises(ScheduleAppError) as exc_info:
            commands.apply_schedule_model(request, user)
        assert exc_info.value.status_code == 400
        assert "mois" in exc_info.value.message.lower()

    def test_raises_when_invalid_year(self):
        """Année hors plage → ScheduleAppError validation."""
        user = MagicMock()
        user.active_company_id = "comp-1"
        user.has_rh_access_in_company = MagicMock(return_value=True)
        request = MagicMock()
        request.employee_ids = ["emp-1"]
        request.year = 2019
        request.month = 3
        request.week_configs = {1: _make_week_config()}

        with pytest.raises(ScheduleAppError) as exc_info:
            commands.apply_schedule_model(request, user)
        assert exc_info.value.status_code == 400
        assert "année" in exc_info.value.message.lower()

    def test_success_updates_existing_schedule(self):
        """Ligne existante → update_planned_calendar_only appelé."""
        user = MagicMock()
        user.active_company_id = "comp-1"
        user.has_rh_access_in_company = MagicMock(return_value=True)
        request = MagicMock()
        request.employee_ids = ["emp-1"]
        request.year = 2025
        request.month = 3
        request.week_configs = {
            1: _make_week_config(8.0, 0.0),
            2: _make_week_config(8.0, 0.0),
            3: _make_week_config(8.0, 0.0),
            4: _make_week_config(8.0, 0.0),
            5: _make_week_config(8.0, 0.0),
        }

        with (
            patch(
                "app.modules.schedules.application.commands.employee_company_reader",
            ) as reader,
            patch(
                "app.modules.schedules.application.commands.domain_rules.is_forfait_jour",
                return_value=False,
            ),
            patch(
                "app.modules.schedules.application.commands.schedule_repository",
            ) as repo,
        ):
            reader.get_company_and_statut.return_value = ("comp-1", "employé")
            repo.exists_schedule.return_value = True

            result = commands.apply_schedule_model(request, user)

        assert result["status"] == "success"
        assert result["details"]["employee_count"] == 1
        assert result["details"]["year"] == 2025
        assert result["details"]["month"] == 3
        repo.update_planned_calendar_only.assert_called_once()
        repo.insert_schedule.assert_not_called()

    def test_success_inserts_new_schedule(self):
        """Ligne inexistante → insert_schedule appelé."""
        user = MagicMock()
        user.active_company_id = "comp-1"
        user.has_rh_access_in_company = MagicMock(return_value=True)
        request = MagicMock()
        request.employee_ids = ["emp-2"]
        request.year = 2025
        request.month = 4
        request.week_configs = {
            1: _make_week_config(7.0, 0.0),
            2: _make_week_config(7.0, 0.0),
            3: _make_week_config(7.0, 0.0),
            4: _make_week_config(7.0, 0.0),
            5: _make_week_config(7.0, 0.0),
        }

        with (
            patch(
                "app.modules.schedules.application.commands.employee_company_reader",
            ) as reader,
            patch(
                "app.modules.schedules.application.commands.domain_rules.is_forfait_jour",
                return_value=True,
            ),
            patch(
                "app.modules.schedules.application.commands.schedule_repository",
            ) as repo,
        ):
            reader.get_company_and_statut.return_value = (
                "comp-1",
                "cadre forfait jour",
            )
            repo.exists_schedule.return_value = False

            result = commands.apply_schedule_model(request, user)

        assert result["status"] == "success"
        repo.insert_schedule.assert_called_once()
        call_args = repo.insert_schedule.call_args[0]
        assert call_args[0] == "emp-2"
        assert call_args[1] == "comp-1"
        assert call_args[2] == 2025
        assert call_args[3] == 4
        assert "calendrier_prevu" in call_args[4]
