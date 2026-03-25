# Fixtures partagées pour tests unitaires et d'intégration.
# Utilisables par tests/unit/<module>/ et tests/integration/<module>/.

import os
import pytest

# Scripts manuels nommés test_*.py mais non destinés à pytest (code au niveau module).
collect_ignore = [
    "test_login.py",
    "test_absenteeism.py",
]


from fastapi.testclient import TestClient

from app.main import app


# ---------------------------------------------------------------------------
# 1) Client HTTP
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    """Client HTTP de test (TestClient sur app.main.app). Utilisable pour tous les tests API."""
    return TestClient(app)


@pytest.fixture
def async_client():
    """Client HTTP async (httpx.AsyncClient) pour tests async. Optionnel : requiert httpx et pytest-asyncio.
    Usage : dans un test marqué @pytest.mark.asyncio, injecter async_client et l'utiliser pour des requêtes async."""
    try:
        import httpx
        from httpx import ASGITransport
    except ImportError:
        pytest.skip("httpx requis pour async_client (pip install httpx)")
    transport = ASGITransport(app=app)
    # Retourne un contexte : les tests async devront utiliser "async with async_client:" ou
    # instancier eux-mêmes httpx.AsyncClient(transport=transport).
    return (transport, app)


# ---------------------------------------------------------------------------
# 2) Authentification
# ---------------------------------------------------------------------------
# Variables d'environnement optionnelles pour auth_headers (login réel) :
#   - TEST_USER_EMAIL : email de l'utilisateur de test (Supabase Auth).
#   - TEST_USER_PASSWORD : mot de passe de l'utilisateur de test.
# Si absentes ou si le login échoue, auth_headers retourne {} : les tests qui
# utilisent auth_headers gèrent déjà ce cas (401 ou skip). Pour des tests E2E
# avec token valide, définir ces variables ou créer un utilisateur de test en DB.


@pytest.fixture
def auth_headers(client: TestClient):
    """En-têtes avec token Bearer pour requêtes authentifiées.
    Tente un login via POST /api/auth/login avec TEST_USER_EMAIL et TEST_USER_PASSWORD.
    En cas d'absence de variables ou d'échec du login, retourne {} (les tests existants
    vérifient alors 401 ou acceptent 200/401 selon le cas)."""
    email = os.getenv("TEST_USER_EMAIL")
    password = os.getenv("TEST_USER_PASSWORD")
    if not email or not password:
        return {}
    response = client.post(
        "/api/auth/login",
        data={"username": email, "password": password},
    )
    if response.status_code != 200:
        return {}
    data = response.json()
    token = data.get("access_token")
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 3) Base de données / Supabase
# ---------------------------------------------------------------------------
# - Tests unitaires : mocker get_supabase_client() / get_supabase_admin_client()
#   dans le module testé (pas besoin de DB réelle).
# - Tests d'intégration avec DB réelle : utiliser la fixture supabase_client
#   (ou db_session si vous préférez le nom session). Pour pointer vers un projet
#   Supabase de test, définir SUPABASE_TEST_URL et SUPABASE_TEST_KEY ; sinon
#   le client utilise la config par défaut (SUPABASE_URL, SUPABASE_KEY).


@pytest.fixture
def db_session(supabase_client):
    """Session ou client DB de test pour tests repository / intégration.
    Par défaut retourne le même client que supabase_client (ou None si Supabase non configuré).
    Pour les tests unitaires, continuer à mocker le repository ou get_supabase_client()."""
    return supabase_client


@pytest.fixture
def supabase_client():
    """Client Supabase pour tests d'intégration. Utilise get_supabase_client() sauf si
    SUPABASE_TEST_URL et SUPABASE_TEST_KEY sont définis (projet Supabase de test dédié).
    En cas d'erreur (env manquants), retourne None ; les tests qui en dépendent peuvent skip."""
    try:
        if os.getenv("SUPABASE_TEST_URL") and os.getenv("SUPABASE_TEST_KEY"):
            from supabase import create_client
            return create_client(
                os.environ["SUPABASE_TEST_URL"],
                os.environ["SUPABASE_TEST_KEY"],
            )
        from app.core.database import get_supabase_client
        return get_supabase_client()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 4) Données de test minimales (optionnel)
# ---------------------------------------------------------------------------
# IDs de test pour les tests d'intégration qui en ont besoin. Récupérés depuis
# la DB de test (via supabase_client) ou des variables d'env si env de test dédiée.
# Sinon None : les tests par module peuvent fournir leurs propres fixtures ou
# constantes (ex. tests/integration/companies/conftest.py avec company_id de test).


@pytest.fixture
def test_user_id(supabase_client):
    """user_id (auth.users.id) de test. Variable d'env TEST_USER_ID ou dérivé du login auth_headers."""
    uid = os.getenv("TEST_USER_ID")
    if uid:
        return uid
    if supabase_client is None:
        return None
    # Optionnel : récupérer depuis la table profiles après un login si besoin
    return None


