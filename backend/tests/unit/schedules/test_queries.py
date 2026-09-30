"""
Tests unitaires des queries du module schedules (application/queries.py).

Repositories et providers mockés. Pas de DB ni HTTP.
"""

from unittest.mock import patch

import pytest

from app.modules.schedules.application import queries
from app.modules.schedules.application.exceptions import ScheduleAppError
from app.modules.schedules.schemas.responses import CumulsResponse


# --- get_employee_calendar ---


class TestGetEmployeeCalendar:
    """Query get_employee_calendar (fichiers moteur de paie)."""

    def test_returns_planned_and_actual_from_file_provider(self):
        """Délègue au file_calendar_provider, retourne planned et actual."""
        planned = [{"day": 1, "type": "work", "hours": 8}]
        actual = [{"day": 1, "hours": 7.5}]
        with (
            patch(
                "app.modules.schedules.application.queries.employee_company_reader",
            ) as reader,
            patch(
                "app.modules.schedules.application.queries.file_calendar_provider",
            ) as file_provider,
        ):
            reader.get_employee_folder_name.return_value = "Dupont_Jean"
            file_provider.read_planned_calendar.return_value = planned
            file_provider.read_actual_hours.return_value = actual

            result = queries.get_employee_calendar("emp-1", 2025, 3)

        assert result == {"planned": planned, "actual": actual}
        file_provider.read_planned_calendar.assert_called_once_with(
            "Dupont_Jean", 2025, 3
        )
        file_provider.read_actual_hours.assert_called_once_with("Dupont_Jean", 2025, 3)

    def test_raises_schedule_app_error_when_employee_not_found(self):
        """Employé inconnu → ScheduleAppError not_found."""
        with patch(
            "app.modules.schedules.application.queries.employee_company_reader",
        ) as reader:
            from app.modules.schedules.domain.exceptions import ScheduleNotFoundError

            reader.get_employee_folder_name.side_effect = ScheduleNotFoundError(
                "Employé non trouvé"
            )

            with pytest.raises(ScheduleAppError) as exc_info:
                queries.get_employee_calendar("emp-unknown", 2025, 3)
        assert exc_info.value.code == "not_found"
        assert exc_info.value.status_code == 404


# --- get_planned_calendar ---


class TestGetPlannedCalendar:
    """Query get_planned_calendar (table employee_schedules)."""

    def test_returns_year_month_and_calendrier_prevu(self):
        """Repository retourne planned_calendar → extraction et retour structuré."""
        db_planned = {
            "calendrier_prevu": [{"jour": 1, "type": "work", "heures_prevues": 8}]
        }
        with patch(
            "app.modules.schedules.application.queries.schedule_repository",
        ) as repo:
            repo.get_planned_calendar.return_value = db_planned

            result = queries.get_planned_calendar("emp-1", 2025, 3)

        assert result["year"] == 2025
        assert result["month"] == 3
        assert result["calendrier_prevu"] == [
            {"jour": 1, "type": "work", "heures_prevues": 8}
        ]
        repo.get_planned_calendar.assert_called_once_with("emp-1", 2025, 3)

    def test_returns_empty_calendar_when_repository_returns_none(self):
        """Repository retourne None → calendrier_prevu vide."""
        with patch(
            "app.modules.schedules.application.queries.schedule_repository",
        ) as repo:
            repo.get_planned_calendar.return_value = None

            result = queries.get_planned_calendar("emp-1", 2025, 3)

        assert result["year"] == 2025
        assert result["month"] == 3
        assert result["calendrier_prevu"] == []


# --- get_actual_hours ---


