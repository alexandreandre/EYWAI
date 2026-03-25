"""
Smoke tests par module : un appel HTTP minimal par module exposé dans app.api.router.

Vérifient que chaque module répond sans 500 (accepter 200, 401, 403, 404, 422 selon le cas).
Utilise client et auth_headers depuis conftest.
"""

import pytest
from fastapi.testclient import TestClient


# Réponses acceptées pour les smoke tests (pas de 500)
ALLOWED_STATUSES = (200, 401, 403, 404, 422)


pytestmark = pytest.mark.e2e


def _assert_not_500(response, module_name: str):
    assert response.status_code in ALLOWED_STATUSES, (
        f"[{module_name}] Attendu 200/401/403/404/422, reçu {response.status_code}"
    )


# --- users (auth déjà couvert dans test_smoke_global) ---


def test_smoke_users_my_companies(client: TestClient, auth_headers: dict):
    """GET /api/users/my-companies."""
    response = client.get("/api/users/my-companies", headers=auth_headers)
    _assert_not_500(response, "users")


def test_smoke_companies_details(client: TestClient, auth_headers: dict):
    """GET /api/company/details."""
    response = client.get("/api/company/details", headers=auth_headers)
    _assert_not_500(response, "companies")


def test_smoke_employees_list(client: TestClient, auth_headers: dict):
    """GET /api/employees (liste)."""
    response = client.get("/api/employees", headers=auth_headers)
    _assert_not_500(response, "employees")


def test_smoke_access_control_permission_categories(
    client: TestClient, auth_headers: dict
):
    """GET /api/access-control/permission-categories."""
    response = client.get(
        "/api/access-control/permission-categories", headers=auth_headers
    )
    _assert_not_500(response, "access_control")


def test_smoke_absences_list(client: TestClient, auth_headers: dict):
    """GET /api/absences/ (liste)."""
    response = client.get("/api/absences/", headers=auth_headers)
    _assert_not_500(response, "absences")


def test_smoke_schedules_me_cumuls(client: TestClient, auth_headers: dict):
    """GET /api/me/current-cumuls."""
    response = client.get("/api/me/current-cumuls", headers=auth_headers)
    _assert_not_500(response, "schedules_me")


def test_smoke_schedules_rh_apply_model(client: TestClient, auth_headers: dict):
    """POST /api/schedules/apply-model (body minimal)."""
    response = client.post(
        "/api/schedules/apply-model",
        json={"employee_ids": [], "year": 2025, "month": 1},
        headers=auth_headers,
    )
    _assert_not_500(response, "schedules_rh")


def test_smoke_monthly_inputs_catalogue(client: TestClient, auth_headers: dict):
    """GET /api/primes-catalogue (monthly_inputs)."""
    response = client.get("/api/primes-catalogue", headers=auth_headers)
    _assert_not_500(response, "monthly_inputs")


def test_smoke_payslips_me(client: TestClient, auth_headers: dict):
    """GET /api/me/payslips."""
    response = client.get("/api/me/payslips", headers=auth_headers)
    _assert_not_500(response, "payslips")


def test_smoke_exports_history(client: TestClient, auth_headers: dict):
    """GET /api/exports/history."""
    response = client.get("/api/exports/history", headers=auth_headers)
    _assert_not_500(response, "exports")


def test_smoke_rates_all(client: TestClient, auth_headers: dict):
    """GET /api/rates/all."""
    response = client.get("/api/rates/all", headers=auth_headers)
    _assert_not_500(response, "rates")


def test_smoke_dashboard_all(client: TestClient, auth_headers: dict):
    """GET /api/dashboard/all."""
    response = client.get("/api/dashboard/all", headers=auth_headers)
    _assert_not_500(response, "dashboard")


def test_smoke_expenses_me(client: TestClient, auth_headers: dict):
    """GET /api/expenses/me."""
    response = client.get("/api/expenses/me", headers=auth_headers)
    _assert_not_500(response, "expenses")


def test_smoke_annual_reviews_list(client: TestClient, auth_headers: dict):
    """GET /api/annual-reviews."""
    response = client.get("/api/annual-reviews", headers=auth_headers)
    _assert_not_500(response, "annual_reviews")


def test_smoke_employee_exits_list(client: TestClient, auth_headers: dict):
    """GET /api/employee-exits/."""
    response = client.get("/api/employee-exits/", headers=auth_headers)
    _assert_not_500(response, "employee_exits")


def test_smoke_bonus_types_list(client: TestClient, auth_headers: dict):
    """GET /api/bonus-types."""
    response = client.get("/api/bonus-types", headers=auth_headers)
    _assert_not_500(response, "bonus_types")