@pytest.fixture
def test_company_id(supabase_client):
    """company_id de test. Variable d'env TEST_COMPANY_ID ou première company en DB de test."""
    cid = os.getenv("TEST_COMPANY_ID")
    if cid:
        return cid
    if supabase_client is None:
        return None
    try:
        r = supabase_client.table("companies").select("id").limit(1).execute()
        if r.data and len(r.data) > 0:
            return r.data[0].get("id")
    except Exception:
        pass
    return None


@pytest.fixture
def test_employee_id(supabase_client, test_company_id):
    """employee_id de test. Variable d'env TEST_EMPLOYEE_ID ou premier employé de test_company_id."""
    eid = os.getenv("TEST_EMPLOYEE_ID")
    if eid:
        return eid
    if supabase_client is None or not test_company_id:
        return None
    try:
        r = (
            supabase_client.table("employees")
            .select("id")
            .eq("company_id", test_company_id)
            .limit(1)
            .execute()
        )
        if r.data and len(r.data) > 0:
            return r.data[0].get("id")
    except Exception:
        pass
    return None


# Fixture optionnelle pour les tests du module employees (tests/integration/employees/test_api.py) :
# @pytest.fixture
# def employees_headers():
#     """En-têtes avec token Bearer pour un utilisateur ayant active_company_id et droits RH.
#     Même format que auth_headers ; peut réutiliser auth_headers si un utilisateur de test a une company."""
#     return {}  # ou return auth_headers si disponible

# --- Module companies (tests/unit/companies/, tests/integration/companies/) ---
# Les tests d'intégration API utilisent dependency_overrides pour get_current_user et des mocks
# pour le repository / fetch_company_with_employees_and_payslips / get_company_id_from_profile
# (pas de JWT ni DB réels). Fixture à ajouter si besoin de tests E2E avec token réel :
# @pytest.fixture
# def companies_headers(auth_headers):
#     """En-têtes pour un utilisateur avec active_company_id et droits RH (pour GET/PATCH /api/company/*).
#     Format : {\"Authorization\": \"Bearer <jwt>\", \"X-Active-Company\": \"<company_id>\"}.
#     À compléter : retourner auth_headers + X-Active-Company si le token de test a une company et droits RH."""
#     return auth_headers  # ou return {**auth_headers, "X-Active-Company": "<company_uuid>"}

# Fixture optionnelle pour les tests du module access_control (tests/integration/access_control/test_api.py) :
# @pytest.fixture
# def access_control_headers(auth_headers):
#     """En-têtes avec token Bearer pour un utilisateur ayant au moins un accès RH à une entreprise.
#     Utiliser auth_headers si le token de test a déjà les droits RH ; sinon créer un token
#     pour un utilisateur avec rôle admin/rh/collaborateur_rh (ou custom avec permissions RH)."""
#     return auth_headers  # ou return {"Authorization": "Bearer <token_rh>"}

# --- Module collective_agreements (tests/unit/collective_agreements/, tests/integration/collective_agreements/) ---
# Les tests d'intégration API utilisent dependency_overrides pour get_current_user (pas de JWT réel requis).
# Fixture à ajouter si besoin de tests E2E avec token réel :
# @pytest.fixture
# def collective_agreements_headers(auth_headers):
#     """En-têtes pour un utilisateur avec active_company_id et droits RH (ou super_admin pour catalogue).
#     Format : {\"Authorization\": \"Bearer <jwt>\", \"X-Active-Company\": \"<company_id>\"}.
#     À compléter : retourner auth_headers + X-Active-Company si le token de test a une company et droits RH."""
#     return auth_headers  # ou return {**auth_headers, "X-Active-Company": "<company_uuid>"}
#
# Pour tests repository contre une DB de test réelle (optionnel) :
# @pytest.fixture
# def collective_agreements_db_client(db_session):
#     """Client Supabase (ou session) pour les tables collective_agreements_catalog,
#     company_collective_agreements, convention_classifications, collective_agreement_texts.
#     À compléter en 8.2 si db_session fournit un client Supabase de test."""
#     return db_session

# --- Module absences (tests/unit/absences/, tests/integration/absences/) ---
# Les tests d’intégration API utilisent :
#   - client : TestClient(app) — déjà défini ci-dessus.
#   - auth_headers : pour les routes protégées (GET/POST /employees/me/*, get-upload-url,
#     PATCH .../status, certificate). À compléter avec un token valide, ex. :
#     {"Authorization": "Bearer <jwt>"}. Pour les routes /employees/me/*, l’utilisateur
#     authentifié doit avoir un employé associé (employees.id = user.id ou employees.user_id = user.id)
#     pour éviter 404 sur soldes / page-data.
#   - db_session : non utilisé par les tests absences actuels (repository testé via mocks).
# Pour des tests bout en bout avec DB réelle, prévoir des données de test dans absence_requests,
# employees (hire_date), et éventuellement salary_certificates.

