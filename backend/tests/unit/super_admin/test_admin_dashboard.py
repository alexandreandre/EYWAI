"""Tests stats dashboard Administration EYWAI (support, badges)."""

from unittest.mock import MagicMock, patch

from app.modules.super_admin.infrastructure import queries as infra_queries


@patch("app.modules.super_admin.infrastructure.queries.get_supabase_client")
def test_get_support_badges_counts_open(mock_get_client):
    mock_sb = MagicMock()
    mock_get_client.return_value = mock_sb
    mock_sb.table.return_value.select.return_value.execute.return_value = MagicMock(
        data=[
            {"status": "envoye", "urgency": "elevee"},
            {"status": "en_cours", "urgency": "normale"},
            {"status": "resolu", "urgency": "faible"},
        ]
    )
    out = infra_queries.get_support_badges()
    assert out["pending"] == 2
    assert out["urgent"] == 1
