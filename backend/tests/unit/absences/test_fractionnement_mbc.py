"""Tests fractionnement CP — formule Excel MBC."""

import pytest

from app.modules.absences.domain.fractionnement import (
    FractionnementMbcInput,
    compute_fractionnement_days_mbc,
)

# Données Excel MBC (solde N-1, report juin, attendu plafonné)
MBC_CASES = [
    ("BOUSSANOUNE", 36, 28, 1),
    ("CVITKOVIC", 29, 19, 2),
    ("FANOVO", 23.5, 6.5, 2),
    ("GAUDEY", 17.5, 6.5, 2),
    ("MOHAMED", 12, 0, 2),
    ("PORRAL", 16, 5, 2),
    ("SCHARFF", 14, 0, 2),
    ("SERE", 7.5, 0, 1),
]


@pytest.mark.parametrize(
    "name,solde_n1,report_juin,expected_days",
    MBC_CASES,
    ids=[c[0] for c in MBC_CASES],
)
def test_fractionnement_mbc_excel_rows(name, solde_n1, report_juin, expected_days):
    result = compute_fractionnement_days_mbc(
        FractionnementMbcInput(
            solde_cp_n1_ouvres=solde_n1,
            cp_reported_june_ouvres=report_juin,
            fifth_week_deduction_ouvres=5,
            ouvres_to_ouvrables_ratio=1.2,
        )
    )
    assert result.days_granted == expected_days


def test_fractionnement_cp_anciennete_deduction():
    """Retrait CP ancienneté réduit le solde et peut changer le nombre de jours."""
    without = compute_fractionnement_days_mbc(
        FractionnementMbcInput(
            solde_cp_n1_ouvres=11,
            cp_reported_june_ouvres=0,
            cp_seniority_deduction_ouvres=0,
        )
    )
    with_seniority = compute_fractionnement_days_mbc(
        FractionnementMbcInput(
            solde_cp_n1_ouvres=11,
            cp_reported_june_ouvres=0,
            cp_seniority_deduction_ouvres=2,
        )
    )
    assert without.solde_ouvres == 6.0
    assert without.solde_ouvrables == 7.2
    assert without.days_granted == 2
    assert with_seniority.solde_ouvres == 4.0
    assert with_seniority.solde_ouvrables == 4.8
    assert with_seniority.days_granted == 1


def test_fractionnement_zero_below_three_ouvrables():
    result = compute_fractionnement_days_mbc(
        FractionnementMbcInput(solde_cp_n1_ouvres=6, cp_reported_june_ouvres=0)
    )
    # 6 - 5 = 1 ouvré → 1.2 ouvrables → 0 jour
    assert result.days_granted == 0