class TestGetActualHours:
    """Query get_actual_hours (table employee_schedules)."""

    def test_returns_year_month_and_calendrier_reel(self):
        """Repository retourne actual_hours → extraction et retour structuré."""
        db_actual = {"calendrier_reel": [{"jour": 1, "heures_faites": 7.5}]}
        with patch(
            "app.modules.schedules.application.queries.schedule_repository",
        ) as repo:
            repo.get_actual_hours.return_value = db_actual

            result = queries.get_actual_hours("emp-1", 2025, 3)

        assert result["year"] == 2025
        assert result["month"] == 3
        assert result["calendrier_reel"] == [{"jour": 1, "heures_faites": 7.5}]
        repo.get_actual_hours.assert_called_once_with("emp-1", 2025, 3)

    def test_returns_empty_calendar_when_repository_returns_none(self):
        """Repository retourne None → calendrier_reel vide."""
        with patch(
            "app.modules.schedules.application.queries.schedule_repository",
        ) as repo:
            repo.get_actual_hours.return_value = None

            result = queries.get_actual_hours("emp-1", 2025, 3)

        assert result["calendrier_reel"] == []


# --- get_my_current_cumuls ---


class TestGetMyCurrentCumuls:
    """Query get_my_current_cumuls."""

    def test_returns_cumuls_response_when_row_exists(self):
        """Dernière ligne cumuls présente → CumulsResponse avec periode et cumuls."""
        row = {
            "cumuls": {
                "periode": {"annee_en_cours": 2025, "dernier_mois_calcule": 3},
                "cumuls": {
                    "brut_total": 3000.0,
                    "heures_remunerees": 151.67,
                },
            }
        }
        with (
            patch(
                "app.modules.schedules.application.queries.schedule_repository",
            ) as repo,
            patch(
                "app.modules.schedules.application.queries.row_to_cumuls",
                return_value=row["cumuls"],
            ),
        ):
            repo.get_latest_cumuls_row.return_value = row
            result = queries.get_my_current_cumuls("emp-1")

        assert isinstance(result, CumulsResponse)
        assert result.periode is not None
        assert result.cumuls is not None
        assert result.cumuls.brut_total == 3000.0
        assert result.cumuls.heures_remunerees == 151.67

    def test_returns_empty_cumuls_when_no_row(self):
        """Aucune ligne cumuls → CumulsResponse(periode=None, cumuls=None)."""
        with (
            patch(
                "app.modules.schedules.application.queries.schedule_repository",
            ) as repo,
            patch(
                "app.modules.schedules.application.queries.row_to_cumuls",
                return_value=None,
            ),
        ):
            repo.get_latest_cumuls_row.return_value = None
            result = queries.get_my_current_cumuls("emp-1")

        assert result.periode is None
        assert result.cumuls is None

    def test_returns_empty_cumuls_when_row_has_no_cumuls_dict(self):
        """Ligne sans cumuls dict valide → CumulsResponse(periode=None, cumuls=None)."""
        with (
            patch(
                "app.modules.schedules.application.queries.schedule_repository",
            ) as repo,
            patch(
                "app.modules.schedules.application.queries.row_to_cumuls",
                return_value="not_a_dict",
            ),
        ):
            repo.get_latest_cumuls_row.return_value = {"cumuls": None}
            result = queries.get_my_current_cumuls("emp-1")

        assert result.periode is None
        assert result.cumuls is None


# --- get_actual_hours : jours_en_conflit (heures saisies un jour d'arrêt) ---


