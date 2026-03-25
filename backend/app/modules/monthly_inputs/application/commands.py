"""
Commandes (cas d'usage écriture) du module monthly_inputs.

Délégation au repository. Comportement identique à api/routers/monthly_inputs.py.
"""

from __future__ import annotations

import sys
from typing import List

from app.modules.monthly_inputs.application.dto import (
    CreateBatchResultDto,
    CreateSingleResultDto,
)
from app.modules.monthly_inputs.infrastructure.repository import (
    monthly_inputs_repository,
)
from app.modules.monthly_inputs.schemas.requests import MonthlyInput, MonthlyInputCreate


def create_monthly_inputs_batch(
    payload: List[MonthlyInput],
) -> CreateBatchResultDto:
    """
    Crée une ou plusieurs saisies mensuelles.
    payload : liste de modèles Pydantic (MonthlyInput) avec model_dump(mode='json', exclude_none=True).
    """
    data_to_insert = [
        item.model_dump(mode="json", exclude_none=True) for item in payload
    ]
    # Debug conservé pour compatibilité (à retirer en phase de nettoyage)
    if data_to_insert:
        print(
            f"\n[monthly_inputs] Insert batch: {len(data_to_insert)} row(s)",
            file=sys.stderr,
        )
    inserted = monthly_inputs_repository.insert_batch(data_to_insert)
    return CreateBatchResultDto(inserted_count=len(inserted))


def create_employee_monthly_input(
    employee_id: str,
    prime_data: MonthlyInputCreate,
) -> CreateSingleResultDto:
    """
    Crée une saisie pour un employé (employee_id injecté).
    prime_data : modèle MonthlyInputCreate, à convertir en dict + employee_id.
    """
    data_to_insert = prime_data.model_dump()
    data_to_insert["employee_id"] = employee_id
    inserted = monthly_inputs_repository.insert_one(data_to_insert)
    return CreateSingleResultDto(inserted_data=inserted)


def delete_monthly_input(input_id: str) -> None:
    """Supprime une saisie par id."""
    monthly_inputs_repository.delete_by_id(input_id)


def delete_employee_monthly_input(employee_id: str, input_id: str) -> None:
    """Supprime une saisie pour un employé (id + employee_id)."""
    monthly_inputs_repository.delete_by_id_and_employee(input_id, employee_id)
