"""Correction en un clic : effacer les heures saisies sur des jours d'arrêt.

`POST /api/employees/{id}/actual-hours/effacer-jours` `{year, month, jours}` remet
chaque jour du réel au type du prévu, à 0 h. Il ne touche qu'aux jours d'arrêt
ou d'absence non travaillée : un jour travaillé ne s'efface pas par ce chemin.
Réservé aux RH de la société du salarié, journalisé. Supabase est moqué.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.schedules.application import commands
from app.modules.schedules.application.exceptions import ScheduleAppError

pytestmark = pytest.mark.unit

_COMMANDS = "app.modules.schedules.application.commands"


def _prevu_septembre() -> dict:
    return {
        "calendrier_prevu": [
            {"jour": 7, "type": "arret_maladie", "heures_prevues": 0, "origine": "absence"},
            {"jour": 8, "type": "arret_maladie", "heures_prevues": 0, "origine": "absence"},
            {"jour": 9, "type": "travail", "heures_prevues": 7.0},
            {"jour": 10, "type": "conges_payes", "heures_prevues": 0, "quotite_absence": 0.5},
        ]
    }


def _reel_septembre() -> dict:
    return {
        "periode": {"annee": 2026, "mois": 9},
        "calendrier_reel": [
            {"jour": 7, "type": "travail", "heures_faites": 9.0},
            {"jour": 8, "type": "travail", "heures_faites": 8.0},
            {"jour": 9, "type": "travail", "heures_faites": 7.0},
            {"jour": 10, "type": "travail", "heures_faites": 4.0},
        ],
    }


def _effacer(jours: list[int], *, reel: dict | None = None):
    with (
        patch(
            f"{_COMMANDS}.get_employee_company_and_statut",
            return_value=("co-1", "Non-Cadre"),
        ),
        patch(f"{_COMMANDS}.schedule_repository") as repo,
        patch(f"{_COMMANDS}.logger") as log,
    ):
        repo.get_planned_calendar.return_value = _prevu_septembre()
        repo.get_actual_hours.return_value = reel if reel is not None else _reel_septembre()
        try:
            resultat = commands.effacer_heures_des_jours(
                "emp-1", 2026, 9, jours, auteur="user-rh-1"
            )
        except ScheduleAppError as exc:
            return exc, repo, log
        return resultat, repo, log


class TestEffacerHeuresDesJours:
    def test_les_jours_d_arret_repassent_au_type_du_prevu_a_zero_heure(self):
        resultat, repo, _ = _effacer([7, 8])

        repo.upsert_schedule.assert_called_once()
        args, kwargs = repo.upsert_schedule.call_args
        assert args == ("emp-1", "co-1", 2026, 9)
        assert kwargs["actual_hours"]["calendrier_reel"] == [
            {"jour": 7, "type": "arret_maladie", "heures_faites": 0},
            {"jour": 8, "type": "arret_maladie", "heures_faites": 0},
            {"jour": 9, "type": "travail", "heures_faites": 7.0},
            {"jour": 10, "type": "travail", "heures_faites": 4.0},
        ]
        assert kwargs["actual_hours"]["periode"] == {"annee": 2026, "mois": 9}
        assert "planned_calendar" not in kwargs
        assert resultat == {
            "status": "success",
            "year": 2026,
            "month": 9,
            "jours": [7, 8],
            "message": "Heures effacées les 7 et 8 septembre.",
        }

    def test_un_jour_travaille_ne_s_efface_pas_et_rien_n_est_ecrit(self):
        erreur, repo, _ = _effacer([7, 9])

        assert isinstance(erreur, ScheduleAppError)
        assert erreur.status_code == 422
        assert erreur.message == (
            "Le 9 septembre n'est ni un jour d'arrêt ni une absence au planning : "
            "ses heures ne sont pas effacées. Rien n'a été modifié."
        )
        repo.upsert_schedule.assert_not_called()

    def test_une_demi_journee_de_conge_ne_s_efface_pas(self):
        """L'autre demi-journée a été travaillée : ses heures sont vraies."""
        erreur, repo, _ = _effacer([10])

        assert isinstance(erreur, ScheduleAppError)
        assert erreur.status_code == 422
        repo.upsert_schedule.assert_not_called()

    def test_un_jour_hors_du_mois_est_refuse(self):
        erreur, repo, _ = _effacer([31])

        assert isinstance(erreur, ScheduleAppError)
        assert erreur.status_code == 422
        repo.upsert_schedule.assert_not_called()

    def test_effacer_deux_fois_ne_change_rien(self):
        deja = _reel_septembre()
        deja["calendrier_reel"][0] = {"jour": 7, "type": "arret_maladie", "heures_faites": 0}
        resultat, repo, _ = _effacer([7], reel=deja)

        assert resultat["jours"] == [7]
        calendrier = repo.upsert_schedule.call_args.kwargs["actual_hours"]["calendrier_reel"]
        assert calendrier[0] == {"jour": 7, "type": "arret_maladie", "heures_faites": 0}

    def test_l_effacement_est_journalise_avec_les_heures_d_avant(self):
        _, _, log = _effacer([7, 8])

        log.info.assert_called_once()
        texte = log.info.call_args.args[0] % log.info.call_args.args[1:]
        assert "emp-1" in texte and "09/2026" in texte and "user-rh-1" in texte
        assert "'jour': 7" in texte and "'heures_avant': 9.0" in texte
        assert "'type_avant': 'travail'" in texte