# --- Module annual_reviews (tests/unit/annual_reviews/, tests/integration/annual_reviews/) ---
# Les tests d'intégration API utilisent dependency_overrides pour get_current_user et des mocks
# pour le repository, donc pas de JWT ni DB réels par défaut.
# Fixture à ajouter si besoin de tests avec token réel :
# @pytest.fixture
# def annual_reviews_headers():
#     """En-têtes pour un utilisateur avec active_company_id et droits RH.
#     À compléter : retourner {\"Authorization\": \"Bearer <jwt>\"} où le JWT correspond à un
#     utilisateur ayant active_company_id renseigné et has_rh_access_in_company(active_company_id)=True."""
#     return {}

# --- Module contract_parser (tests/unit/contract_parser/, tests/integration/contract_parser/) ---
# Les tests d'intégration API utilisent :
#   - client : TestClient(app) — déjà défini ci-dessus.
#   - dependency_overrides[get_current_user] : pour injecter un utilisateur de test (User avec
#     active_company_id et droits RH) ; pas de JWT réel.
#   - patch des commandes (extract_contract_from_pdf, etc.) dans le router pour éviter LLM/PDF réel.
# Fixture optionnelle si besoin de tests E2E avec token réel :
# @pytest.fixture
# def contract_parser_headers(auth_headers):
#     """En-têtes pour un utilisateur authentifié appelant les routes /api/contract-parser/*.
#     Format : {\"Authorization\": \"Bearer <jwt>\", \"X-Active-Company\": \"<company_id>\"} (optionnel).
#     À compléter : retourner auth_headers (ou auth_headers + X-Active-Company) quand auth_headers fournit un JWT valide."""
#     return auth_headers  # ou return {} si auth_headers non disponible

# --- Module bonus_types (tests/unit/bonus_types/, tests/integration/bonus_types/) ---
# Les tests d'intégration API utilisent :
#   - client : TestClient(app) — déjà défini ci-dessus.
#   - dependency_overrides[get_current_user] : pour injecter un utilisateur de test (User avec
#     active_company_id et has_rh_access_in_company) ; pas de JWT réel.
#   - patch de get_bonus_types_service (queries/commands) : pour mocker le service et éviter la DB.
# Les tests repository (test_repository.py) mockent Supabase ; pour des tests contre une DB de test,
# ajouter une fixture db_session (connexion à la DB de test) et des données dans company_bonus_types.
# Fixture optionnelle si besoin de tests API avec token réel :
# @pytest.fixture
# def bonus_types_headers():
#     """En-têtes pour un utilisateur avec active_company_id et droits RH (Admin/RH).
#     À compléter : retourner {\"Authorization\": \"Bearer <jwt>\", \"X-Active-Company\": \"<company_id>\"}."""
#     return {}

# --- Module company_groups (tests/unit/company_groups/, tests/integration/company_groups/) ---
# Les tests d'intégration API utilisent :
#   - client : TestClient(app) — déjà défini ci-dessus.
#   - dependency_overrides[get_current_user] : pour injecter un utilisateur de test (User avec
#     is_super_admin et/ou accessible_companies, is_admin_in_company) ; pas de JWT réel.
#   - patch des application commands/queries : pour mocker la couche application et éviter la DB.
# Les tests repository (test_repository.py) mockent Supabase ; pour des tests contre une DB de test,
# ajouter une fixture db_session et des données dans company_groups, companies (group_id),
# user_company_accesses, profiles.
# Fixture à ajouter si besoin de tests E2E avec token réel :
# @pytest.fixture
# def company_groups_headers(auth_headers):
#     """En-têtes pour un utilisateur super_admin ou admin de plusieurs entreprises (création groupe)
#     ou admin des entreprises du groupe (modification). Format : {\"Authorization\": \"Bearer <jwt>\"}.
#     Optionnel : \"X-Active-Company\": \"<company_id>\" pour le contexte entreprise active."""
#     return auth_headers  # ou return {**auth_headers, "X-Active-Company": "<company_uuid>"}
#
# --- Module copilot (tests/unit/copilot/, tests/integration/copilot/) ---
# Les tests d'intégration API utilisent :
#   - client : TestClient(app) — déjà défini ci-dessus.
#   - dependency_overrides[get_current_user] : pour injecter un utilisateur de test (objet avec .id),
#     pas de JWT réel. Les commandes (execute_text_to_sql, handle_agent_query) sont mockées pour
#     éviter OpenAI et la DB.
# Les tests repository (test_repository.py) mockent get_supabase_client ; pour des tests contre une
# DB de test, ajouter une fixture db_session et des données dans profiles (company_id), employees,
# company_collective_agreements, collective_agreement_texts.
# Fixture à ajouter si besoin de tests E2E avec token réel (sans mocker les commandes) :
# @pytest.fixture
# def copilot_headers(auth_headers):
#     """En-têtes pour un utilisateur authentifié appelant POST /api/copilot/query et
#     POST /api/copilot/query-agent. Format : {\"Authorization\": \"Bearer <jwt>\"}.
#     L'utilisateur doit avoir un company_id dans profiles pour que l'agent résolve le contexte."""
#     return auth_headers

