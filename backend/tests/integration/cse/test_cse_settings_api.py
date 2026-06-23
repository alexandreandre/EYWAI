"""Tests API paramètres CSE entreprise (GET/PUT /api/cse/settings)."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.core.security import get_current_user
from tests.integration.cse.test_api import PREFIX, _make_rh_user

MODULE = "app.modules.cse.api.router"


class TestCseSettingsAPI:
    def test_get_settings_200(self, client: TestClient):
        from app.modules.cse.schemas.responses import CompanyCseSettings

        settings = CompanyCseSettings(company_id="co-1", cse_status="carence")
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.cse.application.cse_settings.get_company_cse_settings",
                return_value=settings,
            ):
                response = client.get(f"{PREFIX}/settings")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert response.json()["cse_status"] == "carence"

    def test_put_settings_200(self, client: TestClient):
        from app.modules.cse.schemas.responses import CompanyCseSettings

        saved = CompanyCseSettings(
            company_id="co-1",
            cse_status="carence",
            carence_valid_until="2027-09-06",
        )
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.cse.application.cse_settings.save_company_cse_settings",
                return_value=saved,
            ):
                response = client.put(
                    f"{PREFIX}/settings",
                    json={
                        "cse_status": "carence",
                        "carence_valid_until": "2027-09-06",
                    },
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert response.json()["carence_valid_until"] == "2027-09-06"
