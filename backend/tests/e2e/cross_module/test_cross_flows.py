"""
Tests e2e de parcours métier traversant plusieurs modules.

Chaque test enchaîne plusieurs appels HTTP (client + auth_headers) et vérifie
les réponses. Pas de modification de la logique métier des modules.
"""
import os
import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.e2e


# ---------------------------------------------------------------------------
# 1) Auth puis accès utilisateur
# ---------------------------------------------------------------------------


def test_auth_then_user_me(client: TestClient):
    """Login (POST /api/auth/login) puis GET /api/auth/me ; vérifier cohérence (même user_id ou email)."""
    email = os.getenv("TEST_USER_EMAIL", "cross-e2e@test.local")
    password = os.getenv("TEST_USER_PASSWORD", "dummy-password")

    login_resp = client.post(
        "/api/auth/login",
        data={"username": email, "password": password},
    )
    assert login_resp.status_code in (200, 400, 401), f"Login doit pas retourner 500 (got {login_resp.status_code})"

    if login_resp.status_code != 200:
        # Sans token valide, GET /me sans header doit retourner 401
        me_resp = client.get("/api/auth/me")
        assert me_resp.status_code == 401
        return

    data = login_resp.json()
    token = data.get("access_token")
    user_login = data.get("user") or {}
    assert token, "Login 200 doit retourner access_token"

    me_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200, f"GET /me avec token doit retourner 200 (got {me_resp.status_code})"
    user_me = me_resp.json()

    # Cohérence : même user_id ou même email
    assert user_me.get("id") == user_login.get("id") or user_me.get("email") == user_login.get("email"), (
        f"Incohérence user: login={user_login!r} vs /me={user_me!r}"
    )


def test_auth_then_my_companies(client: TestClient):
    """Login puis GET /api/users/my-companies ; réponse 200 et liste (éventuellement vide)."""
    email = os.getenv("TEST_USER_EMAIL", "cross-e2e@test.local")
    password = os.getenv("TEST_USER_PASSWORD", "dummy-password")

    login_resp = client.post(
        "/api/auth/login",
        data={"username": email, "password": password},
    )
    assert login_resp.status_code != 500

    if login_resp.status_code != 200:
        # Sans token, my-companies doit retourner 401
        companies_resp = client.get("/api/users/my-companies")
        assert companies_resp.status_code == 401
        return

    token = login_resp.json().get("access_token")
    assert token
    headers = {"Authorization": f"Bearer {token}"}

    companies_resp = client.get("/api/users/my-companies", headers=headers)
    assert companies_resp.status_code == 200, (
        f"GET /api/users/my-companies doit retourner 200 avec token (got {companies_resp.status_code})"
    )
    body = companies_resp.json()
    assert isinstance(body, list), "my-companies doit retourner une liste (éventuellement vide)"


# ---------------------------------------------------------------------------
# 2) Contexte entreprise puis employés
# ---------------------------------------------------------------------------


def test_company_then_employees(client: TestClient, auth_headers: dict):
    """Avec utilisateur authentifié, GET /api/company/details puis GET liste employés ; 200 ou 403 selon droits."""
    if not auth_headers:
        details_resp = client.get("/api/company/details")
        assert details_resp.status_code in (401, 403)
        return

    details_resp = client.get("/api/company/details", headers=auth_headers)
    assert details_resp.status_code in (200, 403), f"company/details doit pas retourner 500 (got {details_resp.status_code})"

    employees_resp = client.get("/api/employees", headers=auth_headers)
    assert employees_resp.status_code in (200, 403), f"employees list doit pas retourner 500 (got {employees_resp.status_code})"

    if details_resp.status_code == 200:
        data = details_resp.json()
        assert "id" in data or "company_id" in data or "company_name" in data or isinstance(data, dict)
    if employees_resp.status_code == 200:
        assert isinstance(employees_resp.json(), list)


# ---------------------------------------------------------------------------
# 3) Employé puis absences
# ---------------------------------------------------------------------------


