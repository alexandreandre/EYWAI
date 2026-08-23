"""
Tests d'intégration HTTP des routes du module absences.

Utilise les fixtures : client (TestClient), auth_headers (conftest.py).
Pour les routes protégées (me/*, get-upload-url, PATCH status, certificate) :
  - Sans token → 401.
  - Avec auth_headers valide (fixture à compléter en 8.2) → 200/201 selon cas.
Préfixe des routes : /api/absences.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.users.schemas.responses import CompanyAccess, User


pytestmark = pytest.mark.integration

TEST_COMPANY_ID = "company-absences-test"


def _make_rh_user():
    access = CompanyAccess(
        company_id=TEST_COMPANY_ID,
        company_name="Test Co",
        role="rh",
        is_primary=True,
    )
    return User(
        id="user-rh-absences-test",
        email="rh@absences.test",
        first_name="RH",
        last_name="Absences",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[access],
        active_company_id=TEST_COMPANY_ID,
    )


def _make_non_rh_user():
    access = CompanyAccess(
        company_id=TEST_COMPANY_ID,
        company_name="Test Co",
        role="collaborateur",
        is_primary=True,
    )
    return User(
        id="user-non-rh-absences-test",
        email="collab@absences.test",
        first_name="Collab",
        last_name="Test",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[access],
        active_company_id=TEST_COMPANY_ID,
    )


def _make_collaborateur_rh_user():
    access = CompanyAccess(
        company_id=TEST_COMPANY_ID,
        company_name="Test Co",
        role="collaborateur_rh",
        is_primary=True,
    )
    return User(
        id="user-collab-rh-absences-test",
        email="collab-rh@absences.test",
        first_name="Collab",
        last_name="RH",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[access],
        active_company_id=TEST_COMPANY_ID,
    )


# --- GET /api/absences/ (liste RH) ---


class TestGetAbsenceRequests:
    """GET /api/absences/ — liste des demandes, optionnellement filtrée par status."""

    def test_get_absence_requests_returns_401_without_auth(self, client: TestClient):
        """Sans auth → 401."""
        response = client.get("/api/absences/")
        assert response.status_code == 401

    def test_get_absence_requests_returns_403_for_non_rh_user(self, client: TestClient):
        """Utilisateur sans accès RH → 403."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_non_rh_user()
        try:
            response = client.get("/api/absences/")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 403

    def test_get_absence_requests_returns_200_with_rh_user(self, client: TestClient):
        """Liste (mock) → 200."""
        from app.core.security import get_current_user

        with patch(
            "app.modules.absences.api.router.queries.get_absence_requests",
            return_value=[],
        ):
            app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
            try:
                response = client.get("/api/absences/")
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_absence_requests_with_status_filter(self, client: TestClient):
        """Filtre status=pending transmis à la query."""
        from app.core.security import get_current_user

        with patch(
            "app.modules.absences.api.router.queries.get_absence_requests",
            return_value=[],
        ) as mock_get:
            app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
            try:
                response = client.get("/api/absences/?status=pending")
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        mock_get.assert_called_once_with("pending", company_id=TEST_COMPANY_ID)


# --- POST /api/absences/requests (création, auth requise) ---


