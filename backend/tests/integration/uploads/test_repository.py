"""
Tests d'intégration du repository uploads (LogoRepository).

Sans DB de test : mocks Supabase pour valider la logique et les appels.
Avec DB de test : prévoir la fixture db_session (conftest) et des données
dans companies / company_groups pour des tests CRUD réels.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.modules.uploads.infrastructure.repository import (
    LogoRepository,
    entity_exists,
    get_logo_url,
    update_logo_scale,
    update_logo_url,
)


pytestmark = pytest.mark.integration

COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"
GROUP_ID = "660e8400-e29b-41d4-a716-446655440001"


class TestLogoRepositoryEntityExists:
    """entity_exists(entity_type, entity_id)."""

    def test_company_exists_returns_true(self):
        with patch(
            "app.modules.uploads.infrastructure.repository.supabase"
        ) as mock_sb:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value.execute.return_value = MagicMock(
                data=[{"id": COMPANY_ID}]
            )
            table.select.return_value = chain
            mock_sb.table.return_value = table

            repo = LogoRepository()
            result = repo.entity_exists("company", COMPANY_ID)

            mock_sb.table.assert_called_once_with("companies")
            table.select.assert_called_once_with("id")
            chain.eq.assert_called_once_with("id", COMPANY_ID)
            assert result is True

    def test_company_not_exists_returns_false(self):
        with patch(
            "app.modules.uploads.infrastructure.repository.supabase"
        ) as mock_sb:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value.execute.return_value = MagicMock(data=[])
            table.select.return_value = chain
            mock_sb.table.return_value = table

            repo = LogoRepository()
            result = repo.entity_exists("company", COMPANY_ID)

            assert result is False

    def test_group_uses_company_groups_table(self):
        with patch(
            "app.modules.uploads.infrastructure.repository.supabase"
        ) as mock_sb:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value.execute.return_value = MagicMock(
                data=[{"id": GROUP_ID}]
            )
            table.select.return_value = chain
            mock_sb.table.return_value = table

            repo = LogoRepository()
            repo.entity_exists("group", GROUP_ID)

            mock_sb.table.assert_called_once_with("company_groups")


class TestLogoRepositoryGetLogoUrl:
    """get_logo_url(entity_type, entity_id)."""

    def test_returns_url_when_present(self):
        with patch(
            "app.modules.uploads.infrastructure.repository.supabase"
        ) as mock_sb:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value.execute.return_value = MagicMock(
                data=[{"logo_url": "https://storage/logo.png"}]
            )
            table.select.return_value = chain
            mock_sb.table.return_value = table

            repo = LogoRepository()
            result = repo.get_logo_url("company", COMPANY_ID)

            table.select.assert_called_once_with("logo_url")
            assert result == "https://storage/logo.png"

    def test_returns_none_when_no_row(self):
        with patch(
            "app.modules.uploads.infrastructure.repository.supabase"
        ) as mock_sb:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value.execute.return_value = MagicMock(data=[])
            table.select.return_value = chain
            mock_sb.table.return_value = table

            repo = LogoRepository()
            result = repo.get_logo_url("company", COMPANY_ID)

            assert result is None

    def test_returns_none_when_logo_url_null(self):
        with patch(
            "app.modules.uploads.infrastructure.repository.supabase"
        ) as mock_sb:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value.execute.return_value = MagicMock(
                data=[{"logo_url": None}]
            )
            table.select.return_value = chain
            mock_sb.table.return_value = table
            repo = LogoRepository()
            result = repo.get_logo_url("company", COMPANY_ID)
            assert result is None


class TestLogoRepositoryUpdateLogoUrl:
    """update_logo_url(entity_type, entity_id, logo_url)."""

    def test_update_returns_true_when_row_updated(self):
        with patch(
            "app.modules.uploads.infrastructure.repository.supabase"
        ) as mock_sb:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value.execute.return_value = MagicMock(
                data=[{"id": COMPANY_ID}]
            )
            table.update.return_value = chain
            mock_sb.table.return_value = table

            repo = LogoRepository()
            result = repo.update_logo_url(
                "company", COMPANY_ID, "https://new/logo.png"
            )

            table.update.assert_called_once_with({"logo_url": "https://new/logo.png"})
            chain.eq.assert_called_once_with("id", COMPANY_ID)
            assert result is True

    def test_update_none_clears_logo(self):
        with patch(
            "app.modules.uploads.infrastructure.repository.supabase"
        ) as mock_sb:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value.execute.return_value = MagicMock(
                data=[{"id": COMPANY_ID}]
            )
            table.update.return_value = chain
            mock_sb.table.return_value = table

            repo = LogoRepository()
            repo.update_logo_url("company", COMPANY_ID, None)

            table.update.assert_called_once_with({"logo_url": None})


class TestLogoRepositoryUpdateLogoScale:
    """update_logo_scale(entity_type, entity_id, scale)."""

    def test_update_scale_returns_true_when_row_updated(self):
        with patch(
            "app.modules.uploads.infrastructure.repository.supabase"
        ) as mock_sb:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value.execute.return_value = MagicMock(
                data=[{"id": COMPANY_ID}]
            )
            table.update.return_value = chain
            mock_sb.table.return_value = table

            repo = LogoRepository()
            result = repo.update_logo_scale("company", COMPANY_ID, 1.25)

            table.update.assert_called_once_with({"logo_scale": 1.25})
            assert result is True


class TestRepositoryModuleFunctions:
    """Fonctions module (entity_exists, get_logo_url, update_logo_url, update_logo_scale)."""

    def test_entity_exists_delegates_to_default_repository(self):
        with patch(
            "app.modules.uploads.infrastructure.repository._default_repository"
        ) as mock_repo:
            mock_repo.entity_exists.return_value = True
            assert entity_exists("company", COMPANY_ID) is True
            mock_repo.entity_exists.assert_called_once_with(
                "company", COMPANY_ID
            )

    def test_get_logo_url_delegates(self):
        with patch(
            "app.modules.uploads.infrastructure.repository._default_repository"
        ) as mock_repo:
            mock_repo.get_logo_url.return_value = "https://logo.png"
            assert get_logo_url("company", COMPANY_ID) == "https://logo.png"

    def test_update_logo_url_delegates(self):
        with patch(
            "app.modules.uploads.infrastructure.repository._default_repository"
        ) as mock_repo:
            mock_repo.update_logo_url.return_value = True
            assert (
                update_logo_url("company", COMPANY_ID, "https://x.png")
                is True
            )

    def test_update_logo_scale_delegates(self):
        with patch(
            "app.modules.uploads.infrastructure.repository._default_repository"
        ) as mock_repo:
            mock_repo.update_logo_scale.return_value = True
            assert update_logo_scale("company", COMPANY_ID, 1.0) is True
