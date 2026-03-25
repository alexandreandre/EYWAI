"""
Commands du module expenses (écritures).

Délèguent au repository ; préparation des données via infrastructure (mappers).
Comportement identique à l'ancien router.
"""

from app.modules.expenses.application.dto import (
    CreateExpenseInput,
    UpdateExpenseStatusInput,
)
from app.modules.expenses.infrastructure.mappers import build_create_payload
from app.modules.expenses.infrastructure.repository import ExpenseRepository


def create_expense(input: CreateExpenseInput) -> dict:
    """
    Crée une note de frais (statut initial et payload depuis domain + infrastructure).
    Comportement identique à create_expense_report du router legacy.
    """
    repo = ExpenseRepository()
    db_data = build_create_payload(
        employee_id=input.employee_id,
        date_value=input.date,
        amount=input.amount,
        type_value=input.type,
        description=input.description,
        receipt_url=input.receipt_url,
        filename=input.filename,
    )
    return repo.create(db_data)


def update_expense_status(input: UpdateExpenseStatusInput) -> dict | None:
    """
    Met à jour le statut (validated | rejected).
    Comportement identique à update_expense_status du router legacy.
    """
    repo = ExpenseRepository()
    return repo.update_status(input.expense_id, input.status)
