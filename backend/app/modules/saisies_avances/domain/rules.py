"""
Règles métier pures du domaine saisies et avances.

Aucune dépendance : pas de FastAPI, pas de DB, pas de services externes.
Comportement identique à services.saisies_avances_calculator pour les calculs purs.
"""
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Tuple


# Constantes métier (alignées domain/enums.py et legacy)
MAJORATION_PAR_CHARGE = Decimal("104.00")
MINIMUM_UNTOUCHABLE_DIVISOR = 20  # 1/20e du salaire net
MAX_ADVANCE_DAYS = 10


def calculate_seizable_amount(
    net_salary: Decimal, dependents_count: int = 0
) -> Decimal:
    """
    Calcule la quotité saisissable selon le barème légal français.

    Barème simplifié :
    - Tranche 1: 0 à 500€ → 0%
    - Tranche 2: 500 à 1000€ → 10%
    - Tranche 3: 1000 à 2000€ → 20%
    - Tranche 4: > 2000€ → 30%
    Le salarié doit conserver au minimum 1/20ème de son salaire net.
    """
    majoration = Decimal(dependents_count) * MAJORATION_PAR_CHARGE
    adjusted_salary = net_salary + majoration

    if adjusted_salary <= 500:
        seizable_amount = Decimal("0")
    elif adjusted_salary <= 1000:
        seizable_amount = (adjusted_salary - Decimal("500")) * Decimal("0.10")
    elif adjusted_salary <= 2000:
        seizable_amount = Decimal("50") + (
            (adjusted_salary - Decimal("1000")) * Decimal("0.20")
        )
    else:
        seizable_amount = Decimal("250") + (
            (adjusted_salary - Decimal("2000")) * Decimal("0.30")
        )

    minimum_untouchable = net_salary / Decimal(str(MINIMUM_UNTOUCHABLE_DIVISOR))
    max_seizable = net_salary - minimum_untouchable
    return max(Decimal("0"), min(seizable_amount, max_seizable))


def apply_priority_order(seizures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Trie les saisies par ordre de priorité légal (priority puis start_date).
    """
    return sorted(
        seizures,
        key=lambda s: (s.get("priority", 4), s.get("start_date", date.min)),
    )


def calculate_seizure_deduction(
    seizure: Dict[str, Any],
    net_salary: Decimal,
    seizable_amount: Decimal,
    dependents_count: int = 0,
) -> Decimal:
    """
    Calcule le montant à prélever pour une saisie selon son mode (fixe, pourcentage, barème_legal).
    """
    calculation_mode = seizure.get("calculation_mode", "barème_legal")

    if calculation_mode == "fixe":
        amount = Decimal(str(seizure.get("amount", 0)))
        return min(amount, seizable_amount)

    if calculation_mode == "pourcentage":
        percentage = Decimal(str(seizure.get("percentage", 0)))
        amount = net_salary * (percentage / Decimal("100"))
        return min(amount, seizable_amount)

    # barème_legal
    amount = Decimal(str(seizure.get("amount", 0)))
    if amount > 0:
        return min(amount, seizable_amount)
    return seizable_amount


def compute_advance_available_from_figures(
    daily_salary: Decimal,
    days_worked: Decimal,
    total_outstanding: Decimal,
    max_advance_days: int = MAX_ADVANCE_DAYS,
) -> Tuple[Decimal, Decimal]:
    """
    À partir des données déjà récupérées, calcule le montant disponible pour une avance.
    Retourne (available_amount, max_advance_amount_cap).
    """
    gross_available = daily_salary * days_worked
    available_amount = max(Decimal("0"), gross_available - total_outstanding)
    max_advance_amount = daily_salary * Decimal(str(max_advance_days))
    available_amount = min(available_amount, max_advance_amount)
    return available_amount, max_advance_amount


def initial_advance_status(
    is_employee_request: bool,
    requested_amount: Decimal,
    auto_approval_threshold: Decimal,
) -> str:
    """
    Détermine le statut initial d'une demande d'avance.
    - Employé qui demande pour lui-même : toujours 'pending'
    - RH/Admin : 'approved' si montant <= seuil, sinon 'pending'
    """
    if is_employee_request:
        return "pending"
    return "approved" if requested_amount <= auto_approval_threshold else "pending"


def remaining_to_pay_value(
    approved_amount: Decimal, total_paid: Decimal
) -> float:
    """
    Montant restant à verser à l'employé (pour affichage).
    """
    remaining = approved_amount - total_paid
    if approved_amount > 0 and total_paid >= approved_amount:
        return 0.0
    if approved_amount > 0:
        return float(max(Decimal("0"), remaining))
    return 0.0
