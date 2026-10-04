"""Les deux lectures qui datent la dernière modification des bulletins d'un mois."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core.constants import AUDIT_BULLETIN_SUPPRIME
from app.modules.exports.infrastructure import queries

pytestmark = pytest.mark.unit


def test_les_calculs_des_bulletins_des_annees_demandees_toutes_pages():
    client = MagicMock()
    requete = client.table.return_value.select.return_value.eq.return_value.in_.return_value.order.return_value
    pleine = [{"year": 2026, "month": 9, "generated_at": "x"}] * 1000
    requete.range.return_value.execute.side_effect = [
        SimpleNamespace(data=pleine),
        SimpleNamespace(data=[{"year": 2026, "month": 8, "generated_at": "y"}]),
    ]
    with patch.object(queries, "supabase", client):
        lignes = queries.list_calculs_des_bulletins("c1", [2025, 2026])

    assert len(lignes) == 1001
    client.table.assert_called_with("payslips")
    client.table.return_value.select.assert_called_with("year, month, generated_at")
    client.table.return_value.select.return_value.eq.assert_called_with("company_id", "c1")
    client.table.return_value.select.return_value.eq.return_value.in_.assert_called_with("year", [2025, 2026])
    assert [c.args for c in requete.range.call_args_list] == [(0, 999), (1000, 1999)]


def test_sans_annee_rien_n_est_lu():
    client = MagicMock()
    with patch.object(queries, "supabase", client):
        assert queries.list_calculs_des_bulletins("c1", []) == []
    client.table.assert_not_called()


def test_les_suppressions_de_bulletins_depuis_une_date():
    client = MagicMock()
    requete = client.table.return_value.select.return_value.match.return_value.gte.return_value
    requete.execute.return_value = SimpleNamespace(
        data=[{"details": {"year": 2026, "month": 9}, "created_at": "2026-10-03T09:00:00+00:00"}]
    )
    with patch.object(queries, "supabase", client):
        lignes = queries.list_suppressions_de_bulletins("c1", "2026-10-01T00:00:00+00:00")

    assert lignes == [{"details": {"year": 2026, "month": 9}, "created_at": "2026-10-03T09:00:00+00:00"}]
    client.table.assert_called_with("audit_logs")
    client.table.return_value.select.assert_called_with("details, created_at")
    client.table.return_value.select.return_value.match.assert_called_with(
        {"company_id": "c1", "action": AUDIT_BULLETIN_SUPPRIME}
    )
    client.table.return_value.select.return_value.match.return_value.gte.assert_called_with(
        "created_at", "2026-10-01T00:00:00+00:00"
    )
