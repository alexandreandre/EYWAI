"""
Tests unitaires — DocumentService (mocks Supabase, pas d'appel réel).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.document_service import DocumentService


def test_t10_get_active_template_returns_none_when_no_row() -> None:
    """Pas de ligne template : execute() renvoie data=None (mock Supabase, pas d'appel réel)."""
    exec_res = MagicMock()
    exec_res.data = None
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.maybe_single.return_value.execute.return_value = (
        exec_res
    )
    svc = DocumentService()
    with patch("app.services.document_service.supabase", mock_sb):
        assert (
            svc.get_active_template("550e8400-e29b-41d4-a716-446655440000", "cdi") is None
        )


def test_t11_trace_existing_document_swallows_supabase_error() -> None:
    svc = DocumentService()
    mock_table = MagicMock()
    mock_table.insert.return_value.execute.side_effect = RuntimeError("insert KO")

    with patch("app.services.document_service.supabase") as mock_sb:
        mock_sb.table.return_value = mock_table
        out = svc.trace_existing_document(
            company_id="c1",
            employee_id="e1",
            document_type="certificat_travail",
            category="attestation_sortie",
            file_url="path/to.pdf",
            file_name="certif.pdf",
        )
    assert out == ""


def test_t12_update_status_invalid_raises_value_error() -> None:
    svc = DocumentService()
    with pytest.raises(ValueError, match="Statut invalide"):
        svc.update_status("doc-id", "company-id", "statut_inconnu")
