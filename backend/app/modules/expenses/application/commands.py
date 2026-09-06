"""
Commands du module expenses (écritures).

Délèguent au repository ; préparation des données via infrastructure (mappers).
Comportement identique à l'ancien router.
"""

from app.core.logging import get_logger

from app.modules.expenses.application.dto import (
    CreateExpenseInput,
    UpdateExpenseInput,
    UpdateExpenseStatusInput,
)
from app.modules.expenses.domain.vat import (
    VAT_EXEMPT_EXPENSE_TYPES,
    taux_tva_effectif,
    validate_vat_rate,
)
from app.modules.expenses.infrastructure.mappers import (
    build_create_payload,
    build_update_payload,
)
from app.modules.expenses.infrastructure.repository import ExpenseRepository

logger = get_logger("modules.expenses.application.commands")


def create_expense(input: CreateExpenseInput) -> dict:
    """
    Crée une note de frais (statut initial et payload depuis domain + infrastructure).
    Comportement identique à create_expense_report du router legacy.
    """
    vat_error = validate_vat_rate(input.vat_rate)
    if vat_error:
        raise ValueError(vat_error)

    # Exonérations par type (IK…) : taux forcé côté serveur, le front n'est
    # pas la source de vérité.
    vat_rate = taux_tva_effectif(input.type, input.vat_rate)

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


def update_expense(
    input: UpdateExpenseInput, existing: dict | None = None
) -> dict | None:
    """Modifie les champs d'une note (RH). None si la note n'existe pas.

    `existing` : ligne déjà chargée par l'appelant (garde du router) pour
    éviter une seconde lecture.
    """
    repo = ExpenseRepository()
    if existing is None:
        existing = repo.get_by_id(input.expense_id)
    if existing is None:
        return None

    if input.vat_rate is not None:
        vat_error = validate_vat_rate(input.vat_rate)
        if vat_error:
            raise ValueError(vat_error)

    ancien_type = existing.get("type")
    type_effectif = input.type if input.type is not None else ancien_type
    # Quitter un type exonéré sans donner de taux garderait le 0 % forcé sur
    # un type qui ouvre droit à TVA : on exige un taux explicite.
    if (
        input.type is not None
        and input.type != ancien_type
        and ancien_type in VAT_EXEMPT_EXPENSE_TYPES
        and type_effectif not in VAT_EXEMPT_EXPENSE_TYPES
        and input.vat_rate is None
    ):
        raise ValueError(
            "Précisez le taux de TVA : l'ancien type était exonéré, le nouveau "
            "ne l'est pas."
        )
    # Même garde-fou qu'à la création — seulement quand un champ pertinent
    # bouge, pour laisser un PATCH « description seule » vraiment partiel.
    vat_rate = input.vat_rate
    if type_effectif in VAT_EXEMPT_EXPENSE_TYPES and (
        input.type is not None or input.vat_rate is not None
    ):
        vat_rate = 0.0

    payload = build_update_payload(
        existing,
        date_value=input.date,
        amount=input.amount,
        vat_rate=vat_rate,
        type_value=input.type,
        description=input.description,
        description_definie=input.description_definie,
    )
    if not payload:
        return existing
    return repo.update(input.expense_id, payload)


def delete_expense(expense_id: str, company_id: str | None = None) -> bool:
    """Supprime une note ET son justificatif. False si rien n'a été supprimé.

    `company_id` : garde d'isolation en profondeur — un appelant hors router
    ne peut pas supprimer la note d'une autre société.
    """
    repo = ExpenseRepository()
    existing = repo.get_by_id(expense_id)
    if not existing:
        return False
    if company_id and str(existing.get("company_id") or "") != str(company_id):
        return False
    if not repo.delete(expense_id):
        return False
    receipt = existing.get("receipt_url")
    if receipt:
        # Best-effort : la ligne est déjà supprimée, un échec de purge ne doit
        # pas faire échouer l'appel — mais il est journalisé.
        try:
            from app.modules.expenses.infrastructure.providers import (
                ExpenseStorageProvider,
            )

            ExpenseStorageProvider().remove([str(receipt)])
        except Exception:
            logger.exception(
                "[expenses] justificatif non purgé après suppression: %s", receipt
            )
    return True


def update_expense_status(input: UpdateExpenseStatusInput) -> dict | None:
    """
    Met à jour le statut (validated | rejected).
    Comportement identique à update_expense_status du router legacy.
    """
    repo = ExpenseRepository()
    return repo.update_status(input.expense_id, input.status)
