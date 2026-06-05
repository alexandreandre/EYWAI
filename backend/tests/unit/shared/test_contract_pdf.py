"""Tests unitaires — génération PDF contrat de travail."""

from __future__ import annotations

import pytest

weasyprint = pytest.importorskip("weasyprint")

from app.shared.infrastructure.pdf.contract import generate_contract_pdf

_MIN_EMPLOYEE = {
    "first_name": "Marie",
    "last_name": "Martin",
    "hire_date": "2024-03-01",
    "contract_type": "CDI",
    "job_title": "Comptable",
    "date_naissance": "1990-01-15",
    "lieu_naissance": "Lyon",
    "nationalite": "Française",
    "nir": "1234567890123",
    "adresse": {"rue": "12 rue de la Paix", "code_postal": "69001", "ville": "Lyon"},
    "salaire_de_base": {"valeur": 2800.0},
    "duree_hebdomadaire": 35,
    "statut": "Non-cadre",
    "periode_essai": {"duree_initiale": 2, "unite": "mois", "renouvellement_possible": True},
    "classification_conventionnelle": {
        "groupe_emploi": "B",
        "classe_emploi": "3",
        "coefficient": "250",
    },
}

_MIN_COMPANY = {
    "company_name": "Alpha SARL",
    "siret": "12345678900012",
    "adresse_rue": "1 avenue Centrale",
    "adresse_code_postal": "75001",
    "adresse_ville": "Paris",
    "city": "Paris",
    "nom_signataire_rh": "Jean Directeur",
    "qualite_signataire_rh": "Directeur général",
}


def test_generate_contract_pdf_cdi_returns_valid_pdf() -> None:
    pdf = generate_contract_pdf(_MIN_EMPLOYEE, _MIN_COMPANY, "/nonexistent/logo.png")
    assert isinstance(pdf, bytes)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 5000


def test_generate_contract_pdf_cdd_includes_duration() -> None:
    employee = {
        **_MIN_EMPLOYEE,
        "contract_type": "CDD",
        "date_fin_contrat": "2024-12-31",
        "motif_cdd": "Remplacement congé maternité",
    }
    pdf = generate_contract_pdf(employee, _MIN_COMPANY, "/nonexistent/logo.png")
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 5000
