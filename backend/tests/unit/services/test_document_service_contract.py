"""Tests unitaires — bibliothèque documents CDI/CDD."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

weasyprint = pytest.importorskip("weasyprint")

from app.services.document_service import DocumentService

_EMP = {
    "first_name": "Luc",
    "last_name": "Bernard",
    "hire_date": "2024-01-01",
    "contract_type": "CDI",
    "job_title": "Assistant",
    "salaire_de_base": {"valeur": 2200},
}

_CO = {
    "company_name": "Delta SARL",
    "siret": "11122233344455",
    "adresse_rue": "3 rue Delta",
    "adresse_code_postal": "33000",
    "adresse_ville": "Bordeaux",
}


@patch.object(DocumentService, "get_active_template", return_value=None)
@patch("app.services.document_service.supabase")
def test_generate_document_cdi_uses_contract_pdf(mock_supabase, _mock_tpl) -> None:
    mock_supabase.storage.from_.return_value.upload = MagicMock()
    mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": "doc-1"}]
    )
    svc = DocumentService()
    result = svc.generate_document(
        company_id="co-1",
        employee_id="emp-1",
        document_type="cdi",
        category="contrat",
        employee_data=_EMP,
        company_data=_CO,
    )
    assert result["document_id"] == "doc-1"
    upload_call = mock_supabase.storage.from_.return_value.upload
    assert upload_call.called
    pdf_call = next(
        c for c in upload_call.call_args_list if c[0][2]["content-type"] == "application/pdf"
    )
    pdf_bytes = pdf_call[0][1]
    assert pdf_bytes.startswith(b"%PDF")
