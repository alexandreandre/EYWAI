"""
Tests de câblage (wiring) du module exports : injection des dépendances et flux bout en bout.

Vérifie que le router exports est bien monté, que get_current_user et get_active_company_id
sont injectés correctement, et qu'un flux complet (preview → service → réponse) fonctionne.
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.users.schemas.responses import User, CompanyAccess


pytestmark = pytest.mark.integration

TEST_COMPANY_ID = "company-wiring-test"
TEST_USER_ID = "user-wiring-test"


def _make_user():
    """Utilisateur de test pour les overrides."""
    access = CompanyAccess(
        company_id=TEST_COMPANY_ID,
        company_name="Wiring Test Co",
        role="rh",
        is_primary=True,
    )
    return User(
        id=TEST_USER_ID,
        email="wiring@test.com",
        first_name="Wiring",
        last_name="Test",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[access],
        active_company_id=TEST_COMPANY_ID,
    )


class TestExportsRouterMounted:
    """Vérification que le router exports est monté et répond sur le bon préfixe."""

    def test_exports_routes_are_registered(self, client: TestClient):
        """Les routes /api/exports/* existent (405 ou 401 selon méthode/auth, pas 404)."""
        # GET sans auth → 401 (pas 404)
        r_get = client.get("/api/exports/history")
        assert r_get.status_code != 404, "GET /api/exports/history devrait exister (401 sans auth)"
        assert r_get.status_code == 401

        # POST preview sans auth → 401
        r_preview = client.post(
            "/api/exports/preview",
            json={"export_type": "journal_paie", "period": "2025-01"},
        )
        assert r_preview.status_code != 404
        assert r_preview.status_code == 401

    def test_unknown_export_path_returns_404(self, client: TestClient):
        """Une route inexistante sous /api/exports renvoie 404."""
        response = client.get("/api/exports/unknown-route")
        assert response.status_code == 404


class TestExportsDependencyInjection:
    """Vérification que get_current_user et get_active_company_id sont bien injectés."""

    def test_with_overrides_preview_reaches_service(self, client: TestClient):
        """Avec dependency_overrides, la requête atteint le service et retourne 200."""
        from app.core.security import get_current_user
        from app.modules.exports.api.dependencies import get_active_company_id

        app.dependency_overrides[get_current_user] = _make_user
        app.dependency_overrides[get_active_company_id] = lambda: TEST_COMPANY_ID

        try:
            with patch(
                "app.modules.exports.application.service.preview_export",
                return_value={
                    "export_type": "journal_paie",
                    "period": "2025-01",
                    "employees_count": 0,
                    "totals": {"employees_count": 0},
                    "anomalies": [],
                    "warnings": [],
                    "can_generate": True,
                },
            ) as mock_preview:
                response = client.post(
                    "/api/exports/preview",
                    json={"export_type": "journal_paie", "period": "2025-01"},
                )
                assert response.status_code == 200
                mock_preview.assert_called_once()
                call_kw = mock_preview.call_args
                assert call_kw[0][0] == TEST_COMPANY_ID
                assert call_kw[0][1].export_type == "journal_paie"
                assert call_kw[0][1].period == "2025-01"
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_active_company_id, None)

    def test_with_overrides_get_history_reaches_service(self, client: TestClient):
        """GET /history avec overrides appelle le service avec le bon company_id."""
        from app.core.security import get_current_user
        from app.modules.exports.api.dependencies import get_active_company_id

        app.dependency_overrides[get_current_user] = _make_user
        app.dependency_overrides[get_active_company_id] = lambda: TEST_COMPANY_ID

        try:
            with patch(
                "app.modules.exports.application.service.get_export_history",
                return_value={"exports": [], "total": 0},
            ) as mock_history:
                response = client.get("/api/exports/history")
                assert response.status_code == 200
                mock_history.assert_called_once()
                assert mock_history.call_args[0][0] == TEST_COMPANY_ID
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_active_company_id, None)


class TestExportsEndToEndFlow:
    """Flux bout en bout : router → service → (mock) → réponse HTTP."""

    def test_preview_value_error_becomes_400(self, client: TestClient):
        """Une ValueError levée par le service est traduite en 400 par le router."""
        from app.core.security import get_current_user
        from app.modules.exports.api.dependencies import get_active_company_id

        app.dependency_overrides[get_current_user] = _make_user
        app.dependency_overrides[get_active_company_id] = lambda: TEST_COMPANY_ID

        try:
            with patch(
                "app.modules.exports.application.service.preview_export",
                side_effect=ValueError("Type d'export 'inconnu' non implémenté"),
            ):
                response = client.post(
                    "/api/exports/preview",
                    json={"export_type": "journal_paie", "period": "2025-01"},
                )
                assert response.status_code == 400
                assert "detail" in response.json()
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_active_company_id, None)

    def test_download_value_error_not_found_becomes_404(self, client: TestClient):
        """ValueError('Export non trouvé') du service → 404 en HTTP."""
        from app.core.security import get_current_user
        from app.modules.exports.api.dependencies import get_active_company_id

        app.dependency_overrides[get_current_user] = _make_user
        app.dependency_overrides[get_active_company_id] = lambda: TEST_COMPANY_ID

        try:
            with patch(
                "app.modules.exports.application.service.get_export_download_url",
                side_effect=ValueError("Export non trouvé"),
            ):
                response = client.get("/api/exports/download/exp-123")
                assert response.status_code == 404
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_active_company_id, None)
