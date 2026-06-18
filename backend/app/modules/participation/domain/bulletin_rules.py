"""
Règles métier — bulletin d'option participation / intéressement.

CSG sur participation, répartition choix salarié, flags paie.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal, Tuple

ChoiceType = Literal["full_cash", "partial_cash", "full_pee"]

CSG_TOTAL_RATE = Decimal("0.097")
CSG_DEDUCTIBLE_RATE = Decimal("0.068")
CSG_NON_DEDUCTIBLE_RATE = Decimal("0.029")

DEFAULT_CLAUSE_15J = (
    "À défaut de réponse dans les 15 jours de la remise du présent document, "
    "ou de choix incomplet, illisible ou erroné, le montant de votre participation "
    "sera investi sur le PEE."
)


def _round_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute_participation_csg(gross: float | Decimal) -> Tuple[Decimal, Decimal, Decimal]:
    """Retourne (csg_non_deductible, csg_deductible, total_csg)."""
    brut = Decimal(str(gross))
    if brut <= 0:
        return Decimal("0"), Decimal("0"), Decimal("0")
    non_ded = _round_money(brut * CSG_NON_DEDUCTIBLE_RATE)
    ded = _round_money(brut * CSG_DEDUCTIBLE_RATE)
    total = _round_money(non_ded + ded)
    return non_ded, ded, total


def compute_net_after_advances(
    gross: float | Decimal,
    advance_amount: float | Decimal = 0,
) -> Tuple[Decimal, Decimal, Decimal, Decimal]:
    """
    Calcule CSG et net à payer après acompte.
    Retourne (csg_non_deductible, csg_deductible, net_before_advance, net_final).
    """
    brut = Decimal(str(gross))
    advance = Decimal(str(advance_amount or 0))
    non_ded, ded, _ = compute_participation_csg(brut)
    net_before = _round_money(brut - non_ded - ded)
    net_final = _round_money(net_before - advance)
    return non_ded, ded, net_before, net_final


@dataclass(frozen=True)
class ChoiceSplit:
    cash_amount: Decimal
    pee_amount: Decimal


def split_amount_by_choice(
    choice: ChoiceType,
    net_amount: float | Decimal,
    cash_amount: float | Decimal | None = None,
) -> ChoiceSplit:
    """Répartit le net entre numéraire et PEE selon le choix salarié."""
    net = _round_money(Decimal(str(net_amount)))
    if net <= 0:
        return ChoiceSplit(cash_amount=Decimal("0"), pee_amount=Decimal("0"))

    if choice == "full_cash":
        return ChoiceSplit(cash_amount=net, pee_amount=Decimal("0"))
    if choice == "full_pee":
        return ChoiceSplit(cash_amount=Decimal("0"), pee_amount=net)

    # partial_cash
    cash = _round_money(Decimal(str(cash_amount or 0)))
    if cash < 0:
        cash = Decimal("0")
    if cash > net:
        cash = net
    pee = _round_money(net - cash)
    return ChoiceSplit(cash_amount=cash, pee_amount=pee)


def payroll_flags_for_amount(
    is_cash: bool,
) -> Tuple[bool, bool]:
    """
    Retourne (is_socially_taxed, is_taxable) pour une ligne monthly_input.
    Numéraire : soumis cotisations + impôt. PEE : exonéré.
    """
    if is_cash:
        return True, True
    return False, False


def dispositif_label(dispositif_type: str) -> str:
    if dispositif_type == "interessement":
        return "Intéressement"
    return "Participation"


def document_type_for_dispositif(dispositif_type: str) -> str:
    if dispositif_type == "interessement":
        return "bulletin_interessement"
    return "bulletin_participation"
