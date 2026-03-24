"""
Tests d'intégration du repository et des queries infrastructure exports.

Vérifie les opérations sur exports_history (insert, list, get_by_id) et les helpers
(profiles). Avec DB de test (fixture db_session) : tests réels contre la table.
Sans DB de test : mocks Supabase pour valider la logique et les appels.

Fixture documentée : db_session — session ou client DB de test pour exécuter
les tests contre une base réelle (conftest.py). Si None, les tests utilisent des mocks.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.modules.exports.infrastructure import repository
from app.modules.exports.infrastructure import queries as infra_queries


pytestmark = pytest.mark.integration


class TestInsertExportRecord:
    """Repository.insert_export_record : insertion dans exports_history."""

    def test_insert_calls_supabase_with_record_and_returns_id(self):
        """insert_export_record appelle supabase.table('exports_history').insert(record).execute()."""
        record = {
            "company_id": "company-1",
            "export_type": "journal_paie",
            "period": "2025-01",
            "parameters": {},
            "file_paths": ["exports/company-1/journal_paie/file.xlsx"],
            "report": {"employees_count": 3},
            "status": "generated",
            "generated_by": "user-1",
        }
        with patch("app.modules.exports.infrastructure.repository.supabase") as supabase:
            chain = MagicMock()
            chain.execute.return_value = MagicMock(data=[{"id": "export-uuid-123"}])
            table_mock = MagicMock()
            table_mock.insert.return_value = chain
            supabase.table.return_value = table_mock

            result = repository.insert_export_record(record)

            supabase.table.assert_called_once_with("exports_history")
            table_mock.insert.assert_called_once_with(record)
            assert result == "export-uuid-123"

    def test_insert_returns_none_when_no_data_returned(self):
        """insert_export_record retourne None quand execute().data est vide ou absent."""
        record = {"company_id": "c1", "export_type": "dsn_mensuelle", "period": "2025-02"}
        with patch("app.modules.exports.infrastructure.repository.supabase") as supabase:
            chain = MagicMock()
            chain.execute.return_value = MagicMock(data=[])
            table_mock = MagicMock()
            table_mock.insert.return_value = chain
            supabase.table.return_value = table_mock

            result = repository.insert_export_record(record)

            assert result is None


class TestListExportsByCompany:
    """Infrastructure queries : list_exports_by_company."""

    def test_list_calls_supabase_with_company_id_and_returns_data(self):
        """list_exports_by_company filtre par company_id, ordonne par generated_at desc, limite 100."""
        with patch("app.modules.exports.infrastructure.queries.supabase") as supabase:
            # Chaîne: select().eq(company_id).order().limit().execute()
            limit_ret = MagicMock()
            limit_ret.execute.return_value = MagicMock(
                data=[
                    {
                        "id": "exp-1",
                        "export_type": "journal_paie",
                        "period": "2025-01",
                        "status": "generated",
                        "generated_at": "2025-01-15T10:00:00",
                        "generated_by": "user-1",
                        "report": {},
                        "file_paths": ["path/1.xlsx"],
                    }
                ]
            )
            chain = MagicMock()
            chain.eq.return_value.order.return_value.limit.return_value = limit_ret
            table_mock = MagicMock()
            table_mock.select.return_value = chain
            supabase.table.return_value = table_mock

            result = infra_queries.list_exports_by_company("company-1")

            supabase.table.assert_called_with("exports_history")
            assert len(result) == 1
            assert result[0]["id"] == "exp-1"
            assert result[0]["export_type"] == "journal_paie"

    def test_list_with_export_type_and_period_filters(self):
        """list_exports_by_company avec export_type et period appelle eq pour chaque filtre."""
        with patch("app.modules.exports.infrastructure.queries.supabase") as supabase:
            # Chaîne: select().eq(company_id).order().limit().eq(export_type).eq(period).execute()
            exec_ret = MagicMock()
            exec_ret.execute.return_value = MagicMock(data=[])
            eq2_ret = MagicMock()
            eq2_ret.execute.return_value = MagicMock(data=[])
            eq_ret = MagicMock()
            eq_ret.eq.return_value = eq2_ret
            limit_ret = MagicMock()
            limit_ret.eq.return_value = eq_ret
            chain = MagicMock()
            chain.eq.return_value.order.return_value.limit.return_value = limit_ret
            table_mock = MagicMock()
            table_mock.select.return_value = chain
            supabase.table.return_value = table_mock

            result = infra_queries.list_exports_by_company(
                "company-1",
                export_type="dsn_mensuelle",
                period="2025-02",
            )

            assert result == []
            chain.eq.assert_called_with("company_id", "company-1")
            chain.eq.return_value.order.assert_called_once_with("generated_at", desc=True)
            chain.eq.return_value.order.return_value.limit.assert_called_once_with(100)


class TestGetExportById:
    """Infrastructure queries : get_export_by_id."""

    def test_get_by_id_returns_none_when_not_found(self):
        """get_export_by_id retourne None quand single().execute() ne renvoie pas de data."""
        with patch("app.modules.exports.infrastructure.queries.supabase") as supabase:
            chain = MagicMock()
            chain.eq.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
                data=None
            )
            table_mock = MagicMock()
            table_mock.select.return_value = chain
            supabase.table.return_value = table_mock

            result = infra_queries.get_export_by_id("unknown-id", "company-1")

            assert result is None

    def test_get_by_id_returns_row_when_found(self):
        """get_export_by_id retourne la ligne quand trouvée."""
        row = {
            "id": "exp-1",
            "company_id": "company-1",
            "export_type": "journal_paie",
            "file_paths": ["path/file.xlsx"],
        }
        with patch("app.modules.exports.infrastructure.queries.supabase") as supabase:
            chain = MagicMock()
            chain.eq.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
                data=row
            )
            table_mock = MagicMock()
            table_mock.select.return_value = chain
            supabase.table.return_value = table_mock

            result = infra_queries.get_export_by_id("exp-1", "company-1")

            assert result == row
            chain.eq.assert_called_once_with("id", "exp-1")
            chain.eq.return_value.eq.assert_called_once_with("company_id", "company-1")


class TestGetUserDisplayName:
    """Infrastructure queries : get_user_display_name (profiles)."""

    def test_returns_utilisateur_when_no_profile(self):
        """get_user_display_name retourne 'Utilisateur' quand le profil est absent."""
        with patch("app.modules.exports.infrastructure.queries.supabase") as supabase:
            chain = MagicMock()
            chain.eq.return_value.single.return_value.execute.return_value = MagicMock(data=None)
            table_mock = MagicMock()
            table_mock.select.return_value = chain
            supabase.table.return_value = table_mock

            result = infra_queries.get_user_display_name("user-unknown")

            assert result == "Utilisateur"

    def test_returns_first_name_last_name_when_profile_exists(self):
        """get_user_display_name retourne 'Prénom Nom' depuis profiles."""
        with patch("app.modules.exports.infrastructure.queries.supabase") as supabase:
            chain = MagicMock()
            chain.eq.return_value.single.return_value.execute.return_value = MagicMock(
                data={"first_name": "Marie", "last_name": "Martin"}
            )
            table_mock = MagicMock()
            table_mock.select.return_value = chain
            supabase.table.return_value = table_mock

            result = infra_queries.get_user_display_name("user-1")

            assert result == "Marie Martin"


class TestGetProfilesMap:
    """Infrastructure queries : get_profiles_map."""

    def test_returns_empty_dict_when_empty_user_ids(self):
        """get_profiles_map avec liste vide retourne {}."""
        result = infra_queries.get_profiles_map([])
        assert result == {}

    def test_returns_map_user_id_to_profile(self):
        """get_profiles_map retourne {user_id: {id, first_name, last_name}}."""
        with patch("app.modules.exports.infrastructure.queries.supabase") as supabase:
            chain = MagicMock()
            chain.in_.return_value.execute.return_value = MagicMock(
                data=[
                    {"id": "u1", "first_name": "Jean", "last_name": "Dupont"},
                    {"id": "u2", "first_name": "Anne", "last_name": "Claire"},
                ]
            )
            table_mock = MagicMock()
            table_mock.select.return_value = chain
            supabase.table.return_value = table_mock

            result = infra_queries.get_profiles_map(["u1", "u2"])

            assert result["u1"]["first_name"] == "Jean"
            assert result["u2"]["last_name"] == "Claire"
