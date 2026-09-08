"""Routes de la fenêtre des variables : câblage, droits, normalisation."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

TEST_COMPANY_ID = "company-periode-variables"


def _rh_user():
    from app.modules.users.schemas.responses import CompanyAccess, User

    return User(
        id="user-rh-periode-variables",
        email="rh@periode.test",
        first_name="RH",
        last_name="Variables",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=TEST_COMPANY_ID,
                company_name="Test Co",
                role="rh",
                is_primary=True,
            )
        ],
        active_company_id=TEST_COMPANY_ID,
    )


class TestLectureFenetre:
    def test_sans_auth_401(self, client: TestClient):
        reponse = client.get(
            "/api/payroll-variables/period", params={"year": 2026, "month": 7}
        )
        assert reponse.status_code == 401

    def test_renvoie_la_fenetre_et_le_mois_civil(self, client: TestClient):
        from app.core.security import get_current_user
        from app.main import app

        apercu = {
            "debut": "2026-06-22",
            "fin": "2026-07-26",
            "origine": "regle",
            "semaines": [26, 27, 28, 29, 30],
            "mois_civil": ["2026-07-01", "2026-07-31"],
            "report_debut": "2026-07-27",
        }
        with patch(
            "app.modules.payroll.application.periode_variables_service.apercu_fenetre",
            return_value=apercu,
        ):
            app.dependency_overrides[get_current_user] = _rh_user
            try:
                reponse = client.get(
                    "/api/payroll-variables/period",
                    params={"year": 2026, "month": 7},
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert reponse.status_code == 200
        assert reponse.json() == apercu

    def test_une_autre_societe_est_refusee(self, client: TestClient):
        from app.core.security import get_current_user
        from app.main import app

        app.dependency_overrides[get_current_user] = _rh_user
        try:
            reponse = client.get(
                "/api/payroll-variables/period",
                params={
                    "company_id": "00000000-0000-0000-0000-000000000000",
                    "year": 2026,
                    "month": 7,
                },
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert reponse.status_code == 403


class TestEnregistrementFenetre:
    def test_la_date_saisie_est_transmise_au_service(self, client: TestClient):
        """Gaëlle arrête au samedi 25/07 ; c'est le service qui normalise."""
        from app.core.security import get_current_user
        from app.main import app

        apercu = {
            "debut": "2026-06-22",
            "fin": "2026-07-26",
            "origine": "manuel",
            "semaines": [26, 27, 28, 29, 30],
            "mois_civil": ["2026-07-01", "2026-07-31"],
            "report_debut": "2026-07-27",
        }
        with patch(
            "app.modules.payroll.application.periode_variables_service.enregistrer_fenetre_variables"
        ) as enregistrer, patch(
            "app.modules.payroll.application.periode_variables_service.apercu_fenetre",
            return_value=apercu,
        ):
            app.dependency_overrides[get_current_user] = _rh_user
            try:
                reponse = client.put(
                    "/api/payroll-variables/period",
                    json={"year": 2026, "month": 7, "fin": "2026-07-25"},
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)

        assert reponse.status_code == 200
        assert reponse.json()["fin"] == "2026-07-26"
        assert enregistrer.call_args[0][3] == date(2026, 7, 25)

    def test_une_fenetre_impossible_renvoie_422(self, client: TestClient):
        from app.core.security import get_current_user
        from app.main import app

        with patch(
            "app.modules.payroll.application.periode_variables_service.enregistrer_fenetre_variables",
            side_effect=ValueError("Fin de fenêtre antérieure à son début."),
        ):
            app.dependency_overrides[get_current_user] = _rh_user
            try:
                reponse = client.put(
                    "/api/payroll-variables/period",
                    json={"year": 2026, "month": 7, "fin": "2026-06-01"},
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert reponse.status_code == 422
        assert "antérieure" in reponse.json()["detail"]


class TestListeDesSurcharges:
    def test_liste_les_mois_corriges_a_la_main(self, client: TestClient):
        from app.core.security import get_current_user
        from app.main import app

        with patch(
            "app.modules.payroll.infrastructure.variable_periods_repository.list_variable_periods",
            return_value=[
                {"month": 7, "start_date": "2026-06-22", "end_date": "2026-07-19"}
            ],
        ):
            app.dependency_overrides[get_current_user] = _rh_user
            try:
                reponse = client.get(
                    "/api/payroll-variables/periods", params={"year": 2026}
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert reponse.status_code == 200
        assert reponse.json() == [
            {"month": 7, "debut": "2026-06-22", "fin": "2026-07-19"}
        ]
