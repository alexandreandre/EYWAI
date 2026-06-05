"""Tests unitaires — documents PDF de sortie salarié."""

from __future__ import annotations

from app.modules.payroll.solde_de_tout_compte.document_generator import (
    EmployeeExitDocumentGenerator,
)

_EMP = {
    "first_name": "Paul",
    "last_name": "Durand",
    "date_naissance": "1985-06-20",
    "hire_date": "2020-01-10",
    "job_title": "Technicien",
    "contract_type": "CDI",
    "nir": "1234567890123",
    "salaire_de_base": {"valeur": 2400.0},
}

_CO = {
    "company_name": "Beta SA",
    "siret": "98765432100011",
    "adresse_rue": "5 rue du Port",
    "adresse_code_postal": "44000",
    "adresse_ville": "Nantes",
    "city": "Nantes",
}

_EXIT = {
    "last_working_day": "2025-06-30",
    "exit_type": "demission",
    "notice_period_days": 30,
    "exit_reason": "Projet personnel",
}


def test_certificat_travail_pdf() -> None:
    gen = EmployeeExitDocumentGenerator()
    pdf = gen.generate_certificat_travail(_EMP, _CO, _EXIT)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 800


def test_attestation_pole_emploi_pdf() -> None:
    gen = EmployeeExitDocumentGenerator()
    pdf = gen.generate_attestation_pole_emploi(_EMP, _CO, _EXIT)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 800
