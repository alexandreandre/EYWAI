"""
Tests d'intégration du repository promotions (PromotionRepository).

Vérifie que le repository délègue correctement aux appels Supabase et retourne
les données attendues. Les appels DB sont mockés (pas de DB réelle).
Pour des tests contre une DB de test, prévoir db_session et données dans
promotions, employees, profiles ; documenter la fixture promotions_db_session
dans conftest.py.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.modules.promotions.infrastructure.repository import PromotionRepository
from app.modules.promotions.schemas import PromotionListItem, PromotionRead


pytestmark = pytest.mark.integration


@pytest.fixture
def repo():
    """Instance du repository à tester."""
    return PromotionRepository()


def _make_chain():
    """Chaîne MagicMock pour supabase.table().select().eq()... (retourne self pour chaînage)."""
    chain = MagicMock()
    chain.eq.return_value = chain
    chain.gte.return_value = chain
    chain.lte.return_value = chain
    chain.single.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.offset.return_value = chain
    return chain


class TestPromotionRepositoryGetById:
    """get_by_id."""

    def test_returns_none_when_no_row(self, repo: PromotionRepository):
        """Aucune ligne → None."""
        with patch(
            "app.modules.promotions.infrastructure.repository.supabase"
        ) as mock_sb:
            chain = _make_chain()
            chain.execute.return_value = MagicMock(data=None)
            mock_sb.table.return_value.select.return_value = chain

            result = repo.get_by_id("promo-unknown", "co-1")

            assert result is None

    def test_returns_promotion_read_when_found(self, repo: PromotionRepository):
        """Ligne trouvée → PromotionRead."""
        row = {
            "id": "promo-1",
            "company_id": "co-1",
            "employee_id": "emp-1",
            "promotion_type": "salaire",
            "status": "draft",
            "effective_date": "2025-06-01",
            "request_date": "2025-03-01",
            "previous_job_title": "Dev",
            "new_salary": {"valeur": 3800, "devise": "EUR"},
            "created_at": "2025-03-01T10:00:00",
            "updated_at": "2025-03-01T10:00:00",
        }
        with patch(
            "app.modules.promotions.infrastructure.repository.supabase"
        ) as mock_sb:
            chain = _make_chain()
            chain.execute.return_value = MagicMock(data=row)
            mock_sb.table.return_value.select.return_value = chain

            result = repo.get_by_id("promo-1", "co-1")

            assert result is not None
            assert isinstance(result, PromotionRead)
            assert result.id == "promo-1"
            assert result.status == "draft"
            assert result.promotion_type == "salaire"


class TestPromotionRepositoryList:
    """list."""

    def test_calls_supabase_with_company_id(self, repo: PromotionRepository):
        """Liste avec company_id → appel select + eq company_id."""
        with patch(
            "app.modules.promotions.infrastructure.repository.supabase"
        ) as mock_sb:
            chain = _make_chain()
            chain.execute.return_value = MagicMock(data=[])
            mock_sb.table.return_value.select.return_value = chain

            repo.list("co-1")

            mock_sb.table.assert_called_with("promotions")
            chain.eq.assert_called_with("company_id", "co-1")

    def test_returns_list_items_with_employee_joins(self, repo: PromotionRepository):
        """Liste avec jointures employés → PromotionListItem."""
        raw_rows = [
            {
                "id": "promo-1",
                "employee_id": "emp-1",
                "promotion_type": "salaire",
                "new_salary": {"valeur": 3800},
                "effective_date": "2025-06-01",
                "status": "draft",
                "request_date": "2025-03-01",
                "created_at": "2025-03-01T10:00:00",
                "employees": {"first_name": "Jean", "last_name": "Dupont"},
                "requested_by_profile": {"first_name": "RH", "last_name": "User"},
                "approved_by_profile": None,
            },
        ]
        with patch(
            "app.modules.promotions.infrastructure.repository.supabase"
        ) as mock_sb:
            chain = _make_chain()
            chain.execute.return_value = MagicMock(data=raw_rows)
            mock_sb.table.return_value.select.return_value = chain

            result = repo.list("co-1")

            assert len(result) == 1
            assert isinstance(result[0], PromotionListItem)
            assert result[0].id == "promo-1"
            assert result[0].first_name == "Jean"
            assert result[0].last_name == "Dupont"


class TestPromotionRepositoryCreate:
    """create."""

    def test_inserts_and_returns_id(self, repo: PromotionRepository):
        """Insert → retourne l'id créé."""
        data = {
            "company_id": "co-1",
            "employee_id": "emp-1",
            "promotion_type": "salaire",
            "status": "draft",
            "effective_date": "2025-06-01",
            "request_date": "2025-03-01",
        }
        with patch(
            "app.modules.promotions.infrastructure.repository.supabase"
        ) as mock_sb:
            mock_sb.table.return_value.insert.return_value.execute.return_value.data = [
                {**data, "id": "promo-new"}
            ]

            result = repo.create(data, "co-1", "user-1")

            assert result == "promo-new"
            mock_sb.table.return_value.insert.assert_called_once_with(data)


class TestPromotionRepositoryUpdate:
    """update."""

    def test_updates_by_id_and_company(self, repo: PromotionRepository):
        """Update avec promotion_id et company_id."""
        with patch(
            "app.modules.promotions.infrastructure.repository.supabase"
        ) as mock_sb:
            chain = MagicMock()
            chain.eq.return_value = chain
            chain.execute.return_value = MagicMock(data=[{"id": "promo-1"}])
            mock_sb.table.return_value.update.return_value = chain

            repo.update("promo-1", "co-1", {"status": "pending_approval"})

            mock_sb.table.return_value.update.assert_called_once_with(
                {"status": "pending_approval"}
            )
            assert chain.eq.call_count >= 2


class TestPromotionRepositoryDelete:
    """delete."""

    def test_deletes_by_id_and_company(self, repo: PromotionRepository):
        """Delete avec promotion_id et company_id."""
        with patch(
            "app.modules.promotions.infrastructure.repository.supabase"
        ) as mock_sb:
            chain = MagicMock()
            chain.eq.return_value = chain
            chain.execute.return_value = MagicMock(data=[{"id": "promo-1"}])
            mock_sb.table.return_value.delete.return_value = chain

            repo.delete("promo-1", "co-1")

            mock_sb.table.return_value.delete.assert_called_once()
            assert chain.eq.call_count >= 2
