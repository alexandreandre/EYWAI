"""Attestation de salaire CPAM : motif → colonne (rétabli / net), hors Cerfa officiel."""

from __future__ import annotations

import io
from datetime import date

import pytest
from PyPDF2 import PdfReader

from app.modules.payroll.documents.salary_certificate_generator import (
    KIND_NET,
    KIND_RETABLI,
    SalaryCertificateGenerator,
    amounts_from_payslip_data,
    resolve_cpam_attestation_kind,
)


pytestmark = pytest.mark.unit


def _payslip_avec_absence() -> dict:
    """Brut diminué d'une absence ; le rétabli DSN (type 003) reste au contractuel."""
    return {
        "salaire_brut": 1800.0,
        "net_a_payer": 1400.0,
        "total_primes": 50.0,
        "calcul_du_brut": [
            {"libelle": "Salaire de base", "gain": 2000.0, "quantite": 151.67},
            {
                "libelle": "SOUS-TOTAL SALAIRE CONTRACTUEL",
                "gain": 2000.0,
                "quantite": 151.67,
                "is_sous_total": True,
            },
        ],
        "details_absences": [{"perte": 200.0}],
    }


def _pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _reference(kind: str) -> dict:
    amounts = amounts_from_payslip_data(_payslip_avec_absence())
    month = {
        "year": 2026,
        "month": 7,
        "month_name": "Juillet",
        **amounts,
        "has_payslip": True,
    }
    return {
        "kind": kind,
        "reference_months": [month],
        "period_start": date(2026, 7, 1),
        "period_end": date(2026, 7, 31),
        "months_count": 1,
        "total_retabli": amounts["salaire_retabli"],
        "total_net": amounts["salaire_net"],
        "total_brut": amounts["salaire_brut"],
        "average_monthly": (
            amounts["salaire_retabli"] if kind == KIND_RETABLI else amounts["salaire_net"]
        ),
    }


_EMPLOYEE = {
    "first_name": "Marion",
    "last_name": "Gautheron",
    "date_naissance": "1990-04-12",
    "nir": "2900475123456",
    "hire_date": "2020-01-06",
    "job_title": "Opératrice",
}

_COMPANY = {
    "company_name": "COLORPLAST",
    "raison_sociale": "COLORPLAST",
    "siret": "35157189700029",
    "adresse_rue": "ZI Les Plaines",
    "adresse_code_postal": "01100",
    "adresse_ville": "Oyonnax",
    "city": "Oyonnax",
}


class TestResolveKind:
    def test_maladie_maternite_paternite_utilisent_salaires_retablis(self):
        for absence_type in ("arret_maladie", "arret_maternite", "arret_paternite"):
            assert resolve_cpam_attestation_kind(absence_type) == KIND_RETABLI

    def test_at_et_mp_utilisent_salaires_nets(self):
        assert resolve_cpam_attestation_kind("arret_at") == KIND_NET
        assert resolve_cpam_attestation_kind("arret_maladie_pro") == KIND_NET

    def test_arret_type_accident_travail_force_les_nets(self):
        assert (
            resolve_cpam_attestation_kind("arret_maladie", arret_type="accident_travail")
            == KIND_NET
        )


class TestAmountsFromPayslip:
    def test_retabli_remonte_le_salaire_hors_absence(self):
        amounts = amounts_from_payslip_data(_payslip_avec_absence())
        assert amounts["salaire_brut"] == 1800.0
        assert amounts["salaire_net"] == 1400.0
        assert amounts["salaire_retabli"] == 2000.0

    def test_sans_bulletin_detaille_le_retabli_suit_le_brut(self):
        amounts = amounts_from_payslip_data(
            {"salaire_brut": 2100.0, "net_a_payer": 1600.0}
        )
        assert amounts["salaire_retabli"] == 2100.0
        assert amounts["salaire_net"] == 1600.0


class TestPdfCpam:
    def test_maladie_affiche_salaires_retablis_pas_cerfa(self):
        gen = SalaryCertificateGenerator()
        pdf = gen.generate_salary_certificate(
            _EMPLOYEE,
            _COMPANY,
            {
                "type": "arret_maladie",
                "selected_days": ["2026-08-17", "2026-08-18"],
            },
            _reference(KIND_RETABLI),
        )
        text = _pdf_text(pdf)
        assert "Salaire rétabli" in text
        assert "2 000.00" in text
        assert "Cerfa" not in text
        assert "11135" not in text
        assert "11137" not in text
        # Le brut diminué ne doit pas être la colonne de référence.
        assert "1 800.00" not in text

    def test_at_affiche_salaires_nets(self):
        gen = SalaryCertificateGenerator()
        pdf = gen.generate_salary_certificate(
            _EMPLOYEE,
            _COMPANY,
            {
                "type": "arret_at",
                "selected_days": ["2026-08-17"],
            },
            _reference(KIND_NET),
        )
        text = _pdf_text(pdf)
        assert "Salaire net" in text
        assert "1 400.00" in text
        assert "Salaire rétabli" not in text
        assert "Cerfa" not in text
