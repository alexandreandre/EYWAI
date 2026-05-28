"""
Tests unitaires — common_attestation_generator (PDF ReportLab).
"""

from __future__ import annotations

import pytest

from app.services.common_attestation_generator import (
    CommonAttestationGenerator,
    common_attestation_generator,
)

_MIN_EMPLOYEE = {
    "first_name": "Paul",
    "last_name": "Durand",
    "job_title": "Technicien",
    "hire_date": "2019-06-01",
    "contract_type": "CDI",
    "salaire_de_base": {"valeur": 2200.0},
    "duree_hebdomadaire": 35,
    "gender": "m",
}

_MIN_COMPANY = {
    "company_name": "Beta SA",
    "siret": "11122233344455",
    "city": "Nantes",
}


def test_t5_generate_attestation_emploi_pdf_bytes() -> None:
    pdf = common_attestation_generator.generate(
        "attestation_emploi", _MIN_EMPLOYEE, _MIN_COMPANY, {}
    )
    assert isinstance(pdf, bytes)
    assert len(pdf) > 100
    assert pdf.startswith(b"%PDF")


def test_t6_generate_attestation_salaire_pdf_bytes() -> None:
    pdf = common_attestation_generator.generate(
        "attestation_salaire", _MIN_EMPLOYEE, _MIN_COMPANY, {}
    )
    assert isinstance(pdf, bytes)
    assert len(pdf) > 100


def test_t7_generate_attestation_retraite_pdf_bytes() -> None:
    pdf = common_attestation_generator.generate(
        "attestation_retraite", _MIN_EMPLOYEE, _MIN_COMPANY, {}
    )
    assert isinstance(pdf, bytes)
    assert len(pdf) > 100
    assert pdf.startswith(b"%PDF")


def test_t8_generate_unknown_type_raises_value_error() -> None:
    with pytest.raises(ValueError, match="non pris en charge"):
        common_attestation_generator.generate(
            "type_inexistant", _MIN_EMPLOYEE, _MIN_COMPANY, {}
        )


def test_t9_all_attestation_types_generate_without_crash() -> None:
    gen = CommonAttestationGenerator()
    for att_type in gen.ATTESTATION_TYPES:
        pdf = gen.generate(att_type, _MIN_EMPLOYEE, _MIN_COMPANY, {})
        assert isinstance(pdf, bytes)
        assert len(pdf) > 50
