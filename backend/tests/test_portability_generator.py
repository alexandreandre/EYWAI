"""
Tests unitaires — attestations de portabilité (PDF).
"""

from __future__ import annotations

from app.services.portability_document_generator import (
    EXIT_TYPE_LIBELLES,
    portability_generator,
)

_EMP = {"first_name": "Claire", "last_name": "Petit", "job_title": "Comptable"}
_CO = {"company_name": "Gamma LLC", "siret": "99988877766655"}


def test_t13_generate_portabilite_mutuelle_returns_pdf_bytes() -> None:
    pdf = portability_generator.generate_portabilite_mutuelle(
        _EMP, _CO, "31/12/2025", "licenciement"
    )
    assert isinstance(pdf, bytes)
    assert len(pdf) > 100
    assert pdf.startswith(b"%PDF")


def test_t14_generate_portabilite_prevoyance_returns_pdf_bytes() -> None:
    pdf = portability_generator.generate_portabilite_prevoyance(
        _EMP, _CO, "31/12/2025", "fin_cdd"
    )
    assert isinstance(pdf, bytes)
    assert len(pdf) > 100
    assert pdf.startswith(b"%PDF")


def test_t15_exit_type_libelles_covers_eligible_motifs() -> None:
    for key in ("licenciement", "fin_cdd", "rupture_conventionnelle"):
        assert key in EXIT_TYPE_LIBELLES
        assert isinstance(EXIT_TYPE_LIBELLES[key], str)
        assert len(EXIT_TYPE_LIBELLES[key]) > 0
