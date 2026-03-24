"""
Tests d'intégration du repository repos_compensateur (infrastructure/repository.py).

Avec DB de test (fixture db_session) : opérations réelles contre repos_compensateur_credits.
Sans DB : mock de supabase pour valider les appels (upsert_credit, get_jours_by_employee_year).
"""
from unittest.mock import MagicMock, patch

import pytest

from app.modules.repos_compensateur.domain.entities import ReposCredit
from app.modules.repos_compensateur.infrastructure.repository import (
    get_jours_by_employee_year,
    upsert_credit,
)


pytestmark = pytest.mark.integration


class TestUpsertCredit:
    """Repository upsert_credit."""

    def test_upsert_calls_supabase_with_correct_row_and_conflict(self):
        """upsert_credit appelle supabase.table().upsert(..., on_conflict=...).execute()."""
        with patch(
            "app.modules.repos_compensateur.infrastructure.repository.supabase"
        ) as supabase:
            table_mock = MagicMock()
            chain = MagicMock()
            chain.execute.return_value = MagicMock()
            table_mock.upsert.return_value = chain
            supabase.table.return_value = table_mock

            credit = ReposCredit(
                employee_id="emp-1",
                company_id="comp-1",
                year=2025,
                month=6,
                source="cor",
                heures=14.0,
                jours=2.0,
            )
            result = upsert_credit(credit)

            supabase.table.assert_called_once_with("repos_compensateur_credits")
            table_mock.upsert.assert_called_once()
            call_args = table_mock.upsert.call_args
            row = call_args[0][0]
            assert row["employee_id"] == "emp-1"
            assert row["company_id"] == "comp-1"
            assert row["year"] == 2025
            assert row["month"] == 6
            assert row["source"] == "cor"
            assert row["heures"] == 14.0
            assert row["jours"] == 2.0
            assert call_args[1].get("on_conflict") == "employee_id,year,month,source"
            assert result is True

    def test_upsert_returns_false_on_exception(self):
        """Si upsert lève une exception → retourne False."""
        with patch(
            "app.modules.repos_compensateur.infrastructure.repository.supabase"
        ) as supabase:
            table_mock = MagicMock()
            chain = MagicMock()
            chain.execute.side_effect = Exception("DB error")
            table_mock.upsert.return_value = chain
            supabase.table.return_value = table_mock

            credit = ReposCredit(
                employee_id="emp-1",
                company_id="comp-1",
                year=2025,
                month=6,
                source="cor",
                heures=7.0,
                jours=1.0,
            )
            result = upsert_credit(credit)

            assert result is False


class TestGetJoursByEmployeeYear:
    """Repository get_jours_by_employee_year."""

    def test_empty_employee_ids_returns_empty_dict(self):
        """employee_ids vide → {} sans appeler Supabase."""
        with patch(
            "app.modules.repos_compensateur.infrastructure.repository.supabase"
        ) as supabase:
            result = get_jours_by_employee_year([], 2025)
            assert result == {}
            supabase.table.assert_not_called()

    def test_calls_supabase_and_aggregates_jours_by_employee(self):
        """Appelle select(employee_id, jours).in_().eq(year).execute() et somme les jours par employee_id."""
        with patch(
            "app.modules.repos_compensateur.infrastructure.repository.supabase"
        ) as supabase:
            table_mock = MagicMock()
            chain = MagicMock()
            chain.in_.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[
                    {"employee_id": "emp-1", "jours": 2.0},
                    {"employee_id": "emp-1", "jours": 3.0},
                    {"employee_id": "emp-2", "jours": 1.5},
                ]
            )
            table_mock.select.return_value = chain
            supabase.table.return_value = table_mock

            result = get_jours_by_employee_year(["emp-1", "emp-2"], 2025)

            assert result["emp-1"] == 5.0
            assert result["emp-2"] == 1.5
            table_mock.select.assert_called_once_with("employee_id", "jours")
            chain.in_.assert_called_once_with("employee_id", ["emp-1", "emp-2"])
            chain.in_.return_value.eq.assert_called_once_with("year", 2025)

    def test_empty_data_returns_empty_dict(self):
        """Si execute() retourne data vide ou None → {}."""
        with patch(
            "app.modules.repos_compensateur.infrastructure.repository.supabase"
        ) as supabase:
            table_mock = MagicMock()
            chain = MagicMock()
            chain.in_.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[]
            )
            table_mock.select.return_value = chain
            supabase.table.return_value = table_mock

            result = get_jours_by_employee_year(["emp-1"], 2025)

            assert result == {}

    def test_missing_jours_treated_as_zero(self):
        """Ligne sans 'jours' ou None → 0.0 dans la somme."""
        with patch(
            "app.modules.repos_compensateur.infrastructure.repository.supabase"
        ) as supabase:
            table_mock = MagicMock()
            chain = MagicMock()
            chain.in_.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[
                    {"employee_id": "emp-1", "jours": 2.0},
                    {"employee_id": "emp-1"},  # jours manquant
                ]
            )
            table_mock.select.return_value = chain
            supabase.table.return_value = table_mock

            result = get_jours_by_employee_year(["emp-1"], 2025)

            assert result["emp-1"] == 2.0
