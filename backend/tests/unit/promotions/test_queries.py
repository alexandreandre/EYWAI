"""
Tests unitaires des queries promotions (application/queries.py).

Repositories et providers mockés ; pas de DB ni HTTP.
"""
from datetime import date, datetime
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.modules.promotions.application import queries
from app.modules.promotions.schemas import (
    EmployeeRhAccess,
    PromotionListItem,
    PromotionRead,
    PromotionStats,
)


COMPANY_ID = "company-promo-test"


def _promotion_list_item():
    return PromotionListItem(
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


def _promotion_read():
    return PromotionRead(
        id="promo-1",
        company_id=COMPANY_ID,
        employee_id="emp-1",
        promotion_type="salaire",
        status="draft",
        effective_date=date(2025, 6, 1),
        request_date=date(2025, 3, 1),
        previous_job_title="Dev",
        new_salary={"valeur": 3800, "devise": "EUR"},
        created_at=datetime(2025, 3, 1, 10, 0),
        updated_at=datetime(2025, 3, 1, 10, 0),
    )


class TestListPromotionsQuery:
    """list_promotions_query."""

    @patch("app.modules.promotions.application.queries.get_promotion_repository")
    def test_returns_list_from_repository(self, mock_get_repo):
        """Délègue au repository et retourne la liste."""
        mock_repo = MagicMock()
        mock_repo.list.return_value = [_promotion_list_item()]
        mock_get_repo.return_value = mock_repo

        result = queries.list_promotions_query(
            company_id=COMPANY_ID,
            year=2025,
            status="draft",
            limit=10,
        )

        assert len(result) == 1
        assert result[0].id == "promo-1"
        assert result[0].first_name == "Jean"
        mock_repo.list.assert_called_once_with(
            company_id=COMPANY_ID,
            year=2025,
            status="draft",
            promotion_type=None,
            employee_id=None,
            search=None,
            limit=10,
            offset=None,
        )

    @patch("app.modules.promotions.application.queries.get_promotion_repository")
    def test_empty_list_when_no_promotions(self, mock_get_repo):
        """Liste vide quand le repository ne retourne rien."""
        mock_repo = MagicMock()
        mock_repo.list.return_value = []
        mock_get_repo.return_value = mock_repo

        result = queries.list_promotions_query(company_id=COMPANY_ID)

        assert result == []


class TestGetPromotionByIdQuery:
    """get_promotion_by_id_query."""

    @patch("app.modules.promotions.application.queries.get_promotion_repository")
    def test_raises_404_when_not_found(self, mock_get_repo):
        """Promotion inexistante → 404."""
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = None
        mock_get_repo.return_value = mock_repo

        with pytest.raises(HTTPException) as exc_info:
            queries.get_promotion_by_id_query("promo-unknown", COMPANY_ID)

        assert exc_info.value.status_code == 404
        assert "non trouvée" in exc_info.value.detail.lower()

    @patch("app.modules.promotions.application.queries.get_promotion_repository")
    def test_returns_promotion_read_when_found(self, mock_get_repo):
        """Promotion trouvée → PromotionRead."""
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = _promotion_read()
        mock_get_repo.return_value = mock_repo

        result = queries.get_promotion_by_id_query("promo-1", COMPANY_ID)

        assert result.id == "promo-1"
        assert result.status == "draft"
        assert result.promotion_type == "salaire"
        mock_repo.get_by_id.assert_called_once_with("promo-1", COMPANY_ID)


class TestGetPromotionStatsQuery:
    """get_promotion_stats_query."""

    @patch("app.modules.promotions.application.queries.get_promotion_queries")
    def test_returns_stats_from_queries(self, mock_get_queries):
        """Délègue à IPromotionQueries.get_promotion_stats."""
        mock_queries = MagicMock()
        mock_queries.get_promotion_stats.return_value = PromotionStats(
            total_promotions=5,
            promotions_by_month={"2025-03": 2, "2025-04": 3},
            approval_rate=80.0,
            promotions_by_type={"salaire": 3, "poste": 2},
            average_salary_increase=5.5,
            promotions_with_rh_access=1,
        )
        mock_get_queries.return_value = mock_queries

        result = queries.get_promotion_stats_query(
            company_id=COMPANY_ID,
            year=2025,
        )

        assert result.total_promotions == 5
        assert result.approval_rate == 80.0
        assert result.promotions_by_type["salaire"] == 3
        mock_queries.get_promotion_stats.assert_called_once_with(
            company_id=COMPANY_ID,
            year=2025,
        )


class TestGetEmployeeRhAccessQuery:
    """get_employee_rh_access_query."""

    @patch("app.modules.promotions.application.queries.get_promotion_queries")
    def test_returns_employee_rh_access(self, mock_get_queries):
        """Délègue à IPromotionQueries.get_employee_rh_access."""
        mock_queries = MagicMock()
        mock_queries.get_employee_rh_access.return_value = EmployeeRhAccess(
            has_access=True,
            current_role="collaborateur_rh",
            can_grant_access=True,
            available_roles=["rh", "admin"],
        )
        mock_get_queries.return_value = mock_queries

        result = queries.get_employee_rh_access_query(
            employee_id="emp-1",
            company_id=COMPANY_ID,
        )

        assert result.has_access is True
        assert result.current_role == "collaborateur_rh"
        assert "rh" in result.available_roles
        assert "admin" in result.available_roles
        mock_queries.get_employee_rh_access.assert_called_once_with(
            employee_id="emp-1",
            company_id=COMPANY_ID,
        )


class TestGetPromotionDocumentStreamQuery:
    """get_promotion_document_stream_query."""

    @patch("app.modules.promotions.infrastructure.providers.get_promotion_document_provider")
    def test_returns_stream_from_provider(self, mock_get_provider):
        """Délègue au provider et retourne le stream PDF."""
        mock_provider = MagicMock()
        mock_provider.get_pdf_stream.return_value = BytesIO(b"%PDF-1.4 fake content")
        mock_get_provider.return_value = mock_provider

        result = queries.get_promotion_document_stream_query(
            promotion_id="promo-1",
            company_id=COMPANY_ID,
        )

        assert result is not None
        assert result.read() == b"%PDF-1.4 fake content"
        mock_provider.get_pdf_stream.assert_called_once_with(
            promotion_id="promo-1",
            company_id=COMPANY_ID,
        )
