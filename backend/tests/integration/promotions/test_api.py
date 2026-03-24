"""
Tests d'intégration HTTP des routes du module promotions.

Préfixe des routes : /api/promotions.
Utilise : client (TestClient). Pour les tests avec utilisateur authentifié,
dependency_overrides pour get_current_user et patch des repositories/queries
(pas de JWT ni DB réels).

Fixture documentée : promotions_headers.
  Si conftest.py fournit promotions_headers (en-têtes avec token Bearer et
  X-Active-Company pour un utilisateur RH), les tests peuvent l'utiliser
  pour des tests E2E avec token réel. Sinon, les tests utilisent
  dependency_overrides[get_current_user] et des mocks.
"""
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.promotions.schemas import (
    PromotionListItem,
    PromotionRead,
    PromotionStats,
)
from app.modules.users.schemas.responses import User, CompanyAccess


pytestmark = pytest.mark.integration

TEST_COMPANY_ID = "company-promotions-test"
TEST_RH_USER_ID = "user-rh-promotions-test"
TEST_ADMIN_USER_ID = "user-admin-promotions-test"


def _make_rh_user():
    """Utilisateur de test avec droits RH sur TEST_COMPANY_ID et active_company_id renseigné."""
    access = CompanyAccess(
        company_id=TEST_COMPANY_ID,
        company_name="Test Co",
        role="rh",
        is_primary=True,
    )
    return User(
        id=TEST_RH_USER_ID,
        email="rh@test.com",
        first_name="RH",
        last_name="Test",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[access],
        active_company_id=TEST_COMPANY_ID,
    )


def _make_admin_user():
    """Utilisateur admin (pour approve/reject)."""
    access = CompanyAccess(
        company_id=TEST_COMPANY_ID,
        company_name="Test Co",
        role="admin",
        is_primary=True,
    )
    return User(
        id=TEST_ADMIN_USER_ID,
        email="admin@test.com",
        first_name="Admin",
        last_name="Test",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[access],
        active_company_id=TEST_COMPANY_ID,
    )


def _make_collaborator_user():
    """Utilisateur sans droits RH."""
    access = CompanyAccess(
        company_id=TEST_COMPANY_ID,
        company_name="Test Co",
        role="collaborateur",
        is_primary=True,
    )
    return User(
        id="user-collab-test",
        email="collab@test.com",
        first_name="Collab",
        last_name="Test",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[access],
        active_company_id=TEST_COMPANY_ID,
    )


def _promotion_read(**kwargs):
    defaults = {
        "id": "promo-1",
        "company_id": TEST_COMPANY_ID,
        "employee_id": "emp-1",
        "promotion_type": "salaire",
        "status": "draft",
        "effective_date": date(2025, 6, 1),
        "request_date": date(2025, 3, 1),
        "previous_job_title": "Dev",
        "new_salary": {"valeur": 3800, "devise": "EUR"},
        "created_at": datetime(2025, 3, 1, 10, 0),
        "updated_at": datetime(2025, 3, 1, 10, 0),
    }
    defaults.update(kwargs)
    return PromotionRead(**defaults)


def _promotion_list_item(**kwargs):
    defaults = {
        "id": "promo-1",
        "employee_id": "emp-1",
        "first_name": "Jean",
        "last_name": "Dupont",
        "promotion_type": "salaire",
        "new_salary": {"valeur": 3800, "devise": "EUR"},
        "effective_date": date(2025, 6, 1),
        "status": "draft",
        "request_date": date(2025, 3, 1),
        "created_at": datetime(2025, 3, 1, 10, 0),
    }
    defaults.update(kwargs)
    return PromotionListItem(**defaults)