class TestGetActualHoursJoursEnConflit:
    """La lecture des heures réelles dit quels jours portent des heures alors que
    le prévu est un arrêt ou une absence : la règle vit dans `conflits_arret`."""

    @staticmethod
    def _lire(prevu, reel, arrets=None, arrets_en_panne=False):
        with (
            patch(
                "app.modules.schedules.application.queries.schedule_repository",
            ) as repo,
            patch(
                "app.modules.schedules.application.queries.arrets_valides_reader",
            ) as lecteur,
        ):
            repo.get_actual_hours.return_value = {"calendrier_reel": reel}
            repo.get_planned_calendar.return_value = {"calendrier_prevu": prevu}
            if arrets_en_panne:
                lecteur.par_salarie.side_effect = RuntimeError("réseau")
            else:
                lecteur.par_salarie.return_value = {"emp-1": arrets or []}
            return queries.get_actual_hours("emp-1", 2026, 9), lecteur

    def test_heures_un_jour_d_arret_sont_signalees(self):
        prevu = [
            {"jour": 7, "type": "arret_maladie", "heures_prevues": 0},
            {"jour": 8, "type": "travail", "heures_prevues": 8},
        ]
        reel = [
            {"jour": 7, "type": "travail", "heures_faites": 9.0},
            {"jour": 8, "type": "travail", "heures_faites": 8.0},
        ]
        resultat, _ = self._lire(prevu, reel)
        assert resultat["jours_en_conflit"] == [7]

    def test_heures_nulles_sur_un_arret_ne_sont_pas_un_conflit(self):
        prevu = [{"jour": 7, "type": "arret_maladie", "heures_prevues": 0}]
        reel = [{"jour": 7, "type": "arret_maladie", "heures_faites": 0}]
        resultat, _ = self._lire(prevu, reel)
        assert resultat["jours_en_conflit"] == []

    def test_weekend_couvert_par_un_arret_valide(self):
        # 5 septembre 2026 : samedi, couvert par un arrêt validé.
        prevu = [{"jour": 5, "type": "weekend", "heures_prevues": 0}]
        reel = [{"jour": 5, "type": "weekend", "heures_faites": 4.0}]
        arrets = [
            {
                "type": "arret_maladie",
                "status": "validated",
                "selected_days": ["2026-09-04", "2026-09-05", "2026-09-07"],
            }
        ]
        resultat, _ = self._lire(prevu, reel, arrets)
        assert resultat["jours_en_conflit"] == [5]

    def test_arrets_illisibles_en_lecture_ecran_la_regle_du_type_seule_s_applique(self):
        prevu = [
            {"jour": 5, "type": "weekend", "heures_prevues": 0},
            {"jour": 7, "type": "conges_payes", "heures_prevues": 0},
        ]
        reel = [
            {"jour": 5, "type": "weekend", "heures_faites": 4.0},
            {"jour": 7, "type": "conges_payes", "heures_faites": 8.0},
        ]
        resultat, _ = self._lire(prevu, reel, arrets_en_panne=True)
        assert resultat["jours_en_conflit"] == [7]

    def test_sans_heures_sur_weekend_les_arrets_ne_sont_pas_lus(self):
        prevu = [{"jour": 7, "type": "arret_maladie", "heures_prevues": 0}]
        reel = [{"jour": 7, "type": "arret_maladie", "heures_faites": 9.0}]
        _, lecteur = self._lire(prevu, reel)
        lecteur.par_salarie.assert_not_called()

    def test_les_autres_champs_sont_inchanges(self):
        resultat, _ = self._lire([], [{"jour": 1, "heures_faites": 7.5}])
        assert resultat["year"] == 2026 and resultat["month"] == 9
        assert resultat["calendrier_reel"] == [{"jour": 1, "heures_faites": 7.5}]
        assert resultat["jours_en_conflit"] == []


class TestRouteActualHoursExposeLesConflits:
    """Le champ traverse le modèle de réponse de la route : l'écran le reçoit."""

    def test_get_actual_hours_rend_jours_en_conflit(self):
        from fastapi.testclient import TestClient

        from app.core.security import get_current_user
        from app.main import app
        from app.modules.users.schemas.responses import CompanyAccess, User

        user = User(
            id="user-rh-1",
            email="rh@test.co",
            first_name="R",
            last_name="H",
            is_platform_admin=False,
            is_group_admin=False,
            accessible_companies=[
                CompanyAccess(company_id="co-1", company_name="Co", role="rh", is_primary=True)
            ],
            active_company_id="co-1",
        )
        app.dependency_overrides[get_current_user] = lambda: user
        try:
            with (
                patch(
                    "app.modules.schedules.api.router.access_control_service.require_employee_access"
                ),
                patch(
                    "app.modules.schedules.api.router.queries.get_actual_hours",
                    return_value={
                        "year": 2026,
                        "month": 9,
                        "calendrier_reel": [{"jour": 7, "heures_faites": 9.0, "type": "travail"}],
                        "jours_en_conflit": [7],
                    },
                ),
            ):
                reponse = TestClient(app).get(
                    "/api/employees/emp-1/actual-hours", params={"year": 2026, "month": 9}
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert reponse.status_code == 200
        assert reponse.json()["jours_en_conflit"] == [7]
