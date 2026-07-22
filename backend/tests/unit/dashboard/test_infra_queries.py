"""
Tests unitaires des requêtes d'infrastructure Supabase du dashboard.

Régression : fetch_payslips_by_company DOIT projeter `year`, sinon
aggregate_payslips_by_period écarte tous les bulletins (year None) et le
graphique Coûts tombe à tort sur la DSN uniquement.
"""

from unittest.mock import MagicMock, patch

from app.modules.dashboard.infrastructure import queries
from app.modules.payroll.domain.payroll_kpi_resolver import (
    aggregate_payslips_by_period,
)


COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"


def _mock_client_returning(rows):
    """Construit un client Supabase factice capturant l'argument de select()."""
    captured = {}
    execute = MagicMock(return_value=MagicMock(data=rows))
    eq = MagicMock(return_value=MagicMock(execute=execute))

    def select(cols):
        captured["cols"] = cols
        return MagicMock(eq=eq)

    table = MagicMock(return_value=MagicMock(select=MagicMock(side_effect=select)))
    client = MagicMock(table=table)
    return client, captured


class TestFetchPayslipsByCompany:
    """fetch_payslips_by_company projette month, year ET payslip_data."""

    @patch("app.modules.dashboard.infrastructure.queries.get_supabase_client")
    def test_select_includes_year(self, mock_get_client):
        """La projection contient `year` (sinon l'agrégation par période casse)."""
        client, captured = _mock_client_returning([])
        mock_get_client.return_value = client

        queries.fetch_payslips_by_company(COMPANY_ID)

        cols = captured["cols"]
        assert "year" in cols, f"projection sans year: {cols!r}"
        assert "month" in cols
        assert "payslip_data" in cols

    @patch("app.modules.dashboard.infrastructure.queries.get_supabase_client")
    def test_rows_aggregate_into_periods(self, mock_get_client):
        """Les lignes renvoyées s'agrègent bien par période YYYY-MM (bulletins pris en compte)."""
        rows = [
            {"month": 5, "year": 2026, "payslip_data": {"salaire_brut": 2000, "net_a_payer": 1560}},
            {"month": 6, "year": 2026, "payslip_data": {"salaire_brut": 2100, "net_a_payer": 1630}},
        ]
        client, _ = _mock_client_returning(rows)
        mock_get_client.return_value = client

        result = queries.fetch_payslips_by_company(COMPANY_ID)
        agg = aggregate_payslips_by_period(result)

        assert set(agg.keys()) == {"2026-05", "2026-06"}
        assert agg["2026-06"].gross == 2100
