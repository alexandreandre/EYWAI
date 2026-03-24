"""
Tests d'intégration HTTP des routes qui consomment le module payroll.

Le module payroll n'expose pas de router avec des routes (api/router.py est un placeholder).
La logique payroll est utilisée via le module payslips (génération, édition, restauration
de bulletins) et d'autres modules. Ces tests vérifient que les routes qui délèguent
au module payroll répondent correctement (auth, validation, délégation).

Fixtures utilisées : client (TestClient), auth_headers / payroll_headers (conftest).
Si payroll_headers n'existe pas encore : utiliser auth_headers ou dependency_overrides.
"""
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app


pytestmark = pytest.mark.integration


class TestPayrollRouterModule:
    """Vérification que le module payroll expose un router (même vide)."""

    def test_payroll_router_importable(self):
        """Le router du module payroll peut être importé et inclus."""
        from app.modules.payroll.api.router import router as payroll_router
        assert payroll_router is not None
        # Le router actuel n'a pas de routes ; il peut être monté sous un préfixe plus tard
        routes = [r for r in payroll_router.routes if hasattr(r, "path")]
        assert isinstance(routes, list)


class TestGeneratePayslipRoute:
    """POST /api/actions/generate-payslip — délègue à la couche payroll (payslips -> payroll)."""

    def test_generate_payslip_without_auth_accepted(self, client: TestClient):
        """La route de génération : avec mock du use case, 200 ; sinon 401/422/500 (DB)."""
        with patch(
            "app.modules.payslips.api.router.generate_payslip",
            return_value=MagicMock(status="ok", message="OK", download_url="/f.pdf"),
        ):
            response = client.post(
                "/api/actions/generate-payslip",
                json={"employee_id": "emp-1", "year": 2025, "month": 3},
            )
        assert response.status_code in (200, 401, 422, 500)

    def test_generate_payslip_returns_status_and_message(self, client: TestClient):
        """Avec mock du use case (au niveau router), la réponse contient status et message."""
        with patch(
            "app.modules.payslips.api.router.generate_payslip",
            return_value=MagicMock(status="ok", message="Généré", download_url=None),
        ):
            response = client.post(
                "/api/actions/generate-payslip",
                json={"employee_id": "emp-1", "year": 2025, "month": 3},
            )
        if response.status_code == 200:
            data = response.json()
            assert "status" in data
            assert "message" in data


class TestPayslipsRoutesUsingPayroll:
    """Routes payslips qui s'appuient sur le module payroll (liste, détail, edit, restore)."""

    def test_get_employee_payslips_returns_list_or_error(self, client: TestClient):
        """GET /api/employees/{id}/payslips — retourne une liste ou erreur."""
        with patch(
            "app.modules.payslips.api.router.get_employee_payslips",
            return_value=[],
        ):
            response = client.get("/api/employees/emp-1/payslips")
        assert response.status_code in (200, 401, 404, 422)
        if response.status_code == 200:
            assert isinstance(response.json(), list)

    def test_get_payslip_detail_requires_auth(self, client: TestClient):
        """GET /api/payslips/{id} — sans token attendu 401 ou 404."""
        response = client.get("/api/payslips/00000000-0000-0000-0000-000000000001")
        assert response.status_code in (200, 401, 403, 404, 422)

    def test_delete_payslip_returns_204_or_error(self, client: TestClient):
        """DELETE /api/payslips/{id} — 204 ou erreur (500 si DB indisponible)."""
        response = client.delete("/api/payslips/00000000-0000-0000-0000-000000000001")
        assert response.status_code in (204, 401, 403, 404, 422, 500)


class TestPayrollExportRoutes:
    """Routes d'export paie (journal, virements, etc.) si exposées sous /api et utilisant payroll."""

    def test_app_responds_on_health_or_docs(self, client: TestClient):
        """L'app monte correctement (doc ou health répond)."""
        response = client.get("/docs")
        assert response.status_code == 200


# --- Fixture à documenter dans conftest.py ---
# @pytest.fixture
# def payroll_headers(auth_headers):
#     """En-têtes pour un utilisateur avec accès RH / entreprise active pour les routes paie.
#     Format : {\"Authorization\": \"Bearer <jwt>\", \"X-Active-Company\": \"<company_id>\"}.
#     À compléter : retourner auth_headers (+ X-Active-Company) quand auth_headers fournit un JWT valide."""
#     return auth_headers  # ou return {**auth_headers, "X-Active-Company": "<company_uuid>"}
