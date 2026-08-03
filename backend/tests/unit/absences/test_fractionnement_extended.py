"""Tests fractionnement légal."""

from app.modules.absences.domain.fractionnement import (
    FractionnementMbcInput,
    compute_fractionnement_days_mbc,
)
from app.modules.absences.domain.fractionnement_legal import (
    FractionnementLegalInput,
    compute_fractionnement_legal,
)


def test_fractionnement_mbc_regression_unchanged():
    result = compute_fractionnement_days_mbc(
        FractionnementMbcInput(
            solde_cp_n1_ouvres=11,
            cp_reported_june_ouvres=0,
            cp_seniority_deduction_ouvres=2,
        )
    )
    assert result.days_granted == 1


def test_fractionnement_legal_no_consecutive_block():
    """Peu de CP pris en période légale → fractionnement possible."""
    validated = [
        {
            "type": "conge_paye",
            "status": "validated",
            "selected_days": [f"2026-05-{d:02d}" for d in range(1, 6)],
        }
    ]
    result = compute_fractionnement_legal(
        FractionnementLegalInput(validated_requests=validated, grant_year=2026)
    )
    assert result.days_granted >= 0


def test_fractionnement_legal_twelve_consecutive_keeps_right():
    """
    12 jours consécutifs pris en période : le droit reste ouvert sur le
    reliquat (L3141-23 en fait la condition, pas une cause d'extinction).
    """
    days = [f"2026-07-{d:02d}" for d in range(1, 13)]
    validated = [
        {
            "type": "conge_paye",
            "status": "validated",
            "selected_days": days,
        }
    ]
    result = compute_fractionnement_legal(
        FractionnementLegalInput(validated_requests=validated, grant_year=2026)
    )
    assert result.days_granted == 2


def test_apply_fractionnement_november_wiring():
    """Bulletin novembre : crédit des jours validés sur les soldes CP.

    Le crédit vient d'un droit validé par les RH. Le cas d'un droit absent ou
    seulement calculé, et l'absence d'écriture en base, sont couverts par
    `test_fractionnement_reglages.py`.
    """
    from unittest.mock import patch

    from app.modules.absences.application.fractionnement_queries import (
        apply_fractionnement_to_payslip_balances,
    )

    balances = {"conges_payes": {"acquis": 25.0, "solde": 10.0}}
    grant = {
        "days_granted": 2,
        "status": "validated",
        "calculation_snapshot": {"source": "fractionnement_legal"},
    }

    with patch(
        "app.modules.absences.application.fractionnement_queries.get_fractionnement_settings",
        return_value={"fractionnement_enabled": True},
    ), patch(
        "app.modules.absences.application.fractionnement_queries.frac_repo.get_fractionnement_grant",
        return_value=grant,
    ):
        result = apply_fractionnement_to_payslip_balances(
            "emp-1", "comp-1", 2026, 11, balances
        )

    assert result["conges_payes"]["acquis"] == 27.0
    assert result["conges_payes"]["solde"] == 12.0
    assert result["fractionnement"]["jours_acquis"] == 2


def test_apply_fractionnement_skipped_outside_november():
    from app.modules.absences.application.fractionnement_queries import (
        apply_fractionnement_to_payslip_balances,
    )

    balances = {"conges_payes": {"acquis": 25.0, "solde": 10.0}}
    result = apply_fractionnement_to_payslip_balances(
        "emp-1", "comp-1", 2026, 10, balances
    )
    assert result == balances