# --- Module cse (tests/unit/cse/, tests/integration/cse/) ---
# Les tests d'intégration API utilisent :
#   - client : TestClient(app) — déjà défini ci-dessus.
#   - dependency_overrides[get_current_user] : pour injecter un utilisateur RH de test (User avec
#     active_company_id et has_rh_access_in_company(active_company_id)=True). Les commandes et
#     queries sont mockées pour éviter la DB réelle.
# Fixture à ajouter si besoin de tests E2E avec JWT réel (sans mocker commands/queries) :
# @pytest.fixture
# def cse_headers(auth_headers):
#     """En-têtes pour un utilisateur RH appelant les routes /api/cse/*.
#     Format : {\"Authorization\": \"Bearer <jwt>\", \"X-Active-Company\": \"<company_id>\"}.
#     À compléter : retourner auth_headers (ou auth_headers + X-Active-Company) quand auth_headers
#     fournit un JWT valide pour un utilisateur ayant active_company_id et droits RH (admin/rh/
#     collaborateur_rh) sur cette entreprise."""
#     return auth_headers  # ou return {**auth_headers, "X-Active-Company": "<company_uuid>"}
#
# --- Module expenses (tests/unit/expenses/, tests/integration/expenses/) ---
# Les tests d'intégration API utilisent :
#   - client : TestClient(app) — déjà défini ci-dessus.
#   - dependency_overrides[get_current_user] : pour injecter un User de test (id = employee_id
#     pour les routes /me et POST /). Pas de JWT réel.
#   - patch de _expense_service (router) ou ExpenseRepository/ExpenseStorageProvider (commands/
#     queries) pour éviter DB et storage réels.
# Fixture optionnelle si besoin de tests E2E avec token réel :
# @pytest.fixture
# def expenses_headers(auth_headers):
#     """En-têtes pour un utilisateur authentifié appelant les routes /api/expenses/* (get-upload-url,
#     POST /, GET /me, GET /, PATCH /{id}/status). L'utilisateur doit avoir un employé associé
#     (employee_id = user.id) pour créer et lister ses notes de frais. Format : {\"Authorization\":
#     \"Bearer <jwt>\"}. À compléter : retourner auth_headers quand auth_headers fournit un JWT valide."""
#     return auth_headers
#
# --- Module dashboard (tests/unit/dashboard/, tests/integration/dashboard/) ---
# Les tests d'intégration API utilisent dependency_overrides pour get_current_user (User avec
# active_company_id et has_rh_access_in_company(company_id)=True) ; pas de JWT réel requis.
# Fixture à ajouter si besoin de tests E2E avec token réel :
# @pytest.fixture
# def dashboard_headers(auth_headers):
#     """En-têtes pour un utilisateur avec entreprise active et accès RH (GET /api/dashboard/all,
#     GET /api/dashboard/residence-permit-stats). Format : {\"Authorization\": \"Bearer <jwt>\",
#     \"X-Active-Company\": \"<company_id>\" (optionnel). À compléter : retourner auth_headers
#     (+ X-Active-Company) quand auth_headers fournit un JWT valide pour un utilisateur RH."""
#     return auth_headers  # ou return {**auth_headers, "X-Active-Company": "<company_uuid>"}
#
# --- Module residence_permits (tests/unit/residence_permits/, tests/integration/residence_permits/) ---
# Les tests d'intégration API utilisent client, dependency_overrides pour get_current_user
# (User avec active_company_id et has_rh_access_in_company) et patch de get_residence_permits_list
# pour éviter la DB réelle.
# Fixture à ajouter si besoin de tests E2E avec token réel :
# @pytest.fixture
# def residence_permits_headers(auth_headers):
#     """En-têtes pour GET /api/residence-permits. L'utilisateur doit avoir active_company_id
#     renseigné et has_rh_access_in_company(active_company_id)=True.
#     Format : {\"Authorization\": \"Bearer <jwt>\", \"X-Active-Company\": \"<company_id>\" (optionnel).
#     À compléter : retourner auth_headers quand auth_headers fournit un JWT valide pour un
#     utilisateur ayant active_company_id et has_rh_access_in_company(active_company_id)=True."""
#     return auth_headers  # ou return {**auth_headers, "X-Active-Company": "<company_uuid>"}
#
# Pour tests repository contre une DB de test réelle (optionnel) :
# @pytest.fixture
# def residence_permits_db_session(db_session):
#     """Session ou client DB pour la table employees (is_subject_to_residence_permit,
#     residence_permit_expiry_date, employment_status). À compléter si db_session fournit
#     un client Supabase de test avec données employees."""
#     return db_session
#
# --- Module employee_exits (tests/unit/employee_exits/, tests/integration/employee_exits/) ---
# Les tests d'intégration API utilisent dependency_overrides pour get_current_user (User avec
# active_company_id et rôle admin/rh) et patch des commands/queries ; pas de JWT ni DB réels.
# Fixture à ajouter si besoin de tests E2E avec token réel :
# @pytest.fixture
# def employee_exits_headers(auth_headers):
#     """En-têtes pour un utilisateur avec active_company_id et droits RH sur les sorties (admin/rh).
#     Format : {\"Authorization\": \"Bearer <jwt>\", \"X-Active-Company\": \"<company_id>\"}."""
#     return auth_headers  # ou return {**auth_headers, "X-Active-Company": "<company_uuid>"}
#
# --- Module medical_follow_up (tests/unit/medical_follow_up/, tests/integration/medical_follow_up/) ---
# Les tests d'intégration API utilisent dependency_overrides pour get_current_user (User avec
# active_company_id et has_rh_access_in_company) et patch pour get_obligation_repository /
# get_settings_provider ; pas de JWT ni DB réels.
# Fixture à ajouter si besoin de tests E2E avec token réel :
# @pytest.fixture
# def medical_follow_up_headers(auth_headers):
#     """En-têtes pour un utilisateur avec active_company_id et droits RH (GET/PATCH/POST
#     /api/medical-follow-up/obligations, /kpis, /me, /settings). Format : {\"Authorization\":
#     \"Bearer <jwt>\", \"X-Active-Company\": \"<company_id>\" (optionnel). À compléter :
#     retourner auth_headers quand auth_headers fournit un JWT valide pour un utilisateur ayant
#     active_company_id et has_rh_access_in_company(active_company_id)=True (routes RH) ou au moins
#     un employé associé pour GET /me."""
#     return auth_headers  # ou return {**auth_headers, "X-Active-Company": "<company_uuid>"}
#
# --- Module participation (tests/unit/participation/, tests/integration/participation/) ---
# Les tests d'intégration API utilisent dependency_overrides pour get_current_user (objet avec
# .id et .active_company_id, contrat ParticipationUserContext) et patch de get_participation_service
# pour éviter la DB réelle. Fixture à ajouter si besoin de tests E2E avec token réel :
# @pytest.fixture
# def participation_headers(auth_headers):
#     """En-têtes pour les routes /api/participation/* (employee-data/{year}, simulations CRUD).
#     L'utilisateur doit avoir active_company_id renseigné pour accéder aux données et simulations.
#     Format : {\"Authorization\": \"Bearer <jwt>\", \"X-Active-Company\": \"<company_id>\" (optionnel)."""
#     return auth_headers  # ou return {**auth_headers, "X-Active-Company": "<company_uuid>"}
#
# --- Module monthly_inputs (tests/unit/monthly_inputs/, tests/integration/monthly_inputs/) ---
# Les tests d'intégration API utilisent client + mock des commands/queries (pas d'auth sur le routeur actuel).
# Fixture optionnelle si ajout d'auth sur les routes monthly-inputs plus tard :
# @pytest.fixture
# def monthly_inputs_headers(auth_headers):
#     """En-têtes pour les routes /api/monthly-inputs et /api/employees/{id}/monthly-inputs, /api/primes-catalogue.
#     Format : {\"Authorization\": \"Bearer <jwt>\", \"X-Active-Company\": \"<company_id>\" (optionnel)."""
#     return auth_headers
#
# --- Module mutuelle_types (tests/unit/mutuelle_types/, tests/integration/mutuelle_types/) ---
# Les tests d'intégration API utilisent client, dependency_overrides pour get_current_user
# (User avec active_company_id et has_rh_access_in_company pour create/update/delete) et patch
# des fonctions application (list_mutuelle_types, create_mutuelle_type, etc.) ou du repository.
# Fixture à ajouter si besoin de tests E2E avec token réel :
# @pytest.fixture
# def mutuelle_types_headers(auth_headers):
#     """En-têtes pour un utilisateur avec active_company_id et droits RH (Admin/RH) pour
#     GET/POST/PUT/DELETE /api/mutuelle-types. Format : {\"Authorization\": \"Bearer <jwt>\",
#     \"X-Active-Company\": \"<company_id>\" (optionnel). À compléter : retourner auth_headers
#     quand auth_headers fournit un JWT valide pour un utilisateur ayant active_company_id et
#     has_rh_access_in_company(active_company_id)=True (ou is_super_admin pour DELETE)."""
#     return auth_headers  # ou return {**auth_headers, "X-Active-Company": "<company_uuid>"}
#
# --- Module payroll (tests/unit/payroll/, tests/integration/payroll/) ---
# Le module payroll n'expose pas de routes HTTP propres (api/router.py est un placeholder).
# La logique payroll est consommée via le module payslips (POST /api/actions/generate-payslip,
# GET/POST/DELETE /api/payslips/*). Les tests d'intégration utilisent client, patches au niveau
# router pour éviter les appels DB/Supabase, et acceptent 200/401/422/500 selon l'environnement.
# Fixture optionnelle pour tests E2E avec token réel :
# @pytest.fixture
# def payroll_headers(auth_headers):
#     """En-têtes pour un utilisateur avec accès RH / entreprise active pour les routes paie
#     (génération bulletin, exports). Format : {\"Authorization\": \"Bearer <jwt>\",
#     \"X-Active-Company\": \"<company_id>\"}. À compléter : retourner auth_headers
#     (+ X-Active-Company) quand auth_headers fournit un JWT valide."""
#     return auth_headers  # ou return {**auth_headers, "X-Active-Company": "<company_uuid>"}
#
# --- Module exports (tests/unit/exports/, tests/integration/exports/) ---
# Les tests d'intégration API utilisent dependency_overrides pour get_current_user et
# get_active_company_id (app.modules.exports.api.dependencies) ; le service peut être mocké.
# Fixture à ajouter si besoin de tests E2E avec token réel :
# @pytest.fixture
# def exports_headers(auth_headers):
#     """En-têtes pour les routes /api/exports/* (preview, generate, history, download).
#     Format : {\"Authorization\": \"Bearer <jwt>\", \"X-Active-Company\": \"<company_id>\"}.
#     L'utilisateur doit avoir droits RH sur la company pour utiliser les exports."""
#     return {**auth_headers, "X-Active-Company": "<company_uuid>"}  # à compléter avec company_id de test
#
# --- Module payslips (tests/unit/payslips/, tests/integration/payslips/) ---
# Les tests d'intégration API utilisent :
#   - client : TestClient(app) — déjà défini ci-dessus.
#   - dependency_overrides[get_current_user] : pour les routes protégées (GET /api/me/payslips,
#     GET /api/payslips/{id}, POST .../edit, GET .../history, POST .../restore). Pas de JWT réel.
#   - patch des commands/queries/service (generate_payslip, get_my_payslips, get_payslip_details_for_user, etc.)
#     pour éviter DB et storage réels.
# Fixture optionnelle si besoin de tests E2E avec token réel :
# @pytest.fixture
# def payslips_headers(auth_headers):
#     """En-têtes pour les routes /api/me/payslips, /api/payslips/* (détail, edit, history, restore).
#     L'utilisateur doit avoir un employé associé (user.id = employee_id) pour GET /api/me/payslips,
#     ou droits RH (has_rh_access_in_company) pour détail/edit/history/restore.
#     Format : {\"Authorization\": \"Bearer <jwt>\", \"X-Active-Company\": \"<company_id>\" (optionnel)."""
#     return auth_headers  # ou return {**auth_headers, "X-Active-Company": "<company_uuid>"}
#
# Pour tests repository contre une DB de test réelle (optionnel) :
# @pytest.fixture
# def payslips_db_session(db_session):
#     """Session ou client DB pour les tables payslips, employees (statut), employee_schedules (cumuls).
#     À compléter si db_session fournit un client Supabase de test avec données payslips."""
#     return db_session
#
# --- Module schedules (tests/unit/schedules/, tests/integration/schedules/) ---
# Les tests d'intégration API utilisent client, dependency_overrides pour get_current_user
# et patch des commands/queries (pas de JWT ni DB réels).
# Fixture à ajouter si besoin de tests E2E avec token réel :
# @pytest.fixture
# def schedules_headers(auth_headers):
#     """En-têtes pour les routes /api/employees/{id}/planned-calendar, /actual-hours,
#     /calculate-payroll-events, GET /api/me/current-cumuls, POST /api/schedules/apply-model.
#     Pour /api/me/current-cumuls : utilisateur avec id = employee_id (employé associé).
#     Pour POST /api/schedules/apply-model : utilisateur avec active_company_id et
#     has_rh_access_in_company(active_company_id)=True (admin, rh, collaborateur_rh).
#     Format : {\"Authorization\": \"Bearer <jwt>\", \"X-Active-Company\": \"<company_id>\" (optionnel)."""
#     return auth_headers  # ou return {**auth_headers, "X-Active-Company": "<company_uuid>"}
#
# Pour tests repository contre une DB de test réelle (optionnel) :
# @pytest.fixture
# def schedules_db_session(db_session):
#     """Session ou client DB pour la table employee_schedules (planned_calendar, actual_hours,
#     payroll_events, cumuls). À compléter si db_session fournit un client Supabase de test."""
#     return db_session
#
# --- Module promotions (tests/unit/promotions/, tests/integration/promotions/) ---
# Les tests d'intégration API utilisent client, dependency_overrides pour get_current_user et
# patch de get_promotion_repository / get_promotion_queries (pas de JWT ni DB réels).
# Fixture à ajouter si besoin de tests E2E avec token réel :
# @pytest.fixture
# def promotions_headers(auth_headers):
#     """En-têtes pour les routes /api/promotions/* (list, stats, get, create, update, submit,
#     approve, reject, mark-effective, delete, document). L'utilisateur doit avoir active_company_id
#     renseigné et has_rh_access_in_company(active_company_id)=True (admin, rh, collaborateur_rh).
#     Pour approve/reject : is_admin_in_company(company_id) ou is_super_admin.
#     Format : {\"Authorization\": \"Bearer <jwt>\", \"X-Active-Company\": \"<company_id>\" (optionnel)."""
#     return auth_headers  # ou return {**auth_headers, "X-Active-Company": "<company_uuid>"}
#
# Pour tests repository contre une DB de test réelle (optionnel) :
# @pytest.fixture
# def promotions_db_session(db_session):
#     """Session ou client DB pour les tables promotions, employees, profiles, user_company_accesses.
#     À compléter si db_session fournit un client Supabase de test avec données promotions."""
#     return db_session
#
# --- Module recruitment (tests/unit/recruitment/, tests/integration/recruitment/) ---
# Les tests d'intégration API utilisent client, dependency_overrides pour get_current_user
# (User avec active_company_id et has_rh_access_in_company) et patch des commands/queries
# pour éviter la DB réelle.
# Fixture à ajouter si besoin de tests E2E avec token réel :
# @pytest.fixture
# def recruitment_headers(auth_headers):
#     """En-têtes pour les routes /api/recruitment/* (jobs, candidates, interviews, notes,
#     opinions, timeline, rejection-reasons, settings). L'utilisateur doit avoir
#     active_company_id renseigné et has_rh_access_in_company(active_company_id)=True (admin, rh,
#     collaborateur_rh). Format : {\"Authorization\": \"Bearer <jwt>\", \"X-Active-Company\":
#     \"<company_id>\" (optionnel)."""
#     return auth_headers  # ou return {**auth_headers, "X-Active-Company": "<company_uuid>"}
#
# Pour tests repository contre une DB de test réelle (optionnel) :
# @pytest.fixture
# def recruitment_db_session(db_session):
#     """Session ou client DB pour les tables recruitment_jobs, recruitment_candidates,
#     recruitment_pipeline_stages, recruitment_timeline_events, recruitment_interviews,
#     recruitment_notes, recruitment_opinions, recruitment_interview_participants, employees."""
#     return db_session
#
# --- Module rates (tests/unit/rates/, tests/integration/rates/) ---
# Les tests d'intégration API utilisent client et dependency_overrides pour get_all_rates_reader
# (pas d'auth sur GET /api/rates/all). Pas de fixture rates_headers nécessaire pour l'instant.
# Pour tests repository contre une DB de test réelle (optionnel), voir test_repository.py :
# fixture rates_db_session(db_session) pour la table payroll_config.
#
# --- Module repos_compensateur (tests/unit/repos_compensateur/, tests/integration/repos_compensateur/) ---
# Les tests d'intégration API utilisent client, dependency_overrides pour get_current_user
# (objet avec active_company_id pour POST /api/repos-compensateur/calculer-credits) et patch
# de calculer_credits_repos_command pour éviter la DB réelle.
# Fixture à ajouter si besoin de tests E2E avec token réel :
# @pytest.fixture
# def repos_compensateur_headers(auth_headers):
#     """En-têtes pour POST /api/repos-compensateur/calculer-credits. L'utilisateur doit avoir
#     active_company_id renseigné (ou passer company_id en query). Format : {\"Authorization\":
#     \"Bearer <jwt>\", \"X-Active-Company\": \"<company_id>\" (optionnel)."""
#     return auth_headers  # ou return {**auth_headers, "X-Active-Company": "<company_uuid>"}
#
# --- Module saisies_avances (tests/unit/saisies_avances/, tests/integration/saisies_avances/) ---
# Les tests d'intégration API utilisent client, dependency_overrides pour get_current_user
# (User avec active_company_id et rôle rh/collaborateur) et patch des commands/queries pour éviter la DB.
# Fixture à ajouter si besoin de tests E2E avec token réel :
# @pytest.fixture
# def saisies_avances_headers(auth_headers):
#     """En-têtes pour les routes /api/saisies-avances/* (saisies sur salaire, avances, paiements,
#     deductions, advance-repayments). L'utilisateur doit avoir active_company_id renseigné ;
#     pour les routes RH (création saisie, approbation avance) : rôle admin/rh. Pour /employees/me/*
#     : un employé associé (user.id = employee_id). Format : {\"Authorization\": \"Bearer <jwt>\",
#     \"X-Active-Company\": \"<company_id>\" (optionnel)."""
#     return auth_headers  # ou return {**auth_headers, "X-Active-Company": "<company_uuid>"}
#
# Pour tests repository contre une DB de test réelle (optionnel) : db_session et données dans
# salary_seizures, salary_advances, salary_advance_payments, employees.
#
# --- Module rib_alerts (tests/unit/rib_alerts/, tests/integration/rib_alerts/) ---
# Les tests d'intégration API utilisent client, dependency_overrides pour get_current_user
# (User avec active_company_id) et patch de get_rib_alerts / mark_rib_alert_read / resolve_rib_alert
# au niveau du router pour éviter la DB réelle.
# Fixture à ajouter si besoin de tests E2E avec token réel :
# @pytest.fixture
# def rib_alerts_headers(auth_headers):
#     """En-têtes pour GET /api/rib-alerts, PATCH /api/rib-alerts/{id}/read et /resolve.
#     L'utilisateur doit avoir active_company_id renseigné (obligatoire pour toutes les routes).
#     Format : {\"Authorization\": \"Bearer <jwt>\", \"X-Active-Company\": \"<company_id>\" (optionnel)."""
#     return auth_headers  # ou return {**auth_headers, "X-Active-Company": "<company_uuid>"}
#
# Pour tests repository contre une DB de test réelle (optionnel) :
# @pytest.fixture
# def rib_alerts_db_session(db_session):
#     """Session ou client DB pour la table rib_alerts. À compléter si db_session fournit
#     un client Supabase de test avec données rib_alerts."""
#     return db_session
#
# --- Module scraping (tests/unit/scraping/, tests/integration/scraping/) ---
# Les tests d'intégration API utilisent client, dependency_overrides pour get_current_user
# et verify_super_admin (super admin uniquement) ; patch des commands/queries au niveau
# du router pour éviter DB et exécution réelle des scripts de scraping.
# Fixture à ajouter si besoin de tests E2E avec token réel :
# @pytest.fixture
# def scraping_headers(auth_headers):
#     """En-têtes pour les routes /api/scraping/* (dashboard, sources, execute, jobs,
#     schedules, alerts). L'utilisateur doit être super administrateur (présent dans
#     super_admins avec is_active=True). Format : {\"Authorization\": \"Bearer <jwt>\"}."""
#     return auth_headers
#
# Pour tests repository contre une DB de test réelle (optionnel) :
# @pytest.fixture
# def scraping_db_session(db_session):
#     """Session ou client DB pour les tables scraping_sources, scraping_jobs,
#     scraping_schedules, scraping_alerts et RPC get_scraping_stats."""
#     return db_session
#
# --- Module uploads (tests/unit/uploads/, tests/integration/uploads/) ---
# Les tests d'intégration API utilisent client, dependency_overrides pour get_current_user
# et mocks storage/repository pour éviter DB et bucket réels.
# Fixture à ajouter si besoin de tests E2E avec token réel :
# @pytest.fixture
# def uploads_headers(auth_headers):
#     """En-têtes pour les routes /api/uploads/* (POST /logo, DELETE /logo/{entity_type}/{entity_id},
#     PATCH /logo-scale/{entity_type}/{entity_id}). L'utilisateur doit pouvoir modifier le logo :
#     pour company : admin ou rh de cette company (user_company_accesses) ou super_admin ;
#     pour group : super_admin uniquement. Format : {\"Authorization\": \"Bearer <jwt>\",
#     \"X-Active-Company\": \"<company_id>\" (optionnel)."""
#     return auth_headers  # ou return {**auth_headers, "X-Active-Company": "<company_uuid>"}
#
# Pour tests repository contre une DB de test réelle (optionnel) :
# @pytest.fixture
# def uploads_db_session(db_session):
#     """Session ou client DB pour les tables companies, company_groups (logo_url, logo_scale)
#     et le bucket Supabase 'logos'. À compléter si db_session fournit un client de test."""
#     return db_session
#
# --- Module super_admin (tests/unit/super_admin/, tests/integration/super_admin/) ---
# Les tests d'intégration API utilisent client, dependency_overrides pour get_current_user
# et verify_super_admin (défini dans app.modules.super_admin.api.router) ; patch des
# commands/queries pour éviter la DB réelle.
# Fixture à ajouter si besoin de tests E2E avec token réel :
# @pytest.fixture
# def super_admin_headers(auth_headers):
#     """En-têtes pour les routes /api/super-admin/* (dashboard/stats, companies CRUD,
#     users, system/health, super-admins, reduction-fillon). L'utilisateur doit être
#     présent dans la table super_admins avec is_active=True.
#     Format : {\"Authorization\": \"Bearer <jwt>\"}."""
#     return auth_headers
#
# Pour tests repository contre une DB de test réelle (optionnel) :
# @pytest.fixture
# def super_admin_db_session(db_session):
#     """Session ou client DB pour la table super_admins. À compléter si db_session
#     fournit un client Supabase de test avec données super_admins."""
#     return db_session