class TestPromotionsUnauthenticated:
    """Sans token : routes protégées renvoient 401."""

    def test_get_list_returns_401_without_auth(self, client: TestClient):
        """GET /api/promotions sans auth → 401."""
        response = client.get("/api/promotions")
        assert response.status_code == 401

    def test_get_stats_returns_401_without_auth(self, client: TestClient):
        """GET /api/promotions/stats sans auth → 401."""
        response = client.get("/api/promotions/stats")
        assert response.status_code == 401

    def test_get_by_id_returns_401_without_auth(self, client: TestClient):
        """GET /api/promotions/{id} sans auth → 401."""
        response = client.get("/api/promotions/promo-1")
        assert response.status_code == 401

    def test_post_create_returns_401_without_auth(self, client: TestClient):
        """POST /api/promotions sans auth → 401."""
        response = client.post(
            "/api/promotions",
            json={
                "employee_id": "emp-1",
                "promotion_type": "salaire",
                "new_salary": {"valeur": 3800, "devise": "EUR"},
                "effective_date": date.today().isoformat(),
                "request_date": date.today().isoformat(),
            },
        )
        assert response.status_code == 401

    def test_put_update_returns_401_without_auth(self, client: TestClient):
        """PUT /api/promotions/{id} sans auth → 401."""
        response = client.put(
            "/api/promotions/promo-1",
            json={"new_job_title": "Lead Dev"},
        )
        assert response.status_code == 401

    def test_post_submit_returns_401_without_auth(self, client: TestClient):
        """POST /api/promotions/{id}/submit sans auth → 401."""
        response = client.post("/api/promotions/promo-1/submit")
        assert response.status_code == 401

    def test_post_approve_returns_401_without_auth(self, client: TestClient):
        """POST /api/promotions/{id}/approve sans auth → 401."""
        response = client.post(
            "/api/promotions/promo-1/approve",
            json={"notes": "OK"},
        )
        assert response.status_code == 401

    def test_post_reject_returns_401_without_auth(self, client: TestClient):
        """POST /api/promotions/{id}/reject sans auth → 401."""
        response = client.post(
            "/api/promotions/promo-1/reject",
            json={"rejection_reason": "Raison de rejet suffisamment longue"},
        )
        assert response.status_code == 401

    def test_post_mark_effective_returns_401_without_auth(self, client: TestClient):
        """POST /api/promotions/{id}/mark-effective sans auth → 401."""
        response = client.post("/api/promotions/promo-1/mark-effective")
        assert response.status_code == 401

    def test_delete_returns_401_without_auth(self, client: TestClient):
        """DELETE /api/promotions/{id} sans auth → 401."""
        response = client.delete("/api/promotions/promo-1")
        assert response.status_code == 401

    def test_get_document_returns_401_without_auth(self, client: TestClient):
        """GET /api/promotions/{id}/document sans auth → 401."""
        response = client.get("/api/promotions/promo-1/document")
        assert response.status_code == 401


