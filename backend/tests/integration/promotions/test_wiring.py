"""
Tests de câblage (wiring) du module promotions.

Vérifient que l'injection des dépendances et le flux de bout en bout
(router → application → repository / queries / provider) fonctionnent.
"""
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.promotions.schemas import PromotionRead, PromotionStats
from app.modules.users.schemas.responses import User, CompanyAccess


pytestmark = pytest.mark.integration

TEST_COMPANY_ID = "company-promo-wiring"
TEST_USER_ID = "user-rh-promo-wiring"


def _rh_user():
    """Utilisateur RH avec active_company_id."""
    return User(
        id=TEST_USER_ID,
        email="rh@test.com",
        first_name="RH",
        last_name="Wiring",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=TEST_COMPANY_ID,
                company_name="Wiring Co",
                role="rh",
                is_primary=True,
            ),
        ],
        active_company_id=TEST_COMPANY_ID,
    )


class TestPromotionsWiring:
    """Flux complet : route → commandes/queries → repository."""

    def test_list_flow_uses_repository(self, client: TestClient):
        """GET /api/promotions : le router appelle list_promotions_query qui utilise le repo."""
        from app.core.security import get_current_user

        from app.modules.promotions.schemas import PromotionListItem

        mock_repo = MagicMock()
        mock_repo.list.return_value = [
            PromotionListItem(
                id="promo-1",
                employee_id="emp-1",
                first_name="Jean",
                last_name="Dupont",
                promotion_type="salaire",
                new_job_title=None,
                new_salary={"valeur": 3800, "devise": "EUR"},
                new_statut=None,
                effective_date=date(2025, 6, 1),
                status="draft",
                request_date=date(2025, 3, 1),
                requested_by_name="RH User",
                approved_by_name=None,
                grant_rh_access=False,
                new_rh_access=None,
                performance_review_id=None,
                created_at=datetime(2025, 3, 1, 10, 0),
            )
        ]

        app.dependency_overrides[get_current_user] = lambda: _rh_user()
        with patch(
            "app.modules.promotions.application.queries.get_promotion_repository",
            return_value=mock_repo,
        ), patch(
            "app.modules.promotions.application.commands.get_promotion_repository",
            return_value=mock_repo,
        ):
            response = client.get("/api/promotions")

        app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == "promo-1"
        mock_repo.list.assert_called_once()
        call_kw = mock_repo.list.call_args[1]
        assert call_kw["company_id"] == TEST_COMPANY_ID

    def test_stats_flow_uses_queries(self, client: TestClient):
        """GET /api/promotions/stats : get_promotion_stats_query → IPromotionQueries."""
        from app.core.security import get_current_user

        mock_queries = MagicMock()
        mock_queries.get_promotion_stats.return_value = PromotionStats(
            total_promotions=3,
            promotions_by_month={"2025-03": 2, "2025-04": 1},
            approval_rate=66.67,
            promotions_by_type={"salaire": 2, "poste": 1},
            average_salary_increase=5.0,
            promotions_with_rh_access=0,
        )

        app.dependency_overrides[get_current_user] = lambda: _rh_user()
        with patch(
            "app.modules.promotions.application.queries.get_promotion_queries",
            return_value=mock_queries,
        ):
            response = client.get("/api/promotions/stats")

        app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        data = response.json()
        assert data["total_promotions"] == 3
        assert data["approval_rate"] == 66.67
        mock_queries.get_promotion_stats.assert_called_once_with(
            company_id=TEST_COMPANY_ID,
            year=None,
        )

    def test_get_by_id_flow_uses_repository(self, client: TestClient):
        """GET /api/promotions/{id} : get_promotion_by_id_query → repo.get_by_id."""
        from app.core.security import get_current_user

        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = PromotionRead(
            id="promo-1",
            company_id=TEST_COMPANY_ID,
            employee_id="emp-1",
            promotion_type="salaire",
            status="draft",
            effective_date=date(2025, 6, 1),
            request_date=date(2025, 3, 1),
            created_at=datetime(2025, 3, 1, 10, 0),
            updated_at=datetime(2025, 3, 1, 10, 0),
        )

        app.dependency_overrides[get_current_user] = lambda: _rh_user()
        with patch(
            "app.modules.promotions.application.queries.get_promotion_repository",
            return_value=mock_repo,
        ), patch(
            "app.modules.promotions.application.commands.get_promotion_repository",
            return_value=mock_repo,
        ):
            response = client.get("/api/promotions/promo-1")

        app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        assert response.json()["id"] == "promo-1"
        mock_repo.get_by_id.assert_called_once_with("promo-1", TEST_COMPANY_ID)

    def test_create_flow_uses_repository_and_snapshot(self, client: TestClient):
        """POST /api/promotions : create_promotion_cmd → snapshot + repo.create + get_by_id."""
        from app.core.security import get_current_user

        mock_repo = MagicMock()
        mock_repo.create.return_value = "promo-new-id"

        app.dependency_overrides[get_current_user] = lambda: _rh_user()
        with patch(
            "app.modules.promotions.application.queries.get_promotion_repository",
            return_value=mock_repo,
        ), patch(
            "app.modules.promotions.application.commands.get_promotion_repository",
            return_value=mock_repo,
        ), patch(
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
            return_value=PromotionRead(
                id="promo-new-id",
                company_id=TEST_COMPANY_ID,
                employee_id="emp-1",
                promotion_type="salaire",
                status="draft",
                effective_date=date(2025, 6, 1),
                request_date=date.today(),
                created_at=datetime(2025, 3, 1, 10, 0),
                updated_at=datetime(2025, 3, 1, 10, 0),
            ),
        ):
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

        app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 201
        body = response.json()
        assert body["id"] == "promo-new-id"
        mock_repo.create.assert_called_once()
        call_data = mock_repo.create.call_args[0][0]
        assert call_data["employee_id"] == "emp-1"
        assert call_data["company_id"] == TEST_COMPANY_ID
