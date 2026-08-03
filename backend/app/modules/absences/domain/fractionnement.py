"""Règles fractionnement CP — formule MBC."""

from __future__ import annotations

from dataclasses import dataclass


OUVRES_TO_OUVRABLES_DEFAULT = 1.2
FIFTH_WEEK_DEDUCTION_OUVRES_DEFAULT = 5.0


@dataclass(frozen=True)
class FractionnementMbcInput:
    solde_cp_n1_ouvres: float
    cp_reported_june_ouvres: float = 0.0
    cp_seniority_deduction_ouvres: float = 0.0
    fifth_week_deduction_ouvres: float = FIFTH_WEEK_DEDUCTION_OUVRES_DEFAULT
    ouvres_to_ouvrables_ratio: float = OUVRES_TO_OUVRABLES_DEFAULT


@dataclass(frozen=True)
class FractionnementMbcResult:
    solde_ouvres: float
    solde_ouvrables: float
    days_granted: int
    one_day_column: int
    two_days_column: int


def ouvrables_to_ouvres(ouvrables: float, ratio: float = OUVRES_TO_OUVRABLES_DEFAULT) -> float:
    if ratio <= 0:
        return 0.0
    return round(float(ouvrables) / ratio, 2)


def compute_fractionnement_days_mbc(inp: FractionnementMbcInput) -> FractionnementMbcResult:
    """
    Formule Excel MBC :
    solde ouvrés = N-1 au 31/10 − 5ème semaine − report 1/06 − CP ancienneté
    solde ouvrables = solde ouvrés × 1,2
    3–5 ouvrables → 1 j ; ≥6 → 2 j ; <3 → 0
    """
    solde_ouvres = round(
        float(inp.solde_cp_n1_ouvres)
        - float(inp.fifth_week_deduction_ouvres)
        - float(inp.cp_reported_june_ouvres)
        - float(inp.cp_seniority_deduction_ouvres),
        2,
    )
    ratio = float(inp.ouvres_to_ouvrables_ratio) or OUVRES_TO_OUVRABLES_DEFAULT
    solde_ouvrables = round(max(0.0, solde_ouvres) * ratio, 2)

    # Le barème légal raisonne en jours entiers (3, 4 ou 5 → 1 j ; 6 et plus →
    # 2 j). La conversion ouvrés → ouvrables produit des décimales : borner la
    # première tranche à 5,0 laisserait ]5 ; 6[ sans droit, et un reliquat plus
    # élevé ouvrirait alors moins de droits qu'un reliquat plus faible.
    one_day = 1 if 3.0 <= solde_ouvrables < 6.0 else 0
    two_days = 2 if solde_ouvrables >= 6.0 else 0
    days_granted = min(2, max(one_day, two_days))

    return FractionnementMbcResult(
        solde_ouvres=solde_ouvres,
        solde_ouvrables=solde_ouvrables,
        days_granted=days_granted,
        one_day_column=one_day,
        two_days_column=two_days,
    )
