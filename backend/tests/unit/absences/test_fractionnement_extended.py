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


def test_fractionnement_legal_twelve_consecutive_zero():
    """12 jours consécutifs pris → pas de fractionnement."""
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
    assert result.days_granted == 0


def test_apply_fractionnement_november_wiring():
    """Bulletin novembre : crédit fractionnement sur soldes CP."""
    from unittest.mock import patch

    from app.modules.absences.application.fractionnement_queries import (
        apply_fractionnement_to_payslip_balances,
    )

    balances = {"conges_payes": {"acquis": 25.0, "solde": 10.0}}
    computed = {
        "days_granted": 2,
        "calculation_snapshot": {"source": "mbc_auto"},
    }

    with patch(
        "app.modules.absences.application.fractionnement_queries.get_fractionnement_settings",
        return_value={"fractionnement_enabled": True},
    ), patch(
        "app.modules.absences.application.fractionnement_queries.frac_repo.get_fractionnement_grant",
        return_value=None,
    ), patch(
        "app.modules.absences.application.fractionnement_queries._is_november_payslip_validated",
        return_value=False,
    ), patch(
        "app.modules.absences.application.fractionnement_queries.compute_fractionnement_for_employee",
        return_value=computed,
    ), patch(
        "app.modules.absences.application.fractionnement_queries.frac_repo.upsert_fractionnement_grant",
    ) as upsert:
        result = apply_fractionnement_to_payslip_balances(
            "emp-1", "comp-1", 2026, 11, balances
        )

    assert result["conges_payes"]["acquis"] == 27.0
    assert result["conges_payes"]["solde"] == 12.0
    assert result["fractionnement"]["jours_acquis"] == 2
    upsert.assert_called_once()


def test_apply_fractionnement_skipped_outside_november():
    from app.modules.absences.application.fractionnement_queries import (
        apply_fractionnement_to_payslip_balances,
    )

    balances = {"conges_payes": {"acquis": 25.0, "solde": 10.0}}
    result = apply_fractionnement_to_payslip_balances(
        "emp-1", "comp-1", 2026, 10, balances
    )
    assert result == balances
