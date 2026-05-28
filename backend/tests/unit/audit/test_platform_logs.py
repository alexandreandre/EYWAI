"""Tests du journal d'audit plateforme (list_logs_platform)."""

from unittest.mock import MagicMock, patch

from app.modules.audit.infrastructure.repository import audit_repository


@patch("app.modules.audit.infrastructure.repository.supabase")
def test_list_logs_platform_enriches_company_name(mock_sb):
    table = MagicMock()
    mock_sb.table.return_value = table
    q = table.select.return_value
    q.order.return_value = q
    q.range.return_value = q
    q.execute.return_value = MagicMock(
        data=[
            {
                "id": "log-1",
                "company_id": "c1",
                "action": "user.create",
                "resource_type": "user",
                "created_at": "2026-01-01T00:00:00Z",
            }
        ]
    )
    companies_q = MagicMock()
    mock_sb.table.side_effect = lambda name: table if name == "audit_logs" else companies_q
    companies_q.select.return_value.in_.return_value.execute.return_value = MagicMock(
        data=[{"id": "c1", "company_name": "Acme"}]
    )

    rows = audit_repository.list_logs_platform(limit=10)

    assert len(rows) == 1
    assert rows[0]["company_name"] == "Acme"


@patch("app.modules.audit.infrastructure.repository.supabase")
def test_list_logs_platform_returns_empty_on_error(mock_sb):
    mock_sb.table.side_effect = RuntimeError("db down")
    assert audit_repository.list_logs_platform() == []
