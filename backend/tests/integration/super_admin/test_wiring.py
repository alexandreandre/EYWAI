"""
Tests de câblage (wiring) du module super_admin.

Vérifient que l'injection des dépendances et le flux de bout en bout
(router -> verify_super_admin -> application commands/queries -> infrastructure)
fonctionnent pour ce module.
"""
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.users.schemas.responses import User

pytestmark = pytest.mark.integration

TEST_USER_ID = "660e8400-e29b-41d4-a716-446655440001"


def _make_super_admin_user():
    return User(
        id=TEST_USER_ID,
        email="super@test.com",
        first_name="Super",
        last_name="Admin",
        is_super_admin=True,
        is_group_admin=False,
        accessible_companies=[],
        active_company_id=None,
    )


def _verify_super_admin_dep():
    """Retourne un dict ligne super_admins pour les routes."""
    return {
        "id": "sa-1",
        "user_id": TEST_USER_ID,
        "email": "super@test.com",
        "first_name": "Super",
        "last_name": "Admin",
        "can_create_companies": True,
        "can_delete_companies": True,
        "can_view_all_data": True,
        "can_impersonate": False,
        "is_active": True,
    }


class TestSuperAdminWiringVerifyThenQuery:
    """Flux : get_current_user -> verify_super_admin -> queries.get_global_stats."""

    def test_dashboard_stats_flow_calls_verify_then_query(self, client: TestClient):
        """GET /api/super-admin/dashboard/stats : dépendance verify_super_admin injectée puis query appelée."""
        from app.core.security import get_current_user
        from app.modules.super_admin.api.router import verify_super_admin

        app.dependency_overrides[get_current_user] = lambda: _make_super_admin_user()
        app.dependency_overrides[verify_super_admin] = _verify_super_admin_dep
        try:
            with patch(
                "app.modules.super_admin.api.router.queries.get_global_stats",
                return_value={
                    "companies": {"total": 1},
                    "users": {"total": 2},
                    "employees": {"total": 3},
                    "super_admins": {"total": 1},
                    "top_companies": [],
                },
            ) as m_query:
                response = client.get("/api/super-admin/dashboard/stats")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(verify_super_admin, None)

        assert response.status_code == 200
        m_query.assert_called_once()
        # Le dict passé à get_global_stats est celui retourné par verify_super_admin
        call_args = m_query.call_args[0]
        assert len(call_args) == 1
        assert call_args[0]["user_id"] == TEST_USER_ID
        assert call_args[0]["can_create_companies"] is True


class TestSuperAdminWiringVerifyThenCommand:
    """Flux : verify_super_admin -> commands.create_company_with_admin."""

    def test_create_company_flow_calls_verify_then_command(self, client: TestClient):
        """POST /api/super-admin/companies : verify_super_admin puis create_company_with_admin."""
        from app.core.security import get_current_user
        from app.modules.super_admin.api.router import verify_super_admin

        app.dependency_overrides[get_current_user] = lambda: _make_super_admin_user()
        app.dependency_overrides[verify_super_admin] = _verify_super_admin_dep
        try:
            with patch(
                "app.modules.super_admin.api.router.commands.create_company_with_admin",
                return_value={"success": True, "company": {"id": "c1", "company_name": "Wired Co"}},
            ) as m_cmd:
                response = client.post(
                    "/api/super-admin/companies",
                    json={"company_name": "Wired Co", "siret": "123"},
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(verify_super_admin, None)

        assert response.status_code == 200
        assert response.json()["company"]["company_name"] == "Wired Co"
        m_cmd.assert_called_once()
        args = m_cmd.call_args[0]
        assert args[0]["company_name"] == "Wired Co"
        assert args[1]["user_id"] == TEST_USER_ID


class TestSuperAdminWiringServiceVerifyDependsOnRepository:
    """Flux verify_super_admin : service.verify_super_admin_and_return_row utilise get_by_user_id."""

    def test_verify_super_admin_calls_repository_then_mapper(self):
        """En appelant le service, get_by_user_id est invoqué puis super_admin_to_row."""
        from app.modules.super_admin.application.service import verify_super_admin_and_return_row
        from app.modules.super_admin.domain.entities import SuperAdmin
        from uuid import UUID

        entity = SuperAdmin(
            id=UUID("770e8400-e29b-41d4-a716-446655440002"),
            user_id=UUID(TEST_USER_ID),
            email="super@test.com",
            first_name="Super",
            last_name="Admin",
            can_create_companies=True,
            can_delete_companies=True,
            can_view_all_data=True,
            can_impersonate=False,
            is_active=True,
        )
        with patch(
            "app.modules.super_admin.application.service.get_by_user_id",
            return_value=entity,
        ) as m_get:
            with patch(
                "app.modules.super_admin.application.service.super_admin_to_row",
                return_value={"user_id": TEST_USER_ID, "email": "super@test.com"},
            ) as m_to_row:
                row = verify_super_admin_and_return_row(TEST_USER_ID)
        m_get.assert_called_once_with(TEST_USER_ID)
        m_to_row.assert_called_once_with(entity)
        assert row["user_id"] == TEST_USER_ID
