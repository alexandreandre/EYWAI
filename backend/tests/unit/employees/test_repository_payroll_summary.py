"""Tests unitaires — liste summary paie (éligibilité sans filtrage)."""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.employees.infrastructure.repository import EmployeeRepository


pytestmark = pytest.mark.unit


def _complete_payroll_fields():
    return {
        "nir": "1850574001234",
        "date_naissance": "1985-05-01",
        "adresse": {"ville": "Paris"},
        "coordonnees_bancaires": {"iban": "FR7612345678901234567890123"},
        "salaire_de_base": {"montant": 2500},
    }


@patch("app.modules.employees.infrastructure.repository.supabase")
def test_payroll_summary_returns_active_with_eligibility_flags(mock_supabase):
    """status=payroll : tous les actifs, avec payroll_eligible, sans exclure les incomplets."""
    complete = {
        "id": "e1",
        "first_name": "Jean",
        "last_name": "Dupont",
        "employment_status": "actif",
        **_complete_payroll_fields(),
    }
    incomplete = {
        "id": "e2",
        "first_name": "Marie",
        "last_name": "Martin",
        "employment_status": "en_onboarding",
        "nir": None,
    }
    departed = {
        "id": "e3",
        "first_name": "Paul",
        "last_name": "Durand",
        "employment_status": "parti",
        **_complete_payroll_fields(),
    }

    table = MagicMock()
    mock_supabase.table.return_value = table
    table.select.return_value = table
    table.eq.return_value = table
    table.order.return_value = table
    table.execute.return_value = MagicMock(data=[complete, incomplete, departed])

    repo = EmployeeRepository()
    rows = repo.get_summary_by_company("company-1", payroll_ready_only=True)

    # Un parti reste dans la liste paie : il a des bulletins à voir et un
    # dernier mois à payer (Demory, sorti le 24/07, absent de juin et juillet —
    # retour Gaëlle 12/09). La couche application ne garde que ceux dont la
    # sortie est datée ; l'écran décide ensuite mois par mois.
    assert len(rows) == 3
    by_id = {row["id"]: row for row in rows}
    assert by_id["e1"]["payroll_eligible"] is True
    assert by_id["e1"]["profile_complete"] is True
    assert by_id["e2"]["payroll_eligible"] is False
    assert by_id["e2"]["employment_status"] == "en_onboarding"
    assert by_id["e2"]["missing_payroll_fields"]
    assert by_id["e3"]["employment_status"] == "parti"
    assert by_id["e3"]["payroll_eligible"] is True
