"""
Smoke tests par module : un appel HTTP minimal par module exposé dans app.api.router.

Vérifient que chaque module répond sans 500 (accepter 200, 401, 403, 404, 422 selon le cas).
Utilise client et auth_headers depuis conftest.
"""

import pytest
from fastapi.testclient import TestClient


# Réponses acceptées pour les smoke tests (pas de 500).
# 400 inclus : certains endpoints requièrent des headers (ex. X-Active-Company) ;
# leur absence retourne 400 "Bad Request", ce qui est un comportement correct (pas un crash).
# 502 inclus : échec fournisseur LLM (clé absente/invalide, quota, réseau) mappé côté API.
ALLOWED_STATUSES = (200, 400, 401, 403, 404, 422, 502)


pytestmark = pytest.mark.e2e


def _assert_not_500(response, module_name: str):
    assert response.status_code in ALLOWED_STATUSES, (
        f"[{module_name}] Attendu 200/400/401/403/404/422/502, reçu {response.status_code}"
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


def test_smoke_badgeuse_me_status_today(client: TestClient, auth_headers: dict):
    """GET /api/me/badgeuse/status-today."""
    response = client.get("/api/me/badgeuse/status-today", headers=auth_headers)
    _assert_not_500(response, "badgeuse")


def test_smoke_support_tickets_list(client: TestClient, auth_headers: dict):
    """GET /api/support/tickets."""
    response = client.get("/api/support/tickets", headers=auth_headers)
    _assert_not_500(response, "support")


def test_smoke_maintenance_settings_get(client: TestClient, auth_headers: dict):
    """GET /api/maintenance-settings/."""
    response = client.get("/api/maintenance-settings/", headers=auth_headers)
    _assert_not_500(response, "maintenance_settings")


def test_smoke_payroll_simulation_arret_maladie(client: TestClient, auth_headers: dict):
    """POST /api/simulation/arret-maladie (body absent → 422 accepté)."""
    response = client.post(
        "/api/simulation/arret-maladie",
        headers=auth_headers,
    )
    _assert_not_500(response, "payroll")


def test_smoke_planning_week(client: TestClient, auth_headers: dict):
    """GET /api/planning/week."""
    response = client.get("/api/planning/week", headers=auth_headers)
    _assert_not_500(response, "planning")


def test_smoke_signatures_pending(client: TestClient, auth_headers: dict):
    """GET /api/signatures/pending."""
    response = client.get("/api/signatures/pending", headers=auth_headers)
    _assert_not_500(response, "signatures")


def test_smoke_teams_list(client: TestClient, auth_headers: dict):
    """GET /api/teams."""
    response = client.get("/api/teams", headers=auth_headers)
    _assert_not_500(response, "teams")


def test_smoke_accounting_integration_config(client: TestClient, auth_headers: dict):
    """GET /api/accounting-integration/config."""
    response = client.get("/api/accounting-integration/config", headers=auth_headers)
    _assert_not_500(response, "accounting_integration")


def test_smoke_admin_import_company_setup_status(client: TestClient, auth_headers: dict):
    """GET /api/admin-import/company-setup-status."""
    response = client.get(
        "/api/admin-import/company-setup-status", headers=auth_headers
    )
    _assert_not_500(response, "admin_import")


def test_smoke_audit_logs(client: TestClient, auth_headers: dict):
    """GET /api/audit/logs."""
    response = client.get("/api/audit/logs", headers=auth_headers)
    _assert_not_500(response, "audit")


def test_smoke_certifications_dashboard_counts(client: TestClient, auth_headers: dict):
    """GET /api/certifications/dashboard-counts."""
    response = client.get(
        "/api/certifications/dashboard-counts", headers=auth_headers
    )
    _assert_not_500(response, "certifications")


def test_smoke_cet_settings(client: TestClient, auth_headers: dict):
    """GET /api/cet/settings."""
    response = client.get("/api/cet/settings", headers=auth_headers)
    _assert_not_500(response, "cet")


def test_smoke_competencies_refs(client: TestClient, auth_headers: dict):
    """GET /api/competencies/refs."""
    response = client.get("/api/competencies/refs", headers=auth_headers)
    _assert_not_500(response, "competencies")


def test_smoke_document_library_list(client: TestClient, auth_headers: dict):
    """GET /api/document-library/."""
    response = client.get("/api/document-library/", headers=auth_headers)
    _assert_not_500(response, "document_library")


def test_smoke_documents_explorer(client: TestClient, auth_headers: dict):
    """GET /api/documents/explorer."""
    response = client.get("/api/documents/explorer", headers=auth_headers)
    _assert_not_500(response, "documents")


def test_smoke_dsn_import_coverage(client: TestClient, auth_headers: dict):
    """GET /api/dsn-import/coverage."""
    response = client.get("/api/dsn-import/coverage", headers=auth_headers)
    _assert_not_500(response, "dsn_import")


def test_smoke_employee_loans_list(client: TestClient, auth_headers: dict):
    """GET /api/employee-loans/."""
    response = client.get("/api/employee-loans/", headers=auth_headers)
    _assert_not_500(response, "employee_loans")


def test_smoke_ijss_tracking_periods(client: TestClient, auth_headers: dict):
    """GET /api/ijss-tracking/periods."""
    response = client.get("/api/ijss-tracking/periods", headers=auth_headers)
    _assert_not_500(response, "ijss_tracking")


def test_smoke_interview_templates_list(client: TestClient, auth_headers: dict):
    """GET /api/interview-templates."""
    response = client.get("/api/interview-templates", headers=auth_headers)
    _assert_not_500(response, "interview_templates")


def test_smoke_jei_settings_get(client: TestClient, auth_headers: dict):
    """GET /api/jei-settings/."""
    response = client.get("/api/jei-settings/", headers=auth_headers)
    _assert_not_500(response, "jei_settings")


def test_smoke_legal_obligations_overdue_count(client: TestClient, auth_headers: dict):
    """GET /api/legal-obligations/count/overdue."""
    response = client.get(
        "/api/legal-obligations/count/overdue", headers=auth_headers
    )
    _assert_not_500(response, "legal_obligations")


def test_smoke_modulation_settings(client: TestClient, auth_headers: dict):
    """GET /api/modulation/settings."""
    response = client.get("/api/modulation/settings", headers=auth_headers)
    _assert_not_500(response, "modulation")


def test_smoke_net_entreprises_config(client: TestClient, auth_headers: dict):
    """GET /api/net-entreprises/config."""
    response = client.get("/api/net-entreprises/config", headers=auth_headers)
    _assert_not_500(response, "net_entreprises")


def test_smoke_notifications_unread_count(client: TestClient, auth_headers: dict):
    """GET /api/notifications/unread-count."""
    response = client.get("/api/notifications/unread-count", headers=auth_headers)
    _assert_not_500(response, "notifications")


def test_smoke_objectives_achievement_rate(client: TestClient, auth_headers: dict):
    """GET /api/objectives/achievement-rate."""
    response = client.get("/api/objectives/achievement-rate", headers=auth_headers)
    _assert_not_500(response, "objectives")


def test_smoke_oeth_settings_get(client: TestClient, auth_headers: dict):
    """GET /api/oeth-settings/."""
    response = client.get("/api/oeth-settings/", headers=auth_headers)
    _assert_not_500(response, "oeth_settings")


def test_smoke_onboarding_me(client: TestClient, auth_headers: dict):
    """GET /api/onboarding/me."""
    response = client.get("/api/onboarding/me", headers=auth_headers)
    _assert_not_500(response, "onboarding")


def test_smoke_payroll_variables_rules(client: TestClient, auth_headers: dict):
    """GET /api/payroll-variables/rules."""
    response = client.get("/api/payroll-variables/rules", headers=auth_headers)
    _assert_not_500(response, "payroll_variables")


def test_smoke_platform_settings_email(client: TestClient, auth_headers: dict):
    """GET /api/super-admin/email-settings."""
    response = client.get("/api/super-admin/email-settings", headers=auth_headers)
    _assert_not_500(response, "platform_settings")


def test_smoke_prime_anciennete_settings_get(client: TestClient, auth_headers: dict):
    """GET /api/prime-anciennete-settings/."""
    response = client.get("/api/prime-anciennete-settings/", headers=auth_headers)
    _assert_not_500(response, "prime_anciennete_settings")


def test_smoke_test_env_status(client: TestClient, auth_headers: dict):
    """GET /api/test-env/status."""
    response = client.get("/api/test-env/status", headers=auth_headers)
    _assert_not_500(response, "test_env")


def test_smoke_training_catalog(client: TestClient, auth_headers: dict):
    """GET /api/training/catalog."""
    response = client.get("/api/training/catalog", headers=auth_headers)
    _assert_not_500(response, "training")


def test_smoke_training_budget_year(client: TestClient, auth_headers: dict):
    """GET /api/training-budget/2026."""
    response = client.get("/api/training-budget/2026", headers=auth_headers)
    _assert_not_500(response, "training_budget")


def test_smoke_webhooks_list(client: TestClient, auth_headers: dict):
    """GET /api/webhooks."""
    response = client.get("/api/webhooks", headers=auth_headers)
    _assert_not_500(response, "webhooks")


def test_smoke_work_medals_summary(client: TestClient, auth_headers: dict):
    """GET /api/work-medals/summary."""
    response = client.get("/api/work-medals/summary", headers=auth_headers)
    _assert_not_500(response, "work_medals")
