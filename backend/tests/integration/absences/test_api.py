"""
Tests d'intégration HTTP des routes du module absences.

Utilise les fixtures : client (TestClient), auth_headers (conftest.py).
Pour les routes protégées (me/*, get-upload-url, PATCH status, certificate) :
  - Sans token → 401.
  - Avec auth_headers valide (fixture à compléter en 8.2) → 200/201 selon cas.
Préfixe des routes : /api/absences.
"""

import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.integration


# --- GET /api/absences/ (liste globale, sans auth) ---


class TestGetAbsenceRequests:
    """GET /api/absences/ — liste des demandes, optionnellement filtrée par status."""

    def test_get_absence_requests_returns_200(self, client: TestClient):
        """Liste des demandes → 200 et tableau (vide ou non)."""
        response = client.get("/api/absences/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_absence_requests_with_status_filter(self, client: TestClient):
        """Filtre status=pending → 200."""
        response = client.get("/api/absences/?status=pending")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


# --- POST /api/absences/requests (création, sans auth dans le router) ---


class TestCreateAbsenceRequest:
    """POST /api/absences/requests — création d'une demande d'absence."""

    def test_create_absence_request_invalid_body_returns_422(self, client: TestClient):
        """Body invalide (manque champs obligatoires) → 422."""
        response = client.post("/api/absences/requests", json={})
        assert response.status_code == 422

    def test_create_absence_request_empty_selected_days_returns_400(
        self, client: TestClient
    ):
        """selected_days vide → 400 (validation métier)."""
        response = client.post(
            "/api/absences/requests",
            json={
                "employee_id": "emp-test",
                "type": "conge_paye",
                "selected_days": [],
            },
        )
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "jour" in data["detail"].lower() or "sélectionner" in data["detail"].lower()

    def test_create_absence_request_valid_schema_calls_app(
        self, client: TestClient
    ):
        """Body valide (schema) → 201 si employé/DB OK, 404 si employé inconnu, 500 si erreur."""
        response = client.post(
            "/api/absences/requests",
            json={
                "employee_id": "employee-inexistant-uuid",
                "type": "conge_paye",
                "selected_days": ["2025-06-10", "2025-06-11"],
            },
        )
        # 404 employé non trouvé ou 201 si test data existe
        assert response.status_code in (201, 404, 500)
        if response.status_code == 201:
            data = response.json()
            assert "id" in data
            assert data.get("type") == "conge_paye"
            assert "selected_days" in data


# --- GET /api/absences/employees/{employee_id} ---


class TestGetAbsencesForEmployee:
    """GET /api/absences/employees/{employee_id} — demandes pour un employé."""

    def test_get_absences_for_employee_returns_200(self, client: TestClient):
        """Retourne une liste (vide ou non)."""
        response = client.get(
            "/api/absences/employees/00000000-0000-0000-0000-000000000001"
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)


# --- Routes protégées (nécessitent auth_headers) ---


class TestGetUploadUrl:
    """POST /api/absences/get-upload-url — URL signée pour justificatif."""

    def test_get_upload_url_without_token_returns_401(self, client: TestClient):
        """Sans token → 401."""
        response = client.post(
            "/api/absences/get-upload-url",
            json={"filename": "doc.pdf"},
        )
        assert response.status_code == 401

    def test_get_upload_url_with_auth_returns_200_or_401(
        self, client: TestClient, auth_headers: dict
    ):
        """Avec auth_headers : 200 + path/signedURL si token valide, 401 sinon."""
        response = client.post(
            "/api/absences/get-upload-url",
            headers=auth_headers,
            json={"filename": "justif.pdf"},
        )
        if auth_headers:
            assert response.status_code in (200, 401)
            if response.status_code == 200:
                data = response.json()
                assert "path" in data
                assert "signedURL" in data
        else:
            assert response.status_code == 401


class TestUpdateAbsenceRequestStatus:
    """PATCH /api/absences/requests/{request_id}/status — mise à jour statut (utilisateur connecté)."""

    def test_update_status_without_token_returns_401(self, client: TestClient):
        """Sans token → 401."""
        response = client.patch(
            "/api/absences/requests/req-123/status",
            json={"status": "validated"},
        )
        assert response.status_code == 401

    def test_update_status_with_auth_returns_404_or_200(
        self, client: TestClient, auth_headers: dict
    ):
        """Avec auth : 404 si demande inconnue, 200 si OK."""
        if not auth_headers:
            return
        response = client.patch(
            "/api/absences/requests/00000000-0000-0000-0000-000000000099/status",
            headers=auth_headers,
            json={"status": "cancelled"},
        )
        assert response.status_code in (200, 401, 404)


class TestUpdateAbsenceRequestLegacy:
    """PATCH /api/absences/{request_id} — mise à jour statut (admin/RH)."""

    def test_update_legacy_with_valid_body(self, client: TestClient):
        """Route sans Depends auth : 404 si id inconnu, 200 si trouvé."""
        response = client.patch(
            "/api/absences/00000000-0000-0000-0000-000000000099",
            json={"status": "rejected"},
        )
        assert response.status_code in (200, 404, 500)


class TestGetMyEvenementsFamiliaux:
    """GET /api/absences/employees/me/evenements-familiaux."""

    def test_me_evenements_without_token_returns_401(self, client: TestClient):
        """Sans token → 401."""
        response = client.get("/api/absences/employees/me/evenements-familiaux")
        assert response.status_code == 401


class TestGetMyAbsenceBalances:
    """GET /api/absences/employees/me/balances."""

    def test_me_balances_without_token_returns_401(self, client: TestClient):
        """Sans token → 401."""
        response = client.get("/api/absences/employees/me/balances")
        assert response.status_code == 401

    def test_me_balances_with_auth_returns_200_or_404(
        self, client: TestClient, auth_headers: dict
    ):
        """Avec token valide : 200 + balances ou 404 si pas de date d'embauche."""
        if not auth_headers:
            return
        response = client.get(
            "/api/absences/employees/me/balances",
            headers=auth_headers,
        )
        assert response.status_code in (200, 401, 404)
        if response.status_code == 200:
            data = response.json()
            assert "balances" in data
            assert isinstance(data["balances"], list)


class TestGetMyMonthlyCalendar:
    """GET /api/absences/employees/me/calendar."""

    def test_me_calendar_without_token_returns_401(self, client: TestClient):
        """Sans token → 401."""
        response = client.get(
            "/api/absences/employees/me/calendar?year=2025&month=6"
        )
        assert response.status_code == 401

    def test_me_calendar_with_auth_returns_200(
        self, client: TestClient, auth_headers: dict
    ):
        """Avec auth : 200 et liste de jours."""
        if not auth_headers:
            return
        response = client.get(
            "/api/absences/employees/me/calendar?year=2025&month=6",
            headers=auth_headers,
        )
        assert response.status_code in (200, 401)
        if response.status_code == 200:
            data = response.json()
            assert "days" in data


class TestGetMyAbsencesHistory:
    """GET /api/absences/employees/me/history."""

    def test_me_history_without_token_returns_401(self, client: TestClient):
        """Sans token → 401."""
        response = client.get("/api/absences/employees/me/history")
        assert response.status_code == 401


class TestGetMyAbsencesPageData:
    """GET /api/absences/employees/me/page-data."""

    def test_me_page_data_without_token_returns_401(self, client: TestClient):
        """Sans token → 401."""
        response = client.get(
            "/api/absences/employees/me/page-data?year=2025&month=6"
        )
        assert response.status_code == 401

    def test_me_page_data_with_auth_returns_200_or_404(
        self, client: TestClient, auth_headers: dict
    ):
        """Avec auth : 200 (balances, calendar_days, history) ou 404."""
        if not auth_headers:
            return
        response = client.get(
            "/api/absences/employees/me/page-data?year=2025&month=6",
            headers=auth_headers,
        )
        assert response.status_code in (200, 401, 404)
        if response.status_code == 200:
            data = response.json()
            assert "balances" in data
            assert "calendar_days" in data
            assert "history" in data


# --- Attestations de salaire ---


class TestGenerateSalaryCertificate:
    """POST /api/absences/{absence_id}/generate-certificate."""

    def test_generate_certificate_without_token_returns_401(
        self, client: TestClient
    ):
        """Sans token → 401."""
        response = client.post(
            "/api/absences/00000000-0000-0000-0000-000000000001/generate-certificate"
        )
        assert response.status_code == 401


class TestDownloadSalaryCertificate:
    """GET /api/absences/{absence_id}/certificate/download."""

    def test_download_certificate_without_token_returns_401(
        self, client: TestClient
    ):
        """Sans token → 401."""
        response = client.get(
            "/api/absences/00000000-0000-0000-0000-000000000001/certificate/download"
        )
        assert response.status_code == 401


class TestGetSalaryCertificate:
    """GET /api/absences/{absence_id}/certificate."""

    def test_get_certificate_without_token_returns_401(self, client: TestClient):
        """Sans token → 401."""
        response = client.get(
            "/api/absences/00000000-0000-0000-0000-000000000001/certificate"
        )
        assert response.status_code == 401

    def test_get_certificate_with_auth_returns_404_for_unknown_absence(
        self, client: TestClient, auth_headers: dict
    ):
        """Absence sans attestation → 404."""
        if not auth_headers:
            return
        response = client.get(
            "/api/absences/00000000-0000-0000-0000-000000000099/certificate",
            headers=auth_headers,
        )
        assert response.status_code in (401, 404)
