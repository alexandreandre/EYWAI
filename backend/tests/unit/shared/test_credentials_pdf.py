"""Tests unitaires — credentials PDF dynamiques."""

from __future__ import annotations

import pytest

weasyprint = pytest.importorskip("weasyprint")

from app.shared.infrastructure.pdf.credentials import generate_credentials_pdf

_COMPANY = {
    "company_name": "Gamma SAS",
    "nom_signataire_rh": "Sophie RH",
    "qualite_signataire_rh": "Directrice RH",
    "adresse_rue": "2 avenue Test",
    "adresse_code_postal": "69001",
    "adresse_ville": "Lyon",
}


def test_generate_credentials_pdf_dynamic_signatory() -> None:
    pdf = generate_credentials_pdf(
        "Paul",
        "Durand",
        "paul.durand",
        "TempPass123!",
        company_data=_COMPANY,
    )
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 2000