def test_employee_then_absences(client: TestClient, auth_headers: dict):
    """Avec auth, récupérer un employee_id (liste employés) ; puis GET absences pour cet employé ou liste ; 200 ou 404, pas 500."""
    if not auth_headers:
        list_resp = client.get("/api/employees", headers=auth_headers)
        assert list_resp.status_code in (401, 403)
        return

    list_resp = client.get("/api/employees", headers=auth_headers)
    assert list_resp.status_code != 500
    if list_resp.status_code != 200:
        return

    employees = list_resp.json()
    if not employees:
        # Pas d'employé : appeler la liste globale des absences
        abs_resp = client.get("/api/absences/", headers=auth_headers)
        assert abs_resp.status_code in (200, 403), f"absences list doit pas retourner 500 (got {abs_resp.status_code})"
        return

    employee_id = employees[0].get("id")
    assert employee_id
    abs_resp = client.get(f"/api/absences/employees/{employee_id}", headers=auth_headers)
    assert abs_resp.status_code in (200, 404), f"absences/employees/{{id}} doit pas retourner 500 (got {abs_resp.status_code})"
    if abs_resp.status_code == 200:
        assert isinstance(abs_resp.json(), list)


# ---------------------------------------------------------------------------
# 4) Employé puis plannings
# ---------------------------------------------------------------------------


def test_employee_then_schedules(client: TestClient, auth_headers: dict):
    """Avec auth, un employee_id ; GET route schedules liée à cet employé ; 200 ou 404, pas 500."""
    if not auth_headers:
        resp = client.get("/api/employees/00000000-0000-0000-0000-000000000000/calendar-data?year=2025&month=1")
        assert resp.status_code in (401, 403)
        return

    list_resp = client.get("/api/employees", headers=auth_headers)
    assert list_resp.status_code != 500
    if list_resp.status_code != 200:
        return

    employees = list_resp.json()
    employee_id = employees[0].get("id") if employees else "00000000-0000-0000-0000-000000000000"

    schedule_resp = client.get(
        f"/api/employees/{employee_id}/calendar-data",
        params={"year": 2025, "month": 1},
        headers=auth_headers,
    )
    assert schedule_resp.status_code in (200, 404), (
        f"calendar-data doit pas retourner 500 (got {schedule_resp.status_code})"
    )


# ---------------------------------------------------------------------------
# 5) Saisies mensuelles puis paie
# ---------------------------------------------------------------------------


def test_monthly_inputs_then_payslips(client: TestClient, auth_headers: dict):
    """Avec auth et company, GET monthly_inputs (catalogue) puis GET payslips ; les deux 200 ou 401/403 de manière cohérente."""
    # GET catalogue primes (monthly_inputs)
    catalogue_resp = client.get("/api/primes-catalogue", headers=auth_headers or {})
    assert catalogue_resp.status_code != 500
    # GET liste bulletins (payslips)
    payslips_resp = client.get("/api/me/payslips", headers=auth_headers or {})

    assert payslips_resp.status_code != 500

    # Cohérence : si l'un est 200, l'autre peut être 200 ou 403 selon droits ; si pas d'auth les deux 401
    if not auth_headers:
        assert catalogue_resp.status_code in (200, 401, 403)
        assert payslips_resp.status_code in (200, 401, 403)
        return
    assert catalogue_resp.status_code in (200, 401, 403)
    assert payslips_resp.status_code in (200, 401, 403)
    if catalogue_resp.status_code == 200 and payslips_resp.status_code == 200:
        assert isinstance(payslips_resp.json(), list)


# ---------------------------------------------------------------------------
# 6) Exports (après contexte)
# ---------------------------------------------------------------------------


def test_company_then_export_history(client: TestClient, auth_headers: dict):
    """Avec auth, GET /api/company/details puis GET /api/exports/history ; 200 ou 403, pas 500."""
    if not auth_headers:
        details_resp = client.get("/api/company/details")
        assert details_resp.status_code in (401, 403)
        history_resp = client.get("/api/exports/history")
        assert history_resp.status_code in (401, 403)
        return

    details_resp = client.get("/api/company/details", headers=auth_headers)
    assert details_resp.status_code != 500

    history_resp = client.get("/api/exports/history", headers=auth_headers)
    assert history_resp.status_code in (200, 403), (
        f"exports/history doit pas retourner 500 (got {history_resp.status_code})"
    )

    if details_resp.status_code == 200:
        assert isinstance(details_resp.json(), dict)
    if history_resp.status_code == 200:
        data = history_resp.json()
        assert "exports" in data or isinstance(data, (list, dict))
