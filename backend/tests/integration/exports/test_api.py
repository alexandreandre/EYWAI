"""
Tests d'intégration HTTP des routes du module exports.

Préfixe des routes : /api/exports.
Utilise : client (TestClient). Pour les routes protégées, dependency_overrides pour
get_current_user et get_active_company_id ; le service peut être mocké pour éviter DB/storage.
Fixture documentée : exports_headers — si conftest fournit des en-têtes (Authorization + X-Active-Company),
les tests peuvent les utiliser pour des appels E2E avec token réel.
"""

from datetime import datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.users.schemas.responses import User, CompanyAccess


pytestmark = pytest.mark.integration

TEST_COMPANY_ID = "company-exports-test"
TEST_USER_ID = "user-exports-test"


def _make_rh_user():
    """Utilisateur de test avec droits RH et active_company_id pour les exports."""
    access = CompanyAccess(
        company_id=TEST_COMPANY_ID,
        company_name="Test Exports Co",
        role="rh",
        is_primary=True,
    )
    return User(
        id=TEST_USER_ID,
        email="exports@test.com",
        first_name="Exports",
        last_name="Test",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[access],
        active_company_id=TEST_COMPANY_ID,
    )


class TestExportsUnauthenticated:
    """Sans token : toutes les routes protégées renvoient 401."""

    def test_post_preview_returns_401_without_auth(self, client: TestClient):
        """POST /api/exports/preview sans auth → 401."""
        response = client.post(
            "/api/exports/preview",
            json={"export_type": "journal_paie", "period": "2025-01"},
        )
        assert response.status_code == 401

    def test_post_generate_returns_401_without_auth(self, client: TestClient):
        """POST /api/exports/generate sans auth → 401."""
        response = client.post(
            "/api/exports/generate",
            json={"export_type": "journal_paie", "period": "2025-01"},
        )
        assert response.status_code == 401

    def test_get_history_returns_401_without_auth(self, client: TestClient):
        """GET /api/exports/history sans auth → 401."""
        response = client.get("/api/exports/history")
        assert response.status_code == 401

    def test_get_download_returns_401_without_auth(self, client: TestClient):
        """GET /api/exports/download/{export_id} sans auth → 401."""
        response = client.get("/api/exports/download/exp-123")
        assert response.status_code == 401


