"""
Règles métier pures — prêts employeur.

Aucune dépendance FastAPI / Supabase.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Iterable, List

from app.modules.employee_loans.domain.constants import DECLARATION_2062_THRESHOLD_EUR


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def requires_2062(principal: Decimal) -> bool:
    """Prêt ≥ 5 000 € : déclaration formulaire 2062."""
    return principal >= DECLARATION_2062_THRESHOLD_EUR


def compute_monthly_payment(
    principal: Decimal, annual_rate: Decimal, duration_months: int
) -> Decimal:
    """Mensualité constante (amortissement français)."""
    if duration_months <= 0:
        raise ValueError("La durée doit être d'au moins 1 mois.")
    if principal <= 0:
        raise ValueError("Le capital doit être strictement positif.")
    if annual_rate <= 0:
        return _money(principal / Decimal(duration_months))

    monthly_rate = annual_rate / Decimal("12")
    factor = (Decimal("1") + monthly_rate) ** duration_months
    payment = principal * monthly_rate * factor / (factor - Decimal("1"))
    return _money(payment)


@dataclass(frozen=True)
class AmortizationLine:
    installment_number: int
    year: int
    month: int
    capital_part: Decimal
    interest_part: Decimal
    total_due: Decimal
    remaining_capital: Decimal


def _add_months(start: date, offset: int) -> tuple[int, int]:
    total = (start.year * 12 + (start.month - 1)) + offset
    return total // 12, (total % 12) + 1


def build_amortization_schedule(
    principal: Decimal,
    annual_rate: Decimal,
    duration_months: int,
    start_date: date,
) -> tuple[Decimal, List[AmortizationLine]]:
    """Construit l'échéancier d'amortissement prévisionnel."""
    monthly_payment = compute_monthly_payment(principal, annual_rate, duration_months)
    remaining = principal
    monthly_rate = annual_rate / Decimal("12") if annual_rate > 0 else Decimal("0")
    lines: List[AmortizationLine] = []

    for i in range(duration_months):
        year, month = _add_months(start_date, i)
        if monthly_rate > 0:
            interest_part = _money(remaining * monthly_rate)
            capital_part = _money(min(remaining, monthly_payment - interest_part))
            if i == duration_months - 1:
                capital_part = _money(remaining)
                total_due = _money(capital_part + interest_part)
            else:
                total_due = monthly_payment
        else:
            interest_part = Decimal("0.00")
            capital_part = _money(
                remaining if i == duration_months - 1 else principal / Decimal(duration_months)
            )
            total_due = capital_part

        remaining = _money(max(Decimal("0"), remaining - capital_part))
        lines.append(
            AmortizationLine(
                installment_number=i + 1,
                year=year,
                month=month,
                capital_part=capital_part,
                interest_part=interest_part,
                total_due=total_due,
                remaining_capital=remaining,
            )
        )

    return monthly_payment, lines


def compute_interest_benefit_in_kind(
    remaining_capital: Decimal,
    legal_annual_rate: Decimal,
    actual_annual_rate: Decimal,
) -> Decimal:
    """
    Avantage en nature mensuel = intérêts au taux légal − intérêts réellement facturés.
    """
    if remaining_capital <= 0:
        return Decimal("0.00")
    legal_monthly = remaining_capital * legal_annual_rate / Decimal("12")
    actual_monthly = remaining_capital * actual_annual_rate / Decimal("12")
    benefit = legal_monthly - actual_monthly
    return _money(max(Decimal("0"), benefit))


def capital_du_au_debut_du_mois(
    loan: Dict[str, Any],
    capital_repayments: Iterable[Dict[str, Any]],
    year: int,
    month: int,
) -> Decimal:
    """Capital restant dû au début du mois (`year`, `month`).

    Nul avant le mois du premier versement du prêt (sa date de début). Sinon le
    prêt moins le capital remboursé les mois d'avant : l'échéance prélevée sur
    le bulletin du mois ne baisse pas le capital de ce mois, et un mois
    régénéré après son prélèvement garde son capital.
    """
    debut = date.fromisoformat(str(loan.get("start_date"))[:10])
    if (year, month) < (debut.year, debut.month):
        return Decimal("0")
    rembourse = sum(
        (
            Decimal(str(r.get("capital_amount") or 0))
            for r in capital_repayments
            if (int(r["year"]), int(r["month"])) < (year, month)
        ),
        Decimal("0"),
    )
    capital = Decimal(str(loan.get("principal_amount") or 0)) - rembourse
    return _money(max(Decimal("0"), capital))


#: Art. L3251-3 du Code du travail : la retenue pour une avance en espèces
#: (le prêt de l'employeur y est assimilé) ne dépasse pas le dixième du salaire exigible.
LOAN_REPAYMENT_SALARY_FRACTION = Decimal("0.10")


def compute_loan_repayment_cap(
    salaire_exigible: Decimal,
    net_disponible: Decimal,
) -> Decimal:
    """Plafond de retenue du mois : dixième du salaire exigible (art. L3251-3),
    sans jamais dépasser le net encore disponible (le net ne devient pas négatif)."""
    dixieme = salaire_exigible * LOAN_REPAYMENT_SALARY_FRACTION
    return _money(max(Decimal("0"), min(dixieme, net_disponible)))


def _euros_fr(montant: Decimal) -> str:
    texte = f"{abs(montant):,.2f}".replace(",", " ").replace(".", ",")
    return f"{'−' if montant < 0 else ''}{texte} €"


def message_pret_retenu_en_partie(
    *,
    motif: str | None,
    numero: Any,
    capital_retenu: Decimal,
    interets_retenus: Decimal,
    prevu: Decimal,
    reliquat: Decimal,
    salaire_exigible: Decimal,
    net_disponible: Decimal,
    plafond_restant: Decimal,
) -> str:
    """Ce que dit le bulletin d'une échéance de prêt retenue en partie : combien,
    sur combien, la règle appliquée et ce que devient le reliquat.

    La règle est celle du code, dite telle quelle : le capital retenu est
    limité au dixième du salaire exigible (L3251-3) et au net encore
    disponible ; les intérêts suivent au prorata du capital retenu ; l'échéance
    non soldée est reprise seule au bulletin suivant (une échéance par prêt et
    par bulletin), ce qui fait glisser les suivantes d'un mois.
    """
    qui = f"Prêt employeur ({motif})" if motif else "Prêt employeur"
    retenu = capital_retenu + interets_retenus
    debut = (
        f"{qui} : {_euros_fr(retenu)} retenus sur {_euros_fr(prevu)} prévus "
        f"pour l'échéance n° {numero}."
    )
    dixieme = _money(salaire_exigible * LOAN_REPAYMENT_SALARY_FRACTION)
    if net_disponible <= 0:
        raison = "Le net à payer du mois ne permet pas de retenue."
    elif plafond_restant <= 0:
        raison = (
            "Le dixième du salaire exigible (article L3251-3 du Code du travail), "
            f"{_euros_fr(dixieme)}, est déjà retenu pour un autre prêt."
        )
    elif net_disponible < dixieme:
        raison = "Le net à payer du mois ne permet pas plus."
    else:
        part = (
            f"le dixième de {_euros_fr(salaire_exigible)}"
            if plafond_restant >= dixieme
            else f"ce qui reste du dixième de {_euros_fr(salaire_exigible)} après un autre prêt"
        )
        raison = (
            "La retenue est limitée au dixième du salaire exigible (article L3251-3 "
            f"du Code du travail) : {_euros_fr(capital_retenu)} de capital ({part})"
        )
        if interets_retenus > 0:
            raison += f", plus {_euros_fr(interets_retenus)} d'intérêts au prorata"
        raison += "."
    fin = (
        f"Le reliquat de {_euros_fr(reliquat)} reste dû sur l'échéance n° {numero} : "
        "il sera retenu seul sur le bulletin suivant, et les échéances suivantes "
        "glissent d'un mois."
    )
    return f"{debut} {raison} {fin}"


def compute_repayment_amount(
    due_capital: Decimal,
    remaining_seizable: Decimal,
    remaining_capital: Decimal | None = None,
) -> Decimal:
    """Montant de capital effectivement prélevé ce mois."""
    if due_capital <= 0 or remaining_seizable <= 0:
        return Decimal("0.00")
    amount = min(due_capital, remaining_seizable)
    if remaining_capital is not None:
        amount = min(amount, remaining_capital)
    return _money(amount)


def compute_interest_paid(
    due_capital: Decimal,
    due_interest: Decimal,
    capital_paid: Decimal,
) -> Decimal:
    """Intérêts prélevés, proportionnels au capital remboursé si partiel."""
    if capital_paid <= 0 or due_interest <= 0:
        return Decimal("0.00")
    if due_capital <= 0 or capital_paid >= due_capital:
        return due_interest
    ratio = capital_paid / due_capital
    return _money(due_interest * ratio)


def compute_installment_remaining(
    capital_part: Decimal,
    interest_part: Decimal,
    capital_paid: Decimal,
    interest_paid: Decimal,
) -> tuple[Decimal, Decimal]:
    """Reliquat capital et intérêts restants sur une échéance."""
    remaining_capital = _money(max(Decimal("0"), capital_part - capital_paid))
    remaining_interest = _money(max(Decimal("0"), interest_part - interest_paid))
    return remaining_capital, remaining_interest


def is_installment_collectible(
    inst_year: int,
    inst_month: int,
    payslip_year: int,
    payslip_month: int,
) -> bool:
    """True si la période bulletin permet de prélever cette échéance."""
    return (inst_year, inst_month) <= (payslip_year, payslip_month)


def is_installment_settled(
    capital_part: Decimal,
    interest_part: Decimal,
    capital_paid_total: Decimal,
    interest_paid_total: Decimal,
) -> bool:
    """True si l'échéance est entièrement soldée (cumuls)."""
    return (
        capital_paid_total >= capital_part and interest_paid_total >= interest_part
    )


def is_installment_fully_paid(
    due_capital: Decimal,
    due_interest: Decimal,
    capital_paid: Decimal,
    interest_paid: Decimal,
    remaining_after: Decimal,
) -> bool:
    """True si l'échéance du mois est entièrement soldée (prélèvement unique)."""
    if remaining_after <= 0:
        return True
    return capital_paid >= due_capital and interest_paid >= due_interest
