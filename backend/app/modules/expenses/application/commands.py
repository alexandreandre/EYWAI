"""
Commands du module expenses (écritures).

Délèguent au repository ; préparation des données via infrastructure (mappers).
Comportement identique à l'ancien router.
"""

from app.modules.expenses.application.dto import (
    CreateExpenseInput,
    UpdateExpenseInput,
    UpdateExpenseStatusInput,
)
from app.modules.expenses.domain.enums import ExpenseType
from app.modules.expenses.domain.vat import validate_vat_rate
from app.modules.expenses.infrastructure.mappers import (
    build_create_payload,
    build_update_payload,
)
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


def update_expense(input: UpdateExpenseInput) -> dict | None:
    """Modifie les champs d'une note (RH). None si la note n'existe pas."""
    repo = ExpenseRepository()
    existing = repo.get_by_id(input.expense_id)
    if existing is None:
        return None

    if input.vat_rate is not None:
        vat_error = validate_vat_rate(input.vat_rate)
        if vat_error:
            raise ValueError(vat_error)

    # Même garde-fou qu'à la création : les IK sont hors champ de la TVA.
    vat_rate = input.vat_rate
    type_effectif = input.type or existing.get("type")
    if type_effectif == ExpenseType.INDEMNITES_KM.value:
        vat_rate = 0.0

    payload = build_update_payload(
        existing,
        date_value=input.date,
        amount=input.amount,
        vat_rate=vat_rate,
        type_value=input.type,
        description=input.description,
    )
    return repo.update(input.expense_id, payload)


def delete_expense(expense_id: str) -> bool:
    """Supprime une note de frais. False si rien n'a été supprimé."""
    return ExpenseRepository().delete(expense_id)


def update_expense_status(input: UpdateExpenseStatusInput) -> dict | None:
    """
    Met à jour le statut (validated | rejected).
    Comportement identique à update_expense_status du router legacy.
    """
    repo = ExpenseRepository()
    return repo.update_status(input.expense_id, input.status)