def test_smoke_collective_agreements_catalog(client: TestClient, auth_headers: dict):
    """GET /api/collective-agreements/catalog."""
    response = client.get("/api/collective-agreements/catalog", headers=auth_headers)
    _assert_not_500(response, "collective_agreements")


def test_smoke_cse_elected_members(client: TestClient, auth_headers: dict):
    """GET /api/cse/elected-members."""
    response = client.get("/api/cse/elected-members", headers=auth_headers)
    _assert_not_500(response, "cse")


def test_smoke_company_groups_list(client: TestClient, auth_headers: dict):
    """GET /api/company-groups/."""
    response = client.get("/api/company-groups/", headers=auth_headers)
    _assert_not_500(response, "company_groups")


def test_smoke_contract_parser_extract(client: TestClient, auth_headers: dict):
    """POST /api/contract-parser/extract-from-pdf (sans fichier → 422 accepté)."""
    response = client.post(
        "/api/contract-parser/extract-from-pdf",
        headers=auth_headers,
    )
    _assert_not_500(response, "contract_parser")


def test_smoke_copilot_query(client: TestClient, auth_headers: dict):
    """POST /api/copilot/query (body minimal)."""
    response = client.post(
        "/api/copilot/query",
        json={"prompt": "test"},
        headers=auth_headers,
    )
    _assert_not_500(response, "copilot")


def test_smoke_medical_follow_up_obligations(client: TestClient, auth_headers: dict):
    """GET /api/medical-follow-up/obligations."""
    response = client.get("/api/medical-follow-up/obligations", headers=auth_headers)
    _assert_not_500(response, "medical_follow_up")


def test_smoke_mutuelle_types_list(client: TestClient, auth_headers: dict):
    """GET /api/mutuelle-types."""
    response = client.get("/api/mutuelle-types", headers=auth_headers)
    _assert_not_500(response, "mutuelle_types")


def test_smoke_participation_simulations(client: TestClient, auth_headers: dict):
    """GET /api/participation/simulations."""
    response = client.get("/api/participation/simulations", headers=auth_headers)
    _assert_not_500(response, "participation")


def test_smoke_promotions_list(client: TestClient, auth_headers: dict):
    """GET /api/promotions."""
    response = client.get("/api/promotions", headers=auth_headers)
    _assert_not_500(response, "promotions")


def test_smoke_recruitment_jobs(client: TestClient, auth_headers: dict):
    """GET /api/recruitment/jobs."""
    response = client.get("/api/recruitment/jobs", headers=auth_headers)
    _assert_not_500(response, "recruitment")


def test_smoke_repos_compensateur_calculer(client: TestClient, auth_headers: dict):
    """POST /api/repos-compensateur/calculer-credits (query params year, month)."""
    response = client.post(
        "/api/repos-compensateur/calculer-credits?year=2025&month=1",
        headers=auth_headers,
    )
    _assert_not_500(response, "repos_compensateur")


def test_smoke_residence_permits_list(client: TestClient, auth_headers: dict):
    """GET /api/residence-permits."""
    response = client.get("/api/residence-permits", headers=auth_headers)
    _assert_not_500(response, "residence_permits")


def test_smoke_rib_alerts_list(client: TestClient, auth_headers: dict):
    """GET /api/rib-alerts."""
    response = client.get("/api/rib-alerts", headers=auth_headers)
    _assert_not_500(response, "rib_alerts")


def test_smoke_saisies_avances_salary_seizures(client: TestClient, auth_headers: dict):
    """GET /api/saisies-avances/salary-seizures."""
    response = client.get("/api/saisies-avances/salary-seizures", headers=auth_headers)
    _assert_not_500(response, "saisies_avances")


def test_smoke_scraping_dashboard(client: TestClient, auth_headers: dict):
    """GET /api/scraping/dashboard."""
    response = client.get("/api/scraping/dashboard", headers=auth_headers)
    _assert_not_500(response, "scraping")


def test_smoke_super_admin_health(client: TestClient, auth_headers: dict):
    """GET /api/super-admin/system/health."""
    response = client.get("/api/super-admin/system/health", headers=auth_headers)
    _assert_not_500(response, "super_admin")


def test_smoke_uploads_delete_logo(client: TestClient, auth_headers: dict):
    """DELETE /api/uploads/logo/company/fake-id (401/404 accepté)."""
    response = client.delete(
        "/api/uploads/logo/company/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    _assert_not_500(response, "uploads")
