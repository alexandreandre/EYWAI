"""Les montants des saisies et avances sortent en nombre dans le JSON.

Gautheron (Colorplast, 12/09/2026) : `amount` arrivait en chaîne « "46.49" »,
le frontend appelait `toFixed` dessus et la page tombait en écran blanc.
"""

import json
from decimal import Decimal

import pytest

from app.modules.saisies_avances.schemas.responses import (
    SalaryAdvance,
    SalarySeizure,
    SeizableAmountCalculation,
)

pytestmark = pytest.mark.unit


def test_saisie_amount_en_nombre():
    saisie = SalarySeizure(
        id="s1",
        company_id="co",
        employee_id="e",
        type="saisie_arret",
        creditor_name="SGC OYONNAX",
        amount=Decimal("46.49"),
        calculation_mode="fixe",
        start_date="2026-07-01",
        status="active",
        priority=4,
        created_at="2026-09-12T07:03:03",
        updated_at="2026-09-12T07:03:03",
    )
    rendu = json.loads(saisie.model_dump_json())
    assert rendu["amount"] == 46.49
    assert isinstance(rendu["amount"], float)
    assert rendu["percentage"] is None


def test_avance_montants_en_nombre():
    avance = SalaryAdvance(
        id="a1",
        company_id="co",
        employee_id="e",
        type="acompte_salaire",
        requested_amount=Decimal("300"),
        approved_amount=Decimal("250.5"),
        remaining_amount=Decimal("250.5"),
        request_date="2026-09-01",
        requested_date="2026-09-01",
        repayment_months=1,
        status="approved",
        repayment_mode="single",
        created_at="2026-09-01T10:00:00",
        updated_at="2026-09-01T10:00:00",
    )
    rendu = json.loads(avance.model_dump_json())
    assert rendu["requested_amount"] == 300.0
    assert rendu["approved_amount"] == 250.5


def test_calcul_saisissable_en_nombre():
    calcul = SeizableAmountCalculation(
        employee_id="e",
        dependents_count=0,
        net_salary=Decimal("1738.49"),
        adjusted_salary=Decimal("1738.49"),
        seizable_amount=Decimal("46.49"),
        minimum_untouchable=Decimal("635.71"),
    )
    rendu = json.loads(calcul.model_dump_json())
    assert rendu["seizable_amount"] == 46.49


def test_la_validation_reste_decimale():
    saisie = SalarySeizure.model_construct(amount=Decimal("46.49"))
    assert isinstance(saisie.amount, Decimal)