class TestRouteEffacerJours:
    URL = "/api/employees/emp-1/actual-hours/effacer-jours"

    def _rh(self, societe: str = "co-1"):
        from app.modules.users.schemas.responses import CompanyAccess, User

        return User(
            id="user-rh-1",
            email="rh@test.co",
            first_name="R",
            last_name="H",
            is_platform_admin=False,
            is_group_admin=False,
            accessible_companies=[
                CompanyAccess(company_id=societe, company_name="Co", role="rh", is_primary=True)
            ],
            active_company_id=societe,
        )

    def _post(self, client: TestClient, corps: dict, user):
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: user
        try:
            return client.post(self.URL, json=corps)
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_la_route_efface_et_rend_le_resultat(self, client: TestClient):
        attendu = {
            "status": "success",
            "year": 2026,
            "month": 9,
            "jours": [7, 8],
            "message": "Heures effacées les 7 et 8 septembre.",
        }
        with (
            patch(
                "app.modules.schedules.api.router.access_control_service.require_employee_access"
            ) as garde,
            patch(f"{_COMMANDS}.effacer_heures_des_jours", return_value=attendu) as effacer,
        ):
            response = self._post(
                client, {"year": 2026, "month": 9, "jours": [8, 7]}, self._rh()
            )

        assert response.status_code == 200
        assert response.json() == attendu
        garde.assert_called_once()
        assert garde.call_args.args[1:] == ("co-1", "schedules.update", "emp-1")
        effacer.assert_called_once_with("emp-1", 2026, 9, [8, 7], auteur="user-rh-1")

    def test_une_rh_d_une_autre_societe_est_refusee(self, client: TestClient):
        with (
            patch("app.modules.access_control.application.service.providers") as providers,
            patch(f"{_COMMANDS}.effacer_heures_des_jours") as effacer,
        ):
            providers.get_employee_company_id.return_value = "co-autre"
            response = self._post(
                client, {"year": 2026, "month": 9, "jours": [7]}, self._rh("co-1")
            )

        assert response.status_code == 404
        effacer.assert_not_called()

    def test_le_refus_du_metier_arrive_en_clair(self, client: TestClient):
        with (
            patch(
                "app.modules.schedules.api.router.access_control_service.require_employee_access"
            ),
            patch(
                f"{_COMMANDS}.effacer_heures_des_jours",
                side_effect=ScheduleAppError("validation", "Le 9 septembre…", status_code=422),
            ),
        ):
            response = self._post(client, {"year": 2026, "month": 9, "jours": [9]}, self._rh())

        assert response.status_code == 422
        assert response.json()["detail"] == "Le 9 septembre…"

    @pytest.mark.parametrize(
        "corps",
        [
            {"year": 2026, "month": 9, "jours": []},
            {"year": 2026, "month": 13, "jours": [7]},
            {"year": 2026, "month": 9, "jours": [0]},
        ],
    )
    def test_un_corps_invalide_est_refuse(self, client: TestClient, corps):
        with (
            patch(
                "app.modules.schedules.api.router.access_control_service.require_employee_access"
            ),
            patch(f"{_COMMANDS}.effacer_heures_des_jours") as effacer,
        ):
            response = self._post(client, corps, self._rh())

        assert response.status_code == 422
        effacer.assert_not_called()