class TestPromotionsWithRhUser:
    """Avec utilisateur RH injecté (dependency_overrides) et repository mocké."""

    @pytest.fixture
    def mock_repo(self):
        """Repository mock : list, get_by_id, create, update, delete."""
        repo = MagicMock()
        repo.list.return_value = []
        repo.get_by_id.return_value = None
        repo.create.return_value = "promo-new-id"
        return repo

    @pytest.fixture
    def mock_queries(self):
        """IPromotionQueries mock pour stats et employee_rh_access."""
        q = MagicMock()
        q.get_promotion_stats.return_value = PromotionStats(
            total_promotions=0,
            promotions_by_month={},
            approval_rate=0.0,
            promotions_by_type={},
            average_salary_increase=None,
            promotions_with_rh_access=0,
        )
        q.get_employee_rh_access.return_value = MagicMock(
            has_access=False,
            current_role=None,
            can_grant_access=True,
            available_roles=["collaborateur_rh", "rh"],
        )
        return q

    @pytest.fixture
    def client_with_rh(self, client: TestClient, mock_repo, mock_queries):
        """Client avec get_current_user overridé et repository/queries patchés (au niveau application)."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        with patch(
            "app.modules.promotions.application.queries.get_promotion_repository",
            return_value=mock_repo,
        ), patch(
            "app.modules.promotions.application.commands.get_promotion_repository",
            return_value=mock_repo,
        ), patch(
            "app.modules.promotions.application.queries.get_promotion_queries",
            return_value=mock_queries,
        ):
            yield client
        app.dependency_overrides.pop(get_current_user, None)

    def test_get_list_returns_200_and_list(self, client_with_rh: TestClient):
        """GET /api/promotions en tant que RH → 200 et liste."""
        response = client_with_rh.get("/api/promotions")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_list_accepts_query_params(
        self, client_with_rh: TestClient, mock_repo
    ):
        """GET /api/promotions?year=2025&status=draft transmet les filtres."""
        client_with_rh.get("/api/promotions?year=2025&status=draft")
        mock_repo.list.assert_called_once()
        call_kw = mock_repo.list.call_args[1]
        assert call_kw.get("year") == 2025
        assert call_kw.get("status") == "draft"

    def test_get_stats_returns_200(self, client_with_rh: TestClient, mock_queries):
        """GET /api/promotions/stats → 200."""
        response = client_with_rh.get("/api/promotions/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_promotions" in data
        assert "approval_rate" in data

    def test_get_by_id_returns_404_when_not_found(
        self, client_with_rh: TestClient
    ):
        """GET /api/promotions/{id} quand promotion inexistante → 404."""
        response = client_with_rh.get("/api/promotions/promo-unknown")
        assert response.status_code == 404
        assert "non trouvée" in response.json().get("detail", "").lower()

    def test_get_by_id_returns_200_when_found(
        self, client_with_rh: TestClient, mock_repo
    ):
        """GET /api/promotions/{id} quand promotion trouvée → 200."""
        mock_repo.get_by_id.return_value = _promotion_read()
        response = client_with_rh.get("/api/promotions/promo-1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "promo-1"
        assert data["status"] == "draft"

    def test_post_create_returns_201(
        self, client_with_rh: TestClient, mock_repo
    ):
        """POST /api/promotions avec body valide → 201."""
        with patch(
            "app.modules.promotions.application.commands.get_employee_snapshot_for_promotion",
            return_value={
                "employee": {
                    "job_title": "Dev",
                    "salaire_de_base": {"valeur": 3500},
                    "statut": "Cadre",
                    "classification_conventionnelle": None,
                },
                "previous_rh_access": None,
            },
        ), patch(
            "app.modules.promotions.application.commands.get_promotion_by_id_query",
            return_value=_promotion_read(id="promo-new-id"),
        ):
            from datetime import timedelta
            future_date = (date.today() + timedelta(days=1)).isoformat()
            response = client_with_rh.post(
                "/api/promotions",
                json={
                    "employee_id": "emp-1",
                    "promotion_type": "salaire",
                    "new_salary": {"valeur": 3800, "devise": "EUR"},
                    "effective_date": future_date,
                    "request_date": date.today().isoformat(),
                },
            )
        assert response.status_code == 201
        data = response.json()
        assert data["employee_id"] == "emp-1"
        assert data["promotion_type"] == "salaire"
        mock_repo.create.assert_called_once()

    def test_post_create_without_new_data_returns_422(self, client_with_rh: TestClient):
        """POST /api/promotions sans aucun champ nouveau → 422 (validation)."""
        response = client_with_rh.post(
            "/api/promotions",
            json={
                "employee_id": "emp-1",
                "promotion_type": "salaire",
                "effective_date": date.today().isoformat(),
                "request_date": date.today().isoformat(),
            },
        )
        assert response.status_code == 422

    def test_put_update_returns_404_when_not_found(
        self, client_with_rh: TestClient
    ):
        """PUT /api/promotions/{id} quand promotion inexistante → 404."""
        response = client_with_rh.put(
            "/api/promotions/promo-unknown",
            json={"new_job_title": "Lead Dev"},
        )
        assert response.status_code == 404

    def test_put_update_returns_200_when_draft(
        self, client_with_rh: TestClient, mock_repo
    ):
        """PUT /api/promotions/{id} avec draft → 200."""
        mock_repo.get_by_id.return_value = _promotion_read(status="draft")
        with patch(
            "app.modules.promotions.application.commands.get_promotion_by_id_query",
            return_value=_promotion_read(status="draft", new_job_title="Lead Dev"),
        ):
            response = client_with_rh.put(
                "/api/promotions/promo-1",
                json={"new_job_title": "Lead Dev"},
            )
        assert response.status_code == 200
        mock_repo.update.assert_called_once()

    def test_post_submit_returns_404_when_not_found(
        self, client_with_rh: TestClient
    ):
        """POST .../submit quand promotion inexistante → 404."""
        response = client_with_rh.post("/api/promotions/promo-unknown/submit")
        assert response.status_code == 404

    def test_post_mark_effective_returns_400_when_not_draft_or_effective(
        self, client_with_rh: TestClient, mock_repo
    ):
        """POST .../mark-effective quand statut approved → 400."""
        mock_repo.get_by_id.return_value = _promotion_read()
        with patch(
            "app.modules.promotions.application.commands.get_promotion_by_id_query",
            return_value=_promotion_read(status="approved"),
        ):
            response = client_with_rh.post("/api/promotions/promo-1/mark-effective")
        assert response.status_code == 400

    def test_delete_returns_404_when_not_found(
        self, client_with_rh: TestClient
    ):
        """DELETE /api/promotions/{id} quand promotion inexistante → 404."""
        response = client_with_rh.delete("/api/promotions/promo-unknown")
        assert response.status_code == 404

    def test_delete_returns_204_when_draft(
        self, client_with_rh: TestClient, mock_repo
    ):
        """DELETE /api/promotions/{id} quand draft → 204."""
        mock_repo.get_by_id.return_value = _promotion_read(status="draft")
        response = client_with_rh.delete("/api/promotions/promo-1")
        assert response.status_code == 204
        mock_repo.delete.assert_called_once_with("promo-1", TEST_COMPANY_ID)


class TestPromotionsApproveReject:
    """Approve/Reject : réservés aux admin (can_approve_reject)."""

    @pytest.fixture
    def mock_repo(self):
        repo = MagicMock()
        repo.get_by_id.return_value = _promotion_read(status="pending_approval")
        repo.update.return_value = None
        return repo

    @pytest.fixture
    def client_with_admin(self, client: TestClient, mock_repo):
        """Client avec utilisateur admin pour approve/reject."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_admin_user()
        with patch(
            "app.modules.promotions.application.queries.get_promotion_repository",
            return_value=mock_repo,
        ), patch(
            "app.modules.promotions.application.commands.get_promotion_repository",
            return_value=mock_repo,
        ), patch(
            "app.modules.promotions.application.commands.get_promotion_by_id_query",
            return_value=_promotion_read(status="approved"),
        ):
            yield client
        app.dependency_overrides.pop(get_current_user, None)

    def test_post_approve_as_admin_returns_200(
        self, client_with_admin: TestClient, mock_repo
    ):
        """POST .../approve en tant qu'admin → 200."""
        with patch(
            "app.modules.promotions.application.commands.get_promotion_document_provider"
        ) as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.generate_letter.return_value = b"%PDF"
            mock_provider.save_document.return_value = "https://storage/doc.pdf"
            mock_get_provider.return_value = mock_provider
            response = client_with_admin.post(
                "/api/promotions/promo-1/approve",
                json={"notes": "Approuvé"},
            )
        assert response.status_code == 200
        assert mock_repo.update.called

    def test_post_reject_as_admin_returns_200(
        self, client_with_admin: TestClient, mock_repo
    ):
        """POST .../reject en tant qu'admin → 200."""
        with patch(
            "app.modules.promotions.application.commands.get_promotion_by_id_query",
            return_value=_promotion_read(status="rejected"),
        ):
            response = client_with_admin.post(
                "/api/promotions/promo-1/reject",
                json={"rejection_reason": "Raison de rejet suffisamment longue"},
            )
        assert response.status_code == 200
        mock_repo.update.assert_called_once()

    @pytest.fixture
    def client_with_rh_only(self, client: TestClient, mock_repo):
        """Client avec utilisateur RH (non admin) pour tester 403 sur approve/reject."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        with patch(
            "app.modules.promotions.application.commands.get_promotion_repository",
            return_value=mock_repo,
        ), patch(
            "app.modules.promotions.application.queries.get_promotion_repository",
            return_value=mock_repo,
        ):
            yield client
        app.dependency_overrides.pop(get_current_user, None)

    def test_post_approve_as_rh_returns_403(
        self, client_with_rh_only: TestClient
    ):
        """POST .../approve en tant que RH (non admin) → 403."""
        response = client_with_rh_only.post(
            "/api/promotions/promo-1/approve",
            json={"notes": "Approuvé"},
        )
        assert response.status_code == 403
        assert "administrateurs" in response.json().get("detail", "").lower()


class TestPromotionsForbiddenNonRh:
    """Utilisateur authentifié sans droits RH : 403 sur les routes RH."""

    @pytest.fixture
    def mock_repo(self):
        repo = MagicMock()
        repo.list.return_value = []
        repo.get_by_id.return_value = None
        return repo

    @pytest.fixture
    def client_with_collaborator(self, client: TestClient, mock_repo):
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_collaborator_user()
        with patch(
            "app.modules.promotions.application.queries.get_promotion_repository",
            return_value=mock_repo,
        ), patch(
            "app.modules.promotions.application.commands.get_promotion_repository",
            return_value=mock_repo,
        ):
            yield client
        app.dependency_overrides.pop(get_current_user, None)

    def test_get_list_returns_403_for_collaborator(
        self, client_with_collaborator: TestClient
    ):
        """GET /api/promotions en tant que collaborateur → 403."""
        response = client_with_collaborator.get("/api/promotions")
        assert response.status_code == 403
        assert "Accès réservé" in response.json().get("detail", "") or "RH" in response.json().get("detail", "")

    def test_post_create_returns_403_for_collaborator(
        self, client_with_collaborator: TestClient
    ):
        """POST /api/promotions en tant que collaborateur → 403."""
        response = client_with_collaborator.post(
            "/api/promotions",
            json={
                "employee_id": "emp-1",
                "promotion_type": "salaire",
                "new_salary": {"valeur": 3800, "devise": "EUR"},
                "effective_date": date.today().isoformat(),
                "request_date": date.today().isoformat(),
            },
        )
        assert response.status_code == 403


class TestPromotionsNoActiveCompany:
    """Utilisateur sans active_company_id : 400 sur les routes qui en ont besoin."""

    @pytest.fixture
    def user_no_company(self):
        access = CompanyAccess(
            company_id=TEST_COMPANY_ID,
            company_name="Test Co",
            role="rh",
            is_primary=True,
        )
        user = User(
            id=TEST_RH_USER_ID,
            email="rh@test.com",
            first_name="RH",
            last_name="Test",
            is_super_admin=False,
            is_group_admin=False,
            accessible_companies=[access],
            active_company_id=None,
        )
        return user

    @pytest.fixture
    def client_no_company(self, client: TestClient, user_no_company):
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: user_no_company
        with patch(
            "app.modules.promotions.application.queries.get_promotion_repository",
            return_value=MagicMock(),
        ):
            yield client
        app.dependency_overrides.pop(get_current_user, None)

    def test_get_list_returns_400_or_403_when_no_active_company(
        self, client_no_company: TestClient
    ):
        """GET /api/promotions sans active_company_id → 400 ou 403 (require_rh lève 403 si pas d'entreprise active)."""
        response = client_no_company.get("/api/promotions")
        assert response.status_code in (400, 403)
        detail = response.json().get("detail", "").lower()
        assert "entreprise" in detail or "active" in detail or "réservé" in detail or "rh" in detail
