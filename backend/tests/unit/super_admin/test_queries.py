"""
Tests des queries applicatives du module super_admin (application/queries.py).

Infrastructure (infra queries) mockée ; vérification des paramètres et du retour.
"""
from unittest.mock import patch

import pytest

from app.modules.super_admin.application import queries


SUPER_ADMIN_ROW = {"user_id": "uid-1", "is_active": True}


class TestGetGlobalStats:
    """Query get_global_stats."""

    def test_delegates_and_returns_infra_result(self):
        """Délègue à l'infra et retourne le dict stats."""
        infra_result = {
            "companies": {"total": 10, "active": 8, "inactive": 2},
            "users": {"total": 50, "by_role": {"admin": 5}},
            "employees": {"total": 100},
            "super_admins": {"total": 2},
            "top_companies": [],
        }
        with patch(
            "app.modules.super_admin.application.queries.infra_queries.get_global_stats",
            return_value=infra_result,
        ) as m:
            out = queries.get_global_stats(SUPER_ADMIN_ROW)
        m.assert_called_once_with(SUPER_ADMIN_ROW)
        assert out["companies"]["total"] == 10
        assert out["users"]["total"] == 50
        assert out["employees"]["total"] == 100


class TestListCompanies:
    """Query list_companies."""

    def test_delegates_with_defaults(self):
        """Délègue avec skip=0, limit=50 par défaut."""
        infra_result = {"companies": [{"id": "c1", "company_name": "A"}], "total": 1}
        with patch(
            "app.modules.super_admin.application.queries.infra_queries.list_companies",
            return_value=infra_result,
        ) as m:
            out = queries.list_companies()
        m.assert_called_once_with(skip=0, limit=50, search=None, is_active=None)
        assert out["total"] == 1
        assert len(out["companies"]) == 1

    def test_delegates_with_filters(self):
        """Passe search et is_active à l'infra."""
        with patch(
            "app.modules.super_admin.application.queries.infra_queries.list_companies",
            return_value={"companies": [], "total": 0},
        ) as m:
            queries.list_companies(skip=10, limit=20, search="acme", is_active=True)
        m.assert_called_once_with(skip=10, limit=20, search="acme", is_active=True)


class TestGetCompanyDetails:
    """Query get_company_details."""

    def test_delegates_and_returns_company(self):
        """Délègue et retourne les détails entreprise."""
        infra_result = {"id": "c1", "company_name": "Test", "stats": {"employees_count": 5, "users_count": 2}}
        with patch(
            "app.modules.super_admin.application.queries.infra_queries.get_company_details",
            return_value=infra_result,
        ) as m:
            out = queries.get_company_details("c1")
        m.assert_called_once_with("c1")
        assert out["company_name"] == "Test"
        assert out["stats"]["employees_count"] == 5


class TestListAllUsers:
    """Query list_all_users."""

    def test_delegates_with_params(self):
        """Passe skip, limit, company_id, role, search."""
        infra_result = {"users": [{"id": "u1", "email": "u@test.com"}], "total": 1}
        with patch(
            "app.modules.super_admin.application.queries.infra_queries.list_all_users",
            return_value=infra_result,
        ) as m:
            out = queries.list_all_users(
                skip=0, limit=25, company_id="c1", role="admin", search="john"
            )
        m.assert_called_once_with(
            skip=0, limit=25, company_id="c1", role="admin", search="john"
        )
        assert out["total"] == 1
        assert out["users"][0]["email"] == "u@test.com"


class TestGetCompanyUsers:
    """Query get_company_users."""

    def test_delegates_with_role_filter(self):
        """Passe company_id et role optionnel."""
        infra_result = {"users": [], "total": 0}
        with patch(
            "app.modules.super_admin.application.queries.infra_queries.get_company_users",
            return_value=infra_result,
        ) as m:
            queries.get_company_users("c1", role="rh")
        m.assert_called_once_with("c1", role="rh")


class TestListSuperAdmins:
    """Query list_super_admins."""

    def test_delegates_and_returns_list(self):
        """Délègue et retourne { super_admins, total }."""
        infra_result = {"super_admins": [{"id": "sa1", "email": "sa@test.com"}], "total": 1}
        with patch(
            "app.modules.super_admin.application.queries.infra_queries.list_super_admins",
            return_value=infra_result,
        ) as m:
            out = queries.list_super_admins()
        m.assert_called_once()
        assert out["total"] == 1
        assert out["super_admins"][0]["email"] == "sa@test.com"


class TestGetSystemHealth:
    """Query get_system_health."""

    def test_delegates_and_returns_health(self):
        """Délègue et retourne status + checks."""
        infra_result = {"status": "healthy", "checks": {"database": "ok"}}
        with patch(
            "app.modules.super_admin.application.queries.infra_queries.get_system_health",
            return_value=infra_result,
        ) as m:
            out = queries.get_system_health()
        m.assert_called_once()
        assert out["status"] == "healthy"
        assert out["checks"]["database"] == "ok"


class TestGetEmployeesForReductionFillon:
    """Query get_employees_for_reduction_fillon."""

    def test_delegates_and_returns_employees(self):
        """Délègue et retourne { employees, total }."""
        infra_result = {"employees": [{"id": "e1", "name": "Jean Dupont"}], "total": 1}
        with patch(
            "app.modules.super_admin.application.queries.infra_queries.get_employees_for_reduction_fillon",
            return_value=infra_result,
        ) as m:
            out = queries.get_employees_for_reduction_fillon()
        m.assert_called_once()
        assert out["total"] == 1
        assert out["employees"][0]["name"] == "Jean Dupont"


class TestCalculateReductionFillon:
    """Query calculate_reduction_fillon."""

    def test_delegates_with_employee_month_year(self):
        """Passe employee_id, month, year à l'infra."""
        infra_result = {"result": {"libelle": "Réduction Fillon", "montant_patronal": -100}}
        with patch(
            "app.modules.super_admin.application.queries.infra_queries.calculate_reduction_fillon",
            return_value=infra_result,
        ) as m:
            out = queries.calculate_reduction_fillon("e1", 3, 2025)
        m.assert_called_once_with("e1", 3, 2025)
        assert out["result"]["libelle"] == "Réduction Fillon"
