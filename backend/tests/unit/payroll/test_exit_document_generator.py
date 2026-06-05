"""Tests unitaires — attestation employeur et documents de sortie."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.modules.payroll.documents.attestation_employeur_salary_history import (
    compute_attestation_month_count,
    get_salary_history,
)
from app.modules.payroll.solde_de_tout_compte.document_generator import (
    EmployeeExitDocumentGenerator,
)

_EMP = {
    "id": "emp-1",
    "first_name": "Paul",
    "last_name": "Durand",
    "date_naissance": "1985-06-20",
    "hire_date": "2020-01-10",
    "job_title": "Technicien",
    "contract_type": "CDI",
    "nir": "1234567890123",
    "salaire_de_base": {"valeur": 2400.0},
    "duree_hebdomadaire": 35,
}

_EMP_SENIOR = {
    **_EMP,
    "date_naissance": "1968-01-15",
}

_CO = {
    "company_name": "Beta SA",
    "siret": "98765432100011",
    "adresse_rue": "5 rue du Port",
    "adresse_code_postal": "44000",
    "adresse_ville": "Nantes",
    "city": "Nantes",
    "naf_code": "2562Z",
    "urssaf_number": "123456789",
}

_EXIT = {
    "last_working_day": "2025-06-30",
    "exit_type": "demission",
    "notice_period_days": 30,
    "exit_reason": "Projet personnel",
}

_INDEMNITIES = {
    "indemnite_preavis": {"montant": 2400.0},
    "indemnite_conges": {"montant": 800.0},
}


def test_compute_attestation_month_count_under_55() -> None:
    assert compute_attestation_month_count("1985-06-20", "2025-06-30") == 25


def test_compute_attestation_month_count_55_or_more() -> None:
    assert compute_attestation_month_count("1968-01-15", "2025-06-30") == 37


def test_get_salary_history_fallback_without_payslips() -> None:
    history = get_salary_history(
        employee_id="emp-1",
        employee_data=_EMP,
        end_date="2025-06-30",
        supabase_client=None,
        month_count=3,
    )
    assert history["month_count"] == 3
    assert len(history["months"]) == 3
    assert history["months"][-1]["year"] == 2025
    assert history["months"][-1]["month"] == 6
    assert history["months"][-1]["gross_salary"] == 2400.0
    assert history["months"][-1]["is_estimated"] is True
    assert history["total_brut"] == pytest.approx(7200.0)


def test_get_salary_history_from_payslips_mock() -> None:
    mock_sb = MagicMock()
    mock_execute = MagicMock()
    mock_execute.data = [
        {
            "year": 2025,
            "month": 5,
            "payslip_data": {
                "salaire_brut": 2500.0,
                "total_primes": 100.0,
                "heures_travaillees": 151.67,
                "details_absences": [{"quantite": 2, "unite": "jours"}],
            },
        },
        {
            "year": 2025,
            "month": 6,
            "payslip_data": {
                "salaire_brut": 2600.0,
                "total_primes": 0,
                "nombre_jours_travailles": 20,
            },
        },
    ]
    (
        mock_sb.table.return_value.select.return_value.eq.return_value.execute
    ) = MagicMock(return_value=mock_execute)

    history = get_salary_history(
        employee_id="emp-1",
        employee_data=_EMP,
        end_date="2025-06-30",
        supabase_client=mock_sb,
        month_count=2,
    )
    assert len(history["months"]) == 2
    assert history["months"][0]["gross_salary"] == 2500.0
    assert history["months"][0]["has_payslip"] is True
    assert history["months"][0]["primes"] == 100.0
    assert "h" in history["months"][0]["working_time"] or "jour" in history["months"][0]["working_time"]
    assert history["months"][1]["gross_salary"] == 2600.0
    assert len(history["primes_lines"]) == 1


def test_certificat_travail_pdf() -> None:
    gen = EmployeeExitDocumentGenerator()
    pdf = gen.generate_certificat_travail(_EMP, _CO, _EXIT)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 800


def test_attestation_pole_emploi_pdf() -> None:
    gen = EmployeeExitDocumentGenerator()
    pdf = gen.generate_attestation_pole_emploi(
        _EMP,
        _CO,
        _EXIT,
        indemnities=_INDEMNITIES,
        supabase_client=None,
    )
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 2000


def test_attestation_pole_emploi_pdf_senior_37_months() -> None:
    gen = EmployeeExitDocumentGenerator()
    pdf = gen.generate_attestation_pole_emploi(
        _EMP_SENIOR,
        _CO,
        _EXIT,
        indemnities=_INDEMNITIES,
        supabase_client=None,
    )
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 2500
