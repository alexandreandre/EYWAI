"""Saisie d'un contrat passé : la fin ne peut pas précéder le début."""

import pytest
from pydantic import ValidationError

from app.modules.employees.application.contract_periods import ContractPeriodIn


def test_periode_acceptee():
    periode = ContractPeriodIn(
        contract_type=" CDD ",
        date_debut="2026-03-01",
        date_fin="2026-05-31",
    )
    assert periode.contract_type == "CDD"
    assert periode.date_fin.isoformat() == "2026-05-31"


def test_fin_avant_debut_refusee():
    with pytest.raises(ValidationError):
        ContractPeriodIn(
            contract_type="CDD",
            date_debut="2026-09-01",
            date_fin="2026-05-31",
        )