class TestExportsActiveCompanyRequired:
    """X-Active-Company requis : sans header, 400 (après auth)."""

    def test_preview_without_x_active_company_returns_400(self, client: TestClient):
        """Avec auth mais sans X-Active-Company → 400 (get_active_company_id lève HTTPException)."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = _make_rh_user
        # Ne pas override get_active_company_id : il attend le header
        try:
            response = client.post(
                "/api/exports/preview",
                json={"export_type": "journal_paie", "period": "2025-01"},
                headers={"Authorization": "Bearer fake-token"},
            )
            # Sans override, get_active_company_id lit le header ; sans header → 400
            assert response.status_code == 400
            data = response.json()
            assert "X-Active-Company" in data.get("detail", "")
        finally:
            app.dependency_overrides.pop(get_current_user, None)


class TestExportsWithRhUser:
    """Avec utilisateur RH et company_id injectés (dependency_overrides) et service mocké."""

    @pytest.fixture
    def client_with_exports_auth(self, client: TestClient):
        """Client avec get_current_user et get_active_company_id overridés."""
        from app.core.security import get_current_user
        from app.modules.exports.api.dependencies import get_active_company_id

        app.dependency_overrides[get_current_user] = _make_rh_user
        app.dependency_overrides[get_active_company_id] = lambda: TEST_COMPANY_ID
        try:
            yield client
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_active_company_id, None)

    def test_post_preview_returns_200_and_preview_shape(
        self, client_with_exports_auth: TestClient
    ):
        """POST /api/exports/preview avec auth et company → 200 et structure ExportPreviewResponse."""
        mock_response = {
            "export_type": "journal_paie",
            "period": "2025-01",
            "employees_count": 2,
            "totals": {"employees_count": 2, "total_brut": 10000.0},
            "anomalies": [],
            "warnings": [],
            "can_generate": True,
        }
        with patch(
            "app.modules.exports.application.service.preview_export",
            return_value=mock_response,
        ):
            response = client_with_exports_auth.post(
                "/api/exports/preview",
                json={"export_type": "journal_paie", "period": "2025-01"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["export_type"] == "journal_paie"
        assert data["period"] == "2025-01"
        assert "employees_count" in data
        assert "totals" in data
        assert "can_generate" in data

    def test_post_preview_unsupported_type_returns_400(
        self, client_with_exports_auth: TestClient
    ):
        """POST /api/exports/preview avec type non supporté → 400."""
        with patch(
            "app.modules.exports.application.service.preview_export",
            side_effect=ValueError("Type d'export 'inconnu' non implémenté"),
        ):
            response = client_with_exports_auth.post(
                "/api/exports/preview",
                json={"export_type": "journal_paie", "period": "2025-01"},
            )
        assert response.status_code == 400
        assert "detail" in response.json()

    def test_post_preview_invalid_period_returns_422(
        self, client_with_exports_auth: TestClient
    ):
        """POST /api/exports/preview avec période invalide (format) → 422."""
        response = client_with_exports_auth.post(
            "/api/exports/preview",
            json={"export_type": "journal_paie", "period": "invalid"},
        )
        assert response.status_code == 422

    def test_post_generate_returns_200_and_response_shape(
        self, client_with_exports_auth: TestClient
    ):
        """POST /api/exports/generate avec auth → 200 et export_id, files, report."""
        mock_response = {
            "export_id": "exp-uuid-1",
            "export_type": "journal_paie",
            "period": "2025-01",
            "status": "generated",
            "files": [
                {"filename": "out.xlsx", "path": "p", "size": 100, "format": "xlsx"}
            ],
            "report": {
                "export_type": "journal_paie",
                "period": "2025-01",
                "generated_at": datetime.now().isoformat(),
                "generated_by": "Test",
                "employees_count": 1,
                "totals": {"employees_count": 1},
                "anomalies": [],
                "warnings": [],
                "parameters": {},
            },
            "download_urls": {"out.xlsx": "https://signed.url/out.xlsx"},
        }
        with patch(
            "app.modules.exports.application.service.generate_export",
            return_value=mock_response,
        ):
            response = client_with_exports_auth.post(
                "/api/exports/generate",
                json={
                    "export_type": "journal_paie",
                    "period": "2025-01",
                    "format": "xlsx",
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["export_id"] == "exp-uuid-1"
        assert data["status"] == "generated"
        assert len(data["files"]) == 1
        assert "download_urls" in data

    def test_get_history_returns_200_and_list(
        self, client_with_exports_auth: TestClient
    ):
        """GET /api/exports/history → 200 et exports, total."""
        mock_response = {"exports": [], "total": 0}
        with patch(
            "app.modules.exports.application.service.get_export_history",
            return_value=mock_response,
        ):
            response = client_with_exports_auth.get("/api/exports/history")
        assert response.status_code == 200
        data = response.json()
        assert "exports" in data
        assert "total" in data
        assert data["total"] == 0

    def test_get_history_accepts_query_params(
        self, client_with_exports_auth: TestClient
    ):
        """GET /api/exports/history?export_type=dsn_mensuelle&period=2025-01 transmet les filtres."""
        with patch(
            "app.modules.exports.application.service.get_export_history",
            return_value={"exports": [], "total": 0},
        ) as mock_get:
            client_with_exports_auth.get(
                "/api/exports/history?export_type=dsn_mensuelle&period=2025-01"
            )
            mock_get.assert_called_once()
            assert mock_get.call_args[0][1] == "dsn_mensuelle"
            assert mock_get.call_args[0][2] == "2025-01"

    def test_get_download_returns_200_with_download_url(
        self, client_with_exports_auth: TestClient
    ):
        """GET /api/exports/download/{export_id} → 200 et download_url."""
        with patch(
            "app.modules.exports.application.service.get_export_download_url",
            return_value="https://signed.url/file.xlsx",
        ):
            response = client_with_exports_auth.get("/api/exports/download/exp-123")
        assert response.status_code == 200
        data = response.json()
        assert data["download_url"] == "https://signed.url/file.xlsx"

    def test_get_download_export_not_found_returns_404(
        self, client_with_exports_auth: TestClient
    ):
        """GET /api/exports/download/{id} quand export inexistant → 404."""
        with patch(
            "app.modules.exports.application.service.get_export_download_url",
            side_effect=ValueError("Export non trouvé"),
        ):
            response = client_with_exports_auth.get("/api/exports/download/unknown-id")
        assert response.status_code == 404