class TestCreateAbsenceRequest:
    """POST /api/absences/requests — création d'une demande d'absence."""

    def test_create_absence_request_without_auth_returns_401(self, client: TestClient):
        """Sans token → 401."""
        response = client.post(
            "/api/absences/requests",
            json={
                "employee_id": "emp-test",
                "type": "conge_paye",
                "selected_days": ["2025-06-10"],
            },
        )
        assert response.status_code == 401

    def test_create_absence_request_invalid_body_returns_422(self, client: TestClient):
        """Body invalide (manque champs obligatoires) → 422."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_non_rh_user()
        try:
            response = client.post("/api/absences/requests", json={})
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 422

    def test_create_absence_request_empty_selected_days_returns_400(
        self, client: TestClient
    ):
        """selected_days vide → 400 (validation métier)."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_non_rh_user()
        try:
            with patch(
                "app.modules.absences.api.router.absence_router.resolve_employee_id_for_user",
                return_value="emp-resolved",
            ):
                response = client.post(
                    "/api/absences/requests",
                    json={
                        "employee_id": "user-non-rh-absences-test",
                        "type": "conge_paye",
                        "selected_days": [],
                    },
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert (
            "jour" in data["detail"].lower() or "sélectionner" in data["detail"].lower()
        )

    def test_create_absence_request_arret_maladie_returns_403_for_non_rh(
        self, client: TestClient
    ):
        """Un collaborateur ne peut pas déclarer un arrêt maladie lui-même."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_non_rh_user()
        try:
            with patch(
                "app.modules.absences.api.router.absence_router.resolve_employee_id_for_user",
                return_value="emp-resolved",
            ):
                response = client.post(
                    "/api/absences/requests",
                    json={
                        "employee_id": "user-non-rh-absences-test",
                        "type": "arret_maladie",
                        "selected_days": ["2025-06-10"],
                        "arret_type": "maladie_simple",
                    },
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 403
        assert "employeur" in response.json()["detail"].lower()

    def test_create_absence_request_arret_maladie_rh_auto_validates(
        self, client: TestClient
    ):
        """La RH enregistre un arrêt directement : statut validé, sans circuit demande."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        validated_row = {
            "id": "arret-direct-1",
            "employee_id": "emp-target",
            "company_id": TEST_COMPANY_ID,
            "type": "arret_maladie",
            "arret_type": "maladie_simple",
            "selected_days": ["2025-05-01", "2025-05-02"],
            "status": "validated",
            "workflow_step": "approved_rh",
            "comment": None,
            "created_at": "2025-06-01T09:00:00",
            "manager_id": None,
            "attachment_url": None,
            "filename": None,
            "event_subtype": None,
            "jours_payes": None,
        }
        try:
            with (
                patch(
                    "app.modules.absences.api.router.absence_router.employee_company_id",
                    return_value=TEST_COMPANY_ID,
                ),
                patch(
                    "app.modules.absences.api.router.commands.create_absence_request"
                ) as create_cmd,
                patch(
                    "app.modules.absences.api.router.commands.update_absence_request_status"
                ) as validate_cmd,
                patch(
                    "app.modules.absences.api.router.absence_router.update_absence",
                    return_value=validated_row,
                ),
                patch(
                    "app.modules.absences.api.router._notify_rh_status_change",
                ),
                patch(
                    "app.modules.absences.api.router._enrich_single_absence_row",
                    side_effect=lambda row: row,
                ),
            ):
                create_cmd.return_value = {
                    **validated_row,
                    "status": "pending",
                    "workflow_step": "pending",
                }
                validate_cmd.return_value = {
                    **validated_row,
                    "workflow_step": "pending",
                }
                response = client.post(
                    "/api/absences/requests",
                    json={
                        "employee_id": "emp-target",
                        "type": "arret_maladie",
                        "selected_days": ["2025-05-01", "2025-05-02"],
                        "arret_type": "maladie_simple",
                    },
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 201
        data = response.json()
        assert data.get("status") == "validated"
        assert data.get("workflow_step") == "approved_rh"
        validate_cmd.assert_called_once_with(
            "arret-direct-1",
            "validated",
            current_user_id="user-rh-absences-test",
        )
        create_cmd.assert_called_once()

    def test_create_absence_request_arret_maternite_returns_403_for_non_rh(
        self, client: TestClient
    ):
        """Un collaborateur ne peut pas déclarer un congé maternité lui-même."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_non_rh_user()
        try:
            with patch(
                "app.modules.absences.api.router.absence_router.resolve_employee_id_for_user",
                return_value="emp-resolved",
            ):
                response = client.post(
                    "/api/absences/requests",
                    json={
                        "employee_id": "user-non-rh-absences-test",
                        "type": "arret_maternite",
                        "selected_days": ["2025-06-10"],
                        "arret_type": "maladie_simple",
                    },
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 403

    def test_create_absence_request_conge_paye_insufficient_balance_returns_400(
        self, client: TestClient
    ):
        """Un collaborateur ne peut pas demander plus de CP que son solde disponible."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_non_rh_user()
        try:
            with (
                patch(
                    "app.modules.absences.api.router.absence_router.resolve_employee_id_for_user",
                    return_value="emp-resolved",
                ),
                patch(
                    "app.modules.absences.application.queries.assert_employee_conge_paye_request_allowed",
                    side_effect=ValueError(
                        "Solde de congés payés insuffisant. Rapprochez-vous de votre direction "
                        "pour toute demande hors droits acquis."
                    ),
                ),
            ):
                response = client.post(
                    "/api/absences/requests",
                    json={
                        "employee_id": "user-non-rh-absences-test",
                        "type": "conge_paye",
                        "selected_days": ["2026-06-10", "2026-06-11", "2026-06-12"],
                    },
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 400
        assert "insuffisant" in response.json()["detail"].lower()

    def test_create_absence_request_valid_schema_calls_app(self, client: TestClient):
        """Body valide (schema) → 201 si employé/DB OK, 404 si employé inconnu, 500 si erreur."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_non_rh_user()
        try:
            with (
                patch(
                    "app.modules.absences.api.router.absence_router.resolve_employee_id_for_user",
                    return_value="emp-resolved",
                ),
                patch(
                    "app.modules.absences.api.router.commands.create_absence_request"
                ) as create_cmd,
                patch(
                    "app.modules.absences.api.router.absence_router.get_team_manager_employee_id",
                    return_value=None,
                ),
                patch(
                    "app.modules.absences.api.router.absence_router.update_absence",
                    side_effect=lambda rid, payload: {
                        "id": rid,
                        "employee_id": "emp-resolved",
                        "company_id": TEST_COMPANY_ID,
                        "type": "conge_paye",
                        "selected_days": ["2025-06-10", "2025-06-11"],
                        "status": "pending",
                        "comment": None,
                        "created_at": "2025-06-01T09:00:00",
                        "manager_id": None,
                        "attachment_url": None,
                        "filename": None,
                        "event_subtype": None,
                        "jours_payes": None,
                        **payload,
                    },
                ),
                patch(
                    "app.modules.absences.api.router.absence_notif.notify_absence_submitted",
                ),
                patch(
                    "app.modules.absences.api.router.absence_notif.notify_manager_new_request",
                ),
                patch(
                    "app.modules.absences.api.router.absence_notif.notify_leave_request_email",
                ),
                patch(
                    "app.modules.absences.api.router._enrich_single_absence_row",
                    side_effect=lambda row: row,
                ),
            ):
                create_cmd.return_value = {
                    "id": "created-1",
                    "employee_id": "emp-resolved",
                    "company_id": TEST_COMPANY_ID,
                    "type": "conge_paye",
                    "selected_days": ["2025-06-10", "2025-06-11"],
                    "status": "pending",
                    "comment": None,
                    "created_at": "2025-06-01T09:00:00",
                    "manager_id": None,
                    "attachment_url": None,
                    "filename": None,
                    "event_subtype": None,
                    "jours_payes": None,
                }
                response = client.post(
                    "/api/absences/requests",
                    json={
                        "employee_id": "user-non-rh-absences-test",
                        "type": "conge_paye",
                        "selected_days": ["2025-06-10", "2025-06-11"],
                    },
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data.get("type") == "conge_paye"
        assert "selected_days" in data
        create_cmd.assert_called_once()
        assert create_cmd.call_args[0][0].employee_id == "emp-resolved"

    def test_create_absence_request_triggers_leave_email_best_effort(
        self, client: TestClient
    ):
        """Une création salarié déclenche le hook email RH best effort."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_non_rh_user()
        try:
            with (
                patch(
                    "app.modules.absences.api.router.absence_router.resolve_employee_id_for_user",
                    return_value="emp-resolved",
                ),
                patch(
                    "app.modules.absences.api.router.commands.create_absence_request"
                ) as create_cmd,
                patch(
                    "app.modules.absences.api.router.absence_router.get_team_manager_employee_id",
                    return_value=None,
                ),
                patch(
                    "app.modules.absences.api.router.absence_router.update_absence",
                    side_effect=lambda rid, payload: {
                        "id": rid,
                        "employee_id": "emp-resolved",
                        "company_id": TEST_COMPANY_ID,
                        "type": "conge_paye",
                        "selected_days": ["2025-06-10"],
                        "status": "pending",
                        "comment": None,
                        "created_at": "2025-06-01T09:00:00",
                        "manager_id": None,
                        "attachment_url": None,
                        "filename": None,
                        "event_subtype": None,
                        "jours_payes": None,
                        **payload,
                    },
                ),
                patch(
                    "app.modules.absences.api.router.absence_notif.notify_absence_submitted",
                ),
                patch(
                    "app.modules.absences.api.router.absence_notif.notify_leave_request_email",
                ) as email_hook,
                patch(
                    "app.modules.absences.api.router._enrich_single_absence_row",
                    side_effect=lambda row: row,
                ),
            ):
                create_cmd.return_value = {
                    "id": "created-email-1",
                    "employee_id": "emp-resolved",
                    "company_id": TEST_COMPANY_ID,
                    "type": "conge_paye",
                    "selected_days": ["2025-06-10"],
                    "status": "pending",
                    "comment": None,
                    "created_at": "2025-06-01T09:00:00",
                    "manager_id": None,
                    "attachment_url": None,
                    "filename": None,
                    "event_subtype": None,
                    "jours_payes": None,
                }
                response = client.post(
                    "/api/absences/requests",
                    json={
                        "employee_id": "user-non-rh-absences-test",
                        "type": "conge_paye",
                        "selected_days": ["2025-06-10"],
                    },
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 201
        email_hook.assert_called_once()
        assert email_hook.call_args.kwargs["event"] == "employee_request"


class TestLeaveNotificationSettings:
    """GET/PUT /api/absences/leave-notification-settings."""

    def test_get_settings_requires_rh_access(self, client: TestClient):
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_non_rh_user()
        try:
            response = client.get("/api/absences/leave-notification-settings")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 403

    def test_get_settings_returns_default_for_rh(self, client: TestClient):
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.absences.api.router.leave_notification_settings.get_settings",
            ) as get_settings:
                get_settings.return_value = {
                    "company_id": TEST_COMPANY_ID,
                    "enabled": False,
                    "notify_on_employee_request": True,
                    "notify_after_manager_approval": True,
                    "recipient_roles": ["rh", "admin"],
                    "extra_recipient_emails": [],
                    "configured": False,
                }
                response = client.get("/api/absences/leave-notification-settings")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert response.json()["recipient_roles"] == ["rh", "admin"]

    def test_put_settings_forbidden_for_collaborateur_rh(self, client: TestClient):
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: (
            _make_collaborateur_rh_user()
        )
        try:
            response = client.put(
                "/api/absences/leave-notification-settings",
                json={"enabled": True},
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 403

    def test_put_settings_allowed_for_rh(self, client: TestClient):
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.absences.api.router.leave_notification_settings.update_settings",
            ) as update_settings:
                update_settings.return_value = {
                    "company_id": TEST_COMPANY_ID,
                    "enabled": True,
                    "notify_on_employee_request": True,
                    "notify_after_manager_approval": False,
                    "recipient_roles": ["rh"],
                    "extra_recipient_emails": ["paie@example.fr"],
                    "configured": True,
                }
                response = client.put(
                    "/api/absences/leave-notification-settings",
                    json={
                        "enabled": True,
                        "notify_after_manager_approval": False,
                        "recipient_roles": ["rh"],
                        "extra_recipient_emails": ["paie@example.fr"],
                    },
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert response.json()["enabled"] is True
        update_settings.assert_called_once()


# --- GET /api/absences/employees/{employee_id} ---


class TestGetAbsencesForEmployee:
    """GET /api/absences/employees/{employee_id} — demandes pour un employé.

    Route fermée par l'audit du 22/08/2026 : elle exposait en anonyme les
    arrêts maladie et les URLs signées des justificatifs.
    """

    def test_get_absences_for_employee_without_token_returns_401(
        self, client: TestClient
    ):
        """Sans jeton → 401, aucune donnée d'absence ne sort."""
        response = client.get(
            "/api/absences/employees/00000000-0000-0000-0000-000000000001"
        )
        assert response.status_code == 401


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
    """PATCH /api/absences/{request_id} — mise à jour statut (RH)."""

    def test_update_legacy_returns_401_without_auth(self, client: TestClient):
        """Sans auth → 401."""
        response = client.patch(
            "/api/absences/00000000-0000-0000-0000-000000000099",
            json={"status": "rejected"},
        )
        assert response.status_code == 401

    def test_update_legacy_returns_403_for_non_rh_user(self, client: TestClient):
        """Utilisateur sans accès RH → 403."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_non_rh_user()
        try:
            response = client.patch(
                "/api/absences/00000000-0000-0000-0000-000000000099",
                json={"status": "rejected"},
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 403


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
        response = client.get("/api/absences/employees/me/calendar?year=2025&month=6")
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
        response = client.get("/api/absences/employees/me/page-data?year=2025&month=6")
        assert response.status_code == 401

    def test_me_page_data_uses_resolved_employee_id(self, client: TestClient):
        """La query page-data reçoit employees.id résolu, pas l'uid auth."""
        from app.core.security import get_current_user

        page_payload = {
            "balances": [],
            "calendar_days": [],
            "history": [],
        }
        with (
            patch(
                "app.modules.absences.api.router.absence_router.resolve_employee_id_for_user",
                return_value="emp-resolved",
            ),
            patch(
                "app.modules.absences.api.router.queries.get_my_absences_page_data",
                return_value=page_payload,
            ) as mock_page,
        ):
            app.dependency_overrides[get_current_user] = lambda: _make_non_rh_user()
            try:
                response = client.get(
                    "/api/absences/employees/me/page-data?year=2025&month=6"
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        mock_page.assert_called_once_with("emp-resolved", 2025, 6)

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

    def test_generate_certificate_without_token_returns_401(self, client: TestClient):
        """Sans token → 401."""
        response = client.post(
            "/api/absences/00000000-0000-0000-0000-000000000001/generate-certificate"
        )
        assert response.status_code == 401


class TestDownloadSalaryCertificate:
    """GET /api/absences/{absence_id}/certificate/download."""

    def test_download_certificate_without_token_returns_401(self, client: TestClient):
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


# --- Campagne congés / CP ancienneté / fractionnement ---


class TestLeaveCampaignRoutes:
    """Routes campagne congés annuelle et validation grants."""

    def test_leave_campaign_dashboard_without_auth_returns_401(
        self, client: TestClient
    ):
        response = client.get("/api/absences/leave-campaign/dashboard")
        assert response.status_code == 401

    def test_leave_campaign_dashboard_returns_200_with_rh_user(
        self, client: TestClient
    ):
        from app.core.security import get_current_user

        dashboard = {
            "grant_year": 2026,
            "phase": "cp_seniority",
            "today": "2026-06-01",
            "cp_seniority": {
                "enabled": True,
                "preset": "metallurgie_idcc_3248",
                "employee_count": 2,
                "total_days": 3.0,
                "validated_count": 0,
                "overridden_count": 0,
                "warnings_count": 1,
                "deadline": "2026-05-31",
            },
            "fractionnement": {
                "enabled": True,
                "calculation_method": "mbc",
                "employee_count": 2,
                "total_days": 2,
                "validated_count": 0,
                "deadline": "2026-10-31",
            },
            "alerts": [],
        }
        with patch(
            "app.modules.absences.api.router.leave_campaign_queries.get_leave_campaign_dashboard",
            return_value=dashboard,
        ):
            app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
            try:
                response = client.get(
                    "/api/absences/leave-campaign/dashboard?grant_year=2026"
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        data = response.json()
        assert data["grant_year"] == 2026
        assert data["cp_seniority"]["employee_count"] == 2

    def test_validate_cp_seniority_without_auth_returns_401(self, client: TestClient):
        response = client.post(
            "/api/absences/cp-seniority-settings/validate?grant_year=2026"
        )
        assert response.status_code == 401

    def test_validate_cp_seniority_calls_command(self, client: TestClient):
        from app.core.security import get_current_user

        with patch(
            "app.modules.absences.api.router.cp_seniority_commands.validate_cp_seniority_grants",
            return_value={
                "grant_year": 2026,
                "validated_count": 5,
                "status": "validated",
            },
        ) as mock_validate:
            app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
            try:
                response = client.post(
                    "/api/absences/cp-seniority-settings/validate?grant_year=2026"
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert response.json()["validated_count"] == 5
        mock_validate.assert_called_once()

    def test_validate_fractionnement_without_auth_returns_401(self, client: TestClient):
        response = client.post("/api/absences/fractionnement/validate?grant_year=2026")
        assert response.status_code == 401

    def test_validate_fractionnement_calls_query(self, client: TestClient):
        from app.core.security import get_current_user

        with patch(
            "app.modules.absences.api.router.fractionnement_queries.validate_fractionnement_grants",
            return_value={
                "grant_year": 2026,
                "validated_count": 3,
                "status": "validated",
            },
        ) as mock_validate:
            app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
            try:
                response = client.post(
                    "/api/absences/fractionnement/validate?grant_year=2026"
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert response.json()["validated_count"] == 3
        mock_validate.assert_called_once()
