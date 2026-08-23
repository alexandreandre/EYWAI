"""
Commandes (cas d'usage écriture) du module monthly_inputs.

Délégation au repository. Comportement identique à api/routers/monthly_inputs.py.
"""

from __future__ import annotations
from app.core.logging import get_logger, log_app_debug

logger = get_logger("modules.monthly_inputs.application.commands")

from typing import List

from app.modules.monthly_inputs.application.dto import (
    CreateBatchResultDto,
    CreateSingleResultDto,
)
from app.modules.monthly_inputs.infrastructure.repository import (
    monthly_inputs_repository,
)
from app.modules.monthly_inputs.schemas.requests import (
    MonthlyInput,
    MonthlyInputCreate,
    MonthlyInputUpdate,
)


def update_monthly_input(
    input_id: str, payload: MonthlyInputUpdate, company_id: str
) -> dict:
    """Applique une correction manuelle et marque la ligne comme telle.

    `manual_override` protège la ligne de la génération mensuelle suivante :
    la RH a tranché pour ce mois, le générateur ne repasse pas derrière elle.
    """
    changes = payload.model_dump(exclude_none=True)
    if not changes:
        raise ValueError("Aucun champ à mettre à jour.")
    changes["manual_override"] = True
    row = monthly_inputs_repository.update_by_id(input_id, changes, company_id)
    if row is None:
        raise ValueError(f"Saisie {input_id} introuvable.")
    return row


def create_monthly_inputs_batch(
    payload: List[MonthlyInput],
    company_id: str,
) -> CreateBatchResultDto:
    """
    Crée une ou plusieurs saisies mensuelles.
    payload : liste de modèles Pydantic (MonthlyInput) avec model_dump(mode='json', exclude_none=True).
    """
    # company_id imposé par la session, jamais lu dans le corps de requête.
    data_to_insert = [
        {**item.model_dump(mode="json", exclude_none=True), "company_id": str(company_id)}
        for item in payload
    ]
    # Debug conservé pour compatibilité (à retirer en phase de nettoyage)
    if data_to_insert:
        log_app_debug(logger, f'\n[monthly_inputs] Insert batch: {len(data_to_insert)} row(s)')
    inserted = monthly_inputs_repository.insert_batch(data_to_insert)
    return CreateBatchResultDto(
        inserted_count=len(inserted),
        inserted_ids=[str(r["id"]) for r in inserted if r.get("id")],
    )


def create_employee_monthly_input(
    employee_id: str,
    prime_data: MonthlyInputCreate,
    company_id: str,
) -> CreateSingleResultDto:
    """
    Crée une saisie pour un employé (employee_id injecté).
    prime_data : modèle MonthlyInputCreate, à convertir en dict + employee_id.
    """
    data_to_insert = prime_data.model_dump()
    data_to_insert["employee_id"] = employee_id
    data_to_insert["company_id"] = str(company_id)
    inserted = monthly_inputs_repository.insert_one(data_to_insert)
    return CreateSingleResultDto(inserted_data=inserted)


def delete_monthly_input(input_id: str, company_id: str) -> None:
    """Supprime une saisie par id, dans la société de l'appelant."""
    monthly_inputs_repository.delete_by_id(input_id, company_id)


def delete_employee_monthly_input(
    employee_id: str, input_id: str, company_id: str
) -> None:
    """Supprime une saisie d'un salarié, dans la société de l'appelant."""
    monthly_inputs_repository.delete_by_id_and_employee(
        input_id, employee_id, company_id
    )
