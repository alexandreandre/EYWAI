"""
Commands du module expenses (écritures).

Délèguent au repository ; préparation des données via infrastructure (mappers).
Comportement identique à l'ancien router.
"""

from app.modules.expenses.application.dto import (
    CreateExpenseInput,
    UpdateExpenseStatusInput,
)
from app.modules.expenses.domain.enums import ExpenseType
from app.modules.expenses.domain.vat import validate_vat_rate
from app.modules.expenses.infrastructure.mappers import build_create_payload
from app.modules.expenses.infrastructure.repository import ExpenseRepository


def create_expense(input: CreateExpenseInput) -> dict:
    """
    Crée une note de frais (statut initial et payload depuis domain + infrastructure).
    Comportement identique à create_expense_report du router legacy.
    """
    vat_error = validate_vat_rate(input.vat_rate)
    if vat_error:
        raise ValueError(vat_error)

    # Les indemnités kilométriques (barème) sont hors champ de la TVA : taux
    # forcé côté serveur, le front n'est pas la source de vérité.
    vat_rate = (
        0.0 if input.type == ExpenseType.INDEMNITES_KM.value else input.vat_rate
    )

    repo = ExpenseRepository()
    db_data = build_create_payload(
        employee_id=input.employee_id,
        date_value=input.date,
        amount=input.amount,
        vat_rate=vat_rate,
        type_value=input.type,
        description=input.description,
        receipt_url=input.receipt_url,
        filename=input.filename,
        company_id=input.company_id,
        initial_status=input.initial_status,
    )
    return repo.create(db_data)


def update_expense_status(input: UpdateExpenseStatusInput) -> dict | None:
    """
    Met à jour le statut (validated | rejected).
    Comportement identique à update_expense_status du router legacy.
    """
    repo = ExpenseRepository()
    return repo.update_status(input.expense_id, input.status)
