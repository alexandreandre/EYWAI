"""
Règles métier pures — prêts employeur.

Aucune dépendance FastAPI / Supabase.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
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


def compute_loan_repayment_cap(
    *,
    quotite_du_mois: Decimal,
    deja_pris: Decimal,
    net_disponible: Decimal,
) -> Decimal:
    """Plafond de retenue d'un prêt : ce qui reste de la quotité saisissable du
    mois une fois retenu ce qui en est déjà pris (saisies sur salaire, prêt
    précédent), sans jamais dépasser le net encore disponible (le net ne devient
    pas négatif).

    Un prêt signé à part du contrat de travail, pour une durée fixée, n'est pas
    une avance en espèces (le dixième de L3251-3 ne s'y applique pas) : il se
    compense dans la limite de la fraction saisissable du salaire (Cass. soc.,
    15 janvier 2014, n° 12-19.739)."""
    reste = quotite_du_mois - deja_pris
    return _money(max(Decimal("0"), min(reste, net_disponible)))


def retenue_dans_le_plafond(
    due_capital: Decimal,
    due_interest: Decimal,
    plafond: Decimal,
    remaining_capital: Decimal | None = None,
) -> tuple[Decimal, Decimal]:
    """Capital et intérêts retenus ensemble sous le plafond du mois, les intérêts
    au prorata du capital retenu. La part du capital est arrondie au centime
    inférieur : l'arrondi des intérêts ne fait jamais dépasser le plafond."""
    du = due_capital + due_interest
    if du > plafond and du > 0:
        part_capital = (plafond * due_capital / du).quantize(
            Decimal("0.01"), rounding=ROUND_DOWN
        )
    else:
        part_capital = plafond
    capital = compute_repayment_amount(due_capital, part_capital, remaining_capital)
    interets = compute_interest_paid(due_capital, due_interest, capital)
    return capital, min(interets, max(Decimal("0"), plafond - capital))


def _euros_fr(montant: Decimal) -> str:
    texte = f"{abs(montant):,.2f}".replace(",", " ").replace(".", ",")
    return f"{'−' if montant < 0 else ''}{texte} €"


def _qui_a_pris(pris_par_les_saisies: Decimal, pris_par_d_autres_prets: Decimal) -> str:
    if pris_par_les_saisies > 0 and pris_par_d_autres_prets > 0:
        return "les saisies sur salaire et un autre prêt"
    if pris_par_les_saisies > 0:
        return "les saisies sur salaire"
    return "un autre prêt"


def message_pret_retenu_en_partie(
    *,
    motif: str | None,
    numero: Any,
    capital_retenu: Decimal,
    interets_retenus: Decimal,
    prevu: Decimal,
    reliquat: Decimal,
    quotite_du_mois: Decimal | None,
    annee_bareme: int | None,
    pris_par_les_saisies: Decimal,
    quotite_restante: Decimal,
    net_disponible: Decimal,
) -> str:
    """Ce que dit le bulletin d'une échéance de prêt retenue en partie : combien,
    sur combien, la règle appliquée et ce que devient le reliquat.

    La règle est celle du code, dite telle quelle : capital et intérêts
    tiennent ensemble dans ce qui reste de la quotité saisissable du mois
    (`quotite_restante`, avant ce prêt) et dans le net encore disponible
    (`net_disponible`, avant ce prêt) ; les intérêts suivent au prorata du
    capital retenu ; l'échéance non soldée est reprise seule au bulletin
    suivant (une échéance par prêt et par bulletin), ce qui fait glisser les
    suivantes d'un mois.
    """
    qui = f"Prêt employeur ({motif})" if motif else "Prêt employeur"
    retenu = capital_retenu + interets_retenus
    debut = (
        f"{qui} : {_euros_fr(retenu)} retenus sur {_euros_fr(prevu)} prévus "
        f"pour l'échéance n° {numero}."
    )
    if quotite_du_mois is None:
        raison = (
            "Le barème de la quotité saisissable n'est pas chargé : rien n'est "
            "retenu. Contactez le support."
        )
    elif net_disponible <= 0:
        raison = "Le net à payer du mois ne permet pas de retenue."
    else:
        pris_ailleurs = max(
            Decimal("0"), quotite_du_mois - pris_par_les_saisies - quotite_restante
        )
        if quotite_restante <= 0:
            raison = (
                f"La quotité saisissable du mois, {_euros_fr(quotite_du_mois)}, limite "
                "de la retenue (article L3252-2 du Code du travail), est déjà prise par "
                f"{_qui_a_pris(pris_par_les_saisies, pris_ailleurs)}."
            )
        elif net_disponible < quotite_restante:
            raison = "Le net à payer du mois ne permet pas plus."
        else:
            raison = (
                "La retenue, intérêts compris, est limitée à la quotité saisissable "
                f"du mois ({_euros_fr(quotite_du_mois)}, barème {annee_bareme}, "
                "article L3252-2 du Code du travail)"
            )
            if quotite_restante < quotite_du_mois:
                raison += (
                    f", dont il restait {_euros_fr(quotite_restante)} après "
                    f"{_qui_a_pris(pris_par_les_saisies, pris_ailleurs)}"
                )
            raison += f" : {_euros_fr(capital_retenu)} de capital"
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
