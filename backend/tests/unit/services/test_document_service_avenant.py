"""Tests unitaires — routage avenant dans document_service."""

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
    "duree_hebdomadaire": 35,
    "lieu_travail": "Bordeaux",
}

_CO = {
    "company_name": "Delta SARL",
    "siret": "11122233344455",
    "adresse_rue": "3 rue Delta",
    "adresse_code_postal": "33000",
    "adresse_ville": "Bordeaux",
}

_CTX = {
    "type_avenant": "avenant_salaire",
    "date_effet": "2026-06-01",
    "ancien_salaire": 2200,
    "nouveau_salaire": 2400,
    "motif": "Augmentation annuelle",
}


@patch.object(DocumentService, "get_active_template", return_value=None)
@patch("app.services.document_service.supabase")
def test_generate_document_avenant_salaire_uses_avenant_pdf(mock_supabase, _mock_tpl) -> None:
    mock_supabase.storage.from_.return_value.upload = MagicMock()
    mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": "doc-avenant-1"}]
    )
    svc = DocumentService()
    result = svc.generate_document(
        company_id="co-1",
        employee_id="emp-1",
        document_type="avenant_salaire",
        category="avenant",
        employee_data=_EMP,
        company_data=_CO,
        context=_CTX,
    )
    assert result["document_id"] == "doc-avenant-1"
    upload_call = mock_supabase.storage.from_.return_value.upload
    assert upload_call.called
    pdf_bytes = upload_call.call_args[0][1]
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 3000


@patch.object(DocumentService, "get_active_template", return_value=None)
@patch.object(DocumentService, "_generate_fallback_pdf")
@patch("app.services.document_service.supabase")
def test_generate_document_avenant_does_not_use_fallback_attestation(
    mock_supabase, mock_fallback, _mock_tpl
) -> None:
    mock_supabase.storage.from_.return_value.upload = MagicMock()
    mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": "doc-avenant-2"}]
    )
    svc = DocumentService()
    svc.generate_document(
        company_id="co-1",
        employee_id="emp-1",
        document_type="avenant_poste",
        category="avenant",
        employee_data=_EMP,
        company_data=_CO,
        context={
            "type_avenant": "avenant_poste",
            "date_effet": "2026-06-01",
            "ancien_poste": "Assistant",
            "nouveau_poste": "Technicien",
        },
    )
    mock_fallback.assert_not_called()
