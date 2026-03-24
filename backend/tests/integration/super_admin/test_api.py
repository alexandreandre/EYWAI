"""
Tests d'intégration HTTP des routes du module super_admin.

Routes : GET /dashboard/stats, GET/POST/PATCH/DELETE /companies, GET /companies/{id},
DELETE /companies/{id}/permanent, GET /users, GET/POST/PATCH/DELETE /companies/{id}/users,
GET /system/health, GET /super-admins, POST /reduction-fillon/calculate, GET /reduction-fillon/employees.

Utilise : client (TestClient), dependency_overrides pour get_current_user et verify_super_admin,
patch des commands/queries pour éviter DB réelle.

Fixture à ajouter dans tests/conftest.py si besoin de tests E2E avec token réel :
  @pytest.fixture
  def super_admin_headers(auth_headers):
      \"\"\"En-têtes pour les routes /api/super-admin/*. L'utilisateur doit être
      présent dans la table super_admins avec is_active=True.
      Format : {\"Authorization\": \"Bearer <jwt>\"}.\"\"\"
      return auth_headers
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.users.schemas.responses import User

pytestmark = pytest.mark.integration

TEST_USER_ID = "660e8400-e29b-41d4-a716-446655440001"


def _make_super_admin_user():
    """Utilisateur de test (pour get_current_user)."""
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
    """Dépendance mock pour verify_super_admin : retourne un dict ligne super_admins."""
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


# --- Sans auth : 401 ---


class TestSuperAdminUnauthenticated:
    """Sans token : 401."""

    def test_get_dashboard_stats_returns_401_without_token(self, client: TestClient):
        """Sans token, GET /api/super-admin/dashboard/stats renvoie 401."""
        response = client.get("/api/super-admin/dashboard/stats")
        assert response.status_code == 401


# --- Avec verify_super_admin mocké + commands/queries mockés ---


def _apply_super_admin_overrides():
    """Applique dependency_overrides pour super_admin (get_current_user + verify_super_admin)."""
    from app.core.security import get_current_user
    from app.modules.super_admin.api.router import verify_super_admin
    app.dependency_overrides[get_current_user] = lambda: _make_super_admin_user()
    app.dependency_overrides[verify_super_admin] = _verify_super_admin_dep
    return get_current_user, verify_super_admin


def _clear_super_admin_overrides(get_current_user, verify_super_admin):
    """Retire les overrides."""
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(verify_super_admin, None)


class TestSuperAdminDashboardStats:
    """GET /api/super-admin/dashboard/stats."""

    def test_returns_200_with_stats(self, client: TestClient):
        """Retourne 200 et structure companies, users, employees, super_admins, top_companies."""
        gu, vsa = _apply_super_admin_overrides()
        try:
            with patch(
                "app.modules.super_admin.api.router.queries.get_global_stats",
                return_value={
                    "companies": {"total": 5, "active": 4, "inactive": 1},
                    "users": {"total": 20, "by_role": {"admin": 5}},
                    "employees": {"total": 50},
                    "super_admins": {"total": 2},
                    "top_companies": [{"id": "c1", "name": "A", "employees_count": 10}],
                },
            ):
                response = client.get("/api/super-admin/dashboard/stats")
        finally:
            _clear_super_admin_overrides(gu, vsa)
        assert response.status_code == 200
        data = response.json()
        assert data["companies"]["total"] == 5
        assert data["users"]["total"] == 20
        assert "top_companies" in data


class TestSuperAdminCompaniesList:
    """GET /api/super-admin/companies."""

    def test_returns_200_with_companies_and_total(self, client: TestClient):
        """Retourne 200 et { companies, total }."""
        gu, vsa = _apply_super_admin_overrides()
        try:
            with patch(
                "app.modules.super_admin.api.router.queries.list_companies",
                return_value={"companies": [{"id": "c1", "company_name": "Test Co"}], "total": 1},
            ):
                response = client.get("/api/super-admin/companies?skip=0&limit=10")
        finally:
            _clear_super_admin_overrides(gu, vsa)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["companies"]) == 1
        assert data["companies"][0]["company_name"] == "Test Co"


class TestSuperAdminCompanyDetails:
    """GET /api/super-admin/companies/{company_id}."""

    def test_returns_200_with_company_details(self, client: TestClient):
        """Retourne 200 et détails entreprise + stats."""
        gu, vsa = _apply_super_admin_overrides()
        try:
            with patch(
                "app.modules.super_admin.api.router.queries.get_company_details",
                return_value={"id": "c1", "company_name": "Test", "stats": {"employees_count": 5, "users_count": 2}},
            ):
                response = client.get("/api/super-admin/companies/c1")
        finally:
            _clear_super_admin_overrides(gu, vsa)
        assert response.status_code == 200
        assert response.json()["company_name"] == "Test"
        assert response.json()["stats"]["employees_count"] == 5

    def test_returns_404_when_company_not_found(self, client: TestClient):
        """Retourne 404 si entreprise inexistante."""
        gu, vsa = _apply_super_admin_overrides()
        try:
            with patch(
                "app.modules.super_admin.api.router.queries.get_company_details",
                side_effect=LookupError("Entreprise non trouvée"),
            ):
                response = client.get("/api/super-admin/companies/unknown")
        finally:
            _clear_super_admin_overrides(gu, vsa)
        assert response.status_code == 404


class TestSuperAdminCompanyCreate:
    """POST /api/super-admin/companies."""

    def test_returns_200_with_company_and_optionally_admin(self, client: TestClient):
        """Retourne 200 et { success, company, admin? }."""
        gu, vsa = _apply_super_admin_overrides()
        try:
            with patch(
                "app.modules.super_admin.api.router.commands.create_company_with_admin",
                return_value={"success": True, "company": {"id": "c-new", "company_name": "Nouvelle"}},
            ):
                response = client.post(
                    "/api/super-admin/companies",
                    json={"company_name": "Nouvelle", "siret": "123"},
                )
        finally:
            _clear_super_admin_overrides(gu, vsa)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["company"]["company_name"] == "Nouvelle"


class TestSuperAdminCompanyUpdate:
    """PATCH /api/super-admin/companies/{company_id}."""

    def test_returns_200_with_updated_company(self, client: TestClient):
        """Retourne 200 et company mis à jour."""
        gu, vsa = _apply_super_admin_overrides()
        try:
            with patch(
                "app.modules.super_admin.api.router.commands.update_company",
                return_value={"success": True, "company": {"id": "c1", "company_name": "Updated"}},
            ):
                response = client.patch(
                    "/api/super-admin/companies/c1",
                    json={"company_name": "Updated"},
                )
        finally:
            _clear_super_admin_overrides(gu, vsa)
        assert response.status_code == 200
        assert response.json()["company"]["company_name"] == "Updated"


class TestSuperAdminCompanyDelete:
    """DELETE /api/super-admin/companies/{company_id} (soft)."""

    def test_returns_200_after_soft_delete(self, client: TestClient):
        """Retourne 200 après désactivation."""
        gu, vsa = _apply_super_admin_overrides()
        try:
            with patch(
                "app.modules.super_admin.api.router.commands.delete_company_soft",
                return_value={"success": True, "message": "Entreprise désactivée"},
            ):
                response = client.delete("/api/super-admin/companies/c1")
        finally:
            _clear_super_admin_overrides(gu, vsa)
        assert response.status_code == 200
        assert "désactivée" in response.json().get("message", "")


class TestSuperAdminCompanyDeletePermanent:
    """DELETE /api/super-admin/companies/{company_id}/permanent."""

    def test_returns_200_with_deletion_info(self, client: TestClient):
        """Retourne 200 et infos suppression."""
        gu, vsa = _apply_super_admin_overrides()
        try:
            with patch(
                "app.modules.super_admin.api.router.commands.delete_company_permanent",
                return_value={
                    "success": True,
                    "message": "Supprimé",
                    "deleted_company": {"id": "c1", "name": "Test"},
                    "deletion_statistics": {},
                    "total_records_deleted": 1,
                },
            ):
                response = client.delete("/api/super-admin/companies/c1/permanent")
        finally:
            _clear_super_admin_overrides(gu, vsa)
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert response.json()["deleted_company"]["id"] == "c1"


class TestSuperAdminListAllUsers:
    """GET /api/super-admin/users."""

    def test_returns_200_with_users_and_total(self, client: TestClient):
        """Retourne 200 et { users, total }."""
        gu, vsa = _apply_super_admin_overrides()
        try:
            with patch(
                "app.modules.super_admin.api.router.queries.list_all_users",
                return_value={"users": [{"id": "u1", "email": "u@test.com"}], "total": 1},
            ):
                response = client.get("/api/super-admin/users?skip=0&limit=10")
        finally:
            _clear_super_admin_overrides(gu, vsa)
        assert response.status_code == 200
        assert response.json()["total"] == 1
        assert len(response.json()["users"]) == 1


class TestSuperAdminCompanyUsers:
    """GET /api/super-admin/companies/{company_id}/users."""

    def test_returns_200_with_users(self, client: TestClient):
        """Retourne 200 et { users, total }."""
        gu, vsa = _apply_super_admin_overrides()
        try:
            with patch(
                "app.modules.super_admin.api.router.queries.get_company_users",
                return_value={"users": [{"id": "u1", "role": "admin"}], "total": 1},
            ):
                response = client.get("/api/super-admin/companies/c1/users")
        finally:
            _clear_super_admin_overrides(gu, vsa)
        assert response.status_code == 200
        assert response.json()["total"] == 1


class TestSuperAdminCreateCompanyUser:
    """POST /api/super-admin/companies/{company_id}/users."""

    def test_returns_200_with_created_user(self, client: TestClient):
        """Retourne 200 et user créé."""
        gu, vsa = _apply_super_admin_overrides()
        try:
            with patch(
                "app.modules.super_admin.api.router.commands.create_company_user",
                return_value={"success": True, "user": {"id": "u-new", "email": "new@test.com"}},
            ):
                response = client.post(
                    "/api/super-admin/companies/c1/users",
                    json={
                        "email": "new@test.com",
                        "password": "secret",
                        "first_name": "New",
                        "last_name": "User",
                        "role": "collaborateur",
                    },
                )
        finally:
            _clear_super_admin_overrides(gu, vsa)
        assert response.status_code == 200
        assert response.json()["user"]["email"] == "new@test.com"


class TestSuperAdminUpdateCompanyUser:
    """PATCH /api/super-admin/companies/{company_id}/users/{user_id}."""

    def test_returns_200_after_update(self, client: TestClient):
        """Retourne 200 après mise à jour."""
        gu, vsa = _apply_super_admin_overrides()
        try:
            with patch(
                "app.modules.super_admin.api.router.commands.update_company_user",
                return_value={"success": True, "message": "Utilisateur mis à jour avec succès"},
            ):
                response = client.patch(
                    "/api/super-admin/companies/c1/users/u1",
                    json={"first_name": "Updated"},
                )
        finally:
            _clear_super_admin_overrides(gu, vsa)
        assert response.status_code == 200


class TestSuperAdminDeleteCompanyUser:
    """DELETE /api/super-admin/companies/{company_id}/users/{user_id}."""

    def test_returns_200_after_delete(self, client: TestClient):
        """Retourne 200 après suppression accès/user."""
        gu, vsa = _apply_super_admin_overrides()
        try:
            with patch(
                "app.modules.super_admin.api.router.commands.delete_company_user",
                return_value={"success": True, "message": "Accès supprimé"},
            ):
                response = client.delete("/api/super-admin/companies/c1/users/u1")
        finally:
            _clear_super_admin_overrides(gu, vsa)
        assert response.status_code == 200


class TestSuperAdminSystemHealth:
    """GET /api/super-admin/system/health."""

    def test_returns_200_with_status(self, client: TestClient):
        """Retourne 200 et status (healthy/degraded/error)."""
        gu, vsa = _apply_super_admin_overrides()
        try:
            with patch(
                "app.modules.super_admin.api.router.queries.get_system_health",
                return_value={"status": "healthy", "checks": {"database": "ok"}},
            ):
                response = client.get("/api/super-admin/system/health")
        finally:
            _clear_super_admin_overrides(gu, vsa)
        assert response.status_code == 200
        assert response.json()["status"] in ("healthy", "degraded", "error")


class TestSuperAdminListSuperAdmins:
    """GET /api/super-admin/super-admins."""

    def test_returns_200_with_list(self, client: TestClient):
        """Retourne 200 et { super_admins, total }."""
        gu, vsa = _apply_super_admin_overrides()
        try:
            with patch(
                "app.modules.super_admin.api.router.queries.list_super_admins",
                return_value={"super_admins": [{"id": "sa1", "email": "sa@test.com"}], "total": 1},
            ):
                response = client.get("/api/super-admin/super-admins")
        finally:
            _clear_super_admin_overrides(gu, vsa)
        assert response.status_code == 200
        assert response.json()["total"] == 1
        assert len(response.json()["super_admins"]) == 1


class TestSuperAdminReductionFillonCalculate:
    """POST /api/super-admin/reduction-fillon/calculate."""

    def test_returns_200_with_calculation_result(self, client: TestClient):
        """Retourne 200 et structure résultat réduction Fillon."""
        gu, vsa = _apply_super_admin_overrides()
        try:
            with patch(
                "app.modules.super_admin.api.router.queries.calculate_reduction_fillon",
                return_value={"result": {"libelle": "Réduction Fillon", "montant_patronal": -50}, "input_data": {}},
            ):
                response = client.post(
                    "/api/super-admin/reduction-fillon/calculate",
                    json={"employee_id": "e1", "month": 3, "year": 2025},
                )
        finally:
            _clear_super_admin_overrides(gu, vsa)
        assert response.status_code == 200
        assert "result" in response.json()
        assert response.json()["result"]["libelle"] == "Réduction Fillon"


class TestSuperAdminReductionFillonEmployees:
    """GET /api/super-admin/reduction-fillon/employees."""

    def test_returns_200_with_employees_list(self, client: TestClient):
        """Retourne 200 et { employees, total }."""
        gu, vsa = _apply_super_admin_overrides()
        try:
            with patch(
                "app.modules.super_admin.api.router.queries.get_employees_for_reduction_fillon",
                return_value={"employees": [{"id": "e1", "name": "Jean Dupont"}], "total": 1},
            ):
                response = client.get("/api/super-admin/reduction-fillon/employees")
        finally:
            _clear_super_admin_overrides(gu, vsa)
        assert response.status_code == 200
        assert response.json()["total"] == 1
        assert len(response.json()["employees"]) == 1


class TestSuperAdminTestsRunner:
    """GET /api/super-admin/tests/tree, POST /api/super-admin/tests/run."""

    def test_get_tests_tree_returns_levels(self, client: TestClient):
        """200 et niveaux pytest ; niveau Playwright si e2e/specs existe."""
        gu, vsa = _apply_super_admin_overrides()
        try:
            response = client.get("/api/super-admin/tests/tree")
        finally:
            _clear_super_admin_overrides(gu, vsa)
        assert response.status_code == 200
        data = response.json()
        assert "levels" in data
        ids = {lvl["id"] for lvl in data["levels"]}
        assert "unit" in ids
        assert "integration" in ids

        from app.core.paths import REPO_ROOT

        if (REPO_ROOT / "e2e" / "specs").is_dir():
            assert "playwright" in ids
            pw = next(lvl for lvl in data["levels"] if lvl["id"] == "playwright")
            paths = {c["path"] for c in pw["children"]}
            assert any(str(p).startswith("pw:") for p in paths)

    def test_post_tests_run_empty_targets_returns_error_result(self, client: TestClient):
        """POST avec targets vides : 200 et un résultat d'échec explicite."""
        gu, vsa = _apply_super_admin_overrides()
        try:
            response = client.post("/api/super-admin/tests/run", json={"targets": []})
        finally:
            _clear_super_admin_overrides(gu, vsa)
        assert response.status_code == 200
        body = response.json()
        assert "results" in body
        assert body["results"][0]["success"] is False


# --- 403 quand verify_super_admin échoue ---


class TestSuperAdminForbiddenWhenNotSuperAdmin:
    """403 si l'utilisateur n'est pas super admin."""

    def test_returns_403_when_verify_super_admin_raises(self, client: TestClient):
        """Si verify_super_admin lève (utilisateur pas super admin), 403."""
        from app.core.security import get_current_user
        from app.modules.super_admin.api.router import verify_super_admin
        from fastapi import HTTPException

        app.dependency_overrides[get_current_user] = lambda: _make_super_admin_user()

        def fail():
            raise HTTPException(status_code=403, detail="Accès refusé : vous devez être super administrateur")
        app.dependency_overrides[verify_super_admin] = fail
        try:
            response = client.get("/api/super-admin/dashboard/stats")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(verify_super_admin, None)
        assert response.status_code == 403
