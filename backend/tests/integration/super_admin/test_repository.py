"""
Tests d'intégration du repository super_admin (table super_admins).

Sans DB de test : mocks get_supabase_client pour valider la logique et les appels.
Avec DB de test : prévoir la fixture db_session (conftest) et des lignes dans super_admins
pour des tests CRUD réels (get_by_user_id, list_all).

Fixture optionnelle : super_admin_db_session(db_session) si db_session fournit un client
Supabase de test avec table super_admins.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.super_admin.infrastructure.repository import get_by_user_id, list_all
from app.modules.super_admin.domain.entities import SuperAdmin

pytestmark = pytest.mark.integration

TEST_USER_ID = "660e8400-e29b-41d4-a716-446655440001"
TEST_SA_ID = "770e8400-e29b-41d4-a716-446655440002"


class TestGetByUserId:
    """get_by_user_id(user_id) -> Optional[SuperAdmin]."""

    def test_returns_none_when_no_row(self):
        """Retourne None si aucun super admin actif pour ce user_id."""
        with patch(
            "app.modules.super_admin.infrastructure.repository.get_supabase_client",
        ) as m_get_client:
            chain = MagicMock()
            first_eq = chain.eq.return_value
            first_eq.eq.return_value.execute.return_value = MagicMock(data=[])
            m_get_client.return_value.table.return_value.select.return_value = chain

            result = get_by_user_id(TEST_USER_ID)

        assert result is None
        m_get_client.return_value.table.assert_called_once_with("super_admins")
        chain.eq.assert_called_once_with("user_id", TEST_USER_ID)
        first_eq.eq.assert_called_once_with("is_active", True)

    def test_returns_entity_when_one_active_row(self):
        """Retourne une entité SuperAdmin quand une ligne is_active=True existe."""
        row = {
            "id": TEST_SA_ID,
            "user_id": TEST_USER_ID,
            "email": "super@test.com",
            "first_name": "Super",
            "last_name": "Admin",
            "can_create_companies": True,
            "can_delete_companies": False,
            "can_view_all_data": True,
            "can_impersonate": False,
            "is_active": True,
            "created_at": None,
            "last_login_at": None,
            "notes": None,
        }
        with patch(
            "app.modules.super_admin.infrastructure.repository.get_supabase_client",
        ) as m_get_client:
            chain = MagicMock()
            chain.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[row],
            )
            m_get_client.return_value.table.return_value.select.return_value = chain

            result = get_by_user_id(TEST_USER_ID)

        assert result is not None
        assert isinstance(result, SuperAdmin)
        assert str(result.user_id) == TEST_USER_ID
        assert result.email == "super@test.com"
        assert result.can_create_companies is True
        assert result.can_delete_companies is False

    def test_accepts_uuid_or_str(self):
        """Accepte user_id en UUID ou str."""
        from uuid import UUID

        uid_str = TEST_USER_ID
        uid_uuid = UUID(uid_str)
        with patch(
            "app.modules.super_admin.infrastructure.repository.get_supabase_client",
        ) as m_get_client:
            chain = MagicMock()
            chain.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[]
            )
            m_get_client.return_value.table.return_value.select.return_value = chain

            get_by_user_id(uid_str)
            get_by_user_id(uid_uuid)

        # Les deux appels doivent utiliser la même chaîne .eq("user_id", ...)
        assert chain.eq.call_count >= 2


class TestListAll:
    """list_all() -> List[SuperAdmin]."""

    def test_returns_empty_list_when_no_rows(self):
        """Retourne [] si aucune ligne."""
        with patch(
            "app.modules.super_admin.infrastructure.repository.get_supabase_client",
        ) as m_get_client:
            chain = MagicMock()
            chain.order.return_value.execute.return_value = MagicMock(data=None)
            m_get_client.return_value.table.return_value.select.return_value = chain

            result = list_all()

        assert result == []
        m_get_client.return_value.table.assert_called_once_with("super_admins")
        chain.order.assert_called_once_with("created_at", desc=True)

    def test_returns_list_of_entities(self):
        """Retourne une liste d'entités SuperAdmin."""
        rows = [
            {
                "id": TEST_SA_ID,
                "user_id": TEST_USER_ID,
                "email": "sa1@test.com",
                "first_name": "A",
                "last_name": "B",
                "can_create_companies": True,
                "can_delete_companies": True,
                "can_view_all_data": True,
                "can_impersonate": False,
                "is_active": True,
                "created_at": None,
                "last_login_at": None,
                "notes": None,
            },
        ]
        with patch(
            "app.modules.super_admin.infrastructure.repository.get_supabase_client",
        ) as m_get_client:
            chain = MagicMock()
            chain.order.return_value.execute.return_value = MagicMock(data=rows)
            m_get_client.return_value.table.return_value.select.return_value = chain

            result = list_all()

        assert len(result) == 1
        assert isinstance(result[0], SuperAdmin)
        assert result[0].email == "sa1@test.com"
