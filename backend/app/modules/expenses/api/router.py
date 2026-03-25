"""
Router API du module expenses.

Appelle uniquement la couche application (ExpenseApplicationService).
Aucune logique métier ni accès DB/storage ici. Comportement HTTP identique au legacy.
"""

import traceback
from typing import Annotated, List

from fastapi import APIRouter, Body, Depends, HTTPException

from app.core.security import get_current_user
from app.modules.users.schemas.responses import User

from app.modules.expenses.application.dto import (
    CreateExpenseInput,
    ListExpensesInput,
    UpdateExpenseStatusInput,
)
from app.modules.expenses.application.service import ExpenseApplicationService
from app.modules.expenses.schemas.requests import (
    ExpenseBase,
    ExpenseStatus,
    ExpenseStatusUpdateRequest,
)
from app.modules.expenses.schemas.responses import (
    Expense,
    ExpenseWithEmployee,
    SignedUploadUrlResponse,
)

router = APIRouter(prefix="/api/expenses", tags=["Expenses"])

_expense_service = ExpenseApplicationService()


@router.post("/get-upload-url", response_model=SignedUploadUrlResponse)
async def get_upload_url(
    filename: Annotated[str, Body(embed=True)],
    current_user: User = Depends(get_current_user),
):
    """Génère une URL signée pour uploader un justificatif avec son nom original."""
    try:
        return _expense_service.get_signed_upload_url(current_user.id, filename)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur de stockage Supabase: {e}")


@router.post("/", response_model=Expense, status_code=201)
async def create_expense_report(
    expense_data: ExpenseBase,
    current_user: User = Depends(get_current_user),
):
    """Crée une nouvelle note de frais pour l'utilisateur connecté."""
    try:
        input_ = CreateExpenseInput(
            employee_id=current_user.id,
            date=expense_data.date,
            amount=expense_data.amount,
            type=expense_data.type,
            description=expense_data.description,
            receipt_url=expense_data.receipt_url,
            filename=expense_data.filename,
        )
        return _expense_service.create_expense(input_)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me", response_model=List[Expense])
async def get_my_expenses(current_user: User = Depends(get_current_user)):
    """Récupère toutes les notes de frais de l'employé connecté, avec les URLs des justificatifs."""
    try:
        return _expense_service.get_my_expenses(current_user.id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[ExpenseWithEmployee])
async def get_all_expenses(
    status: ExpenseStatus | None = None,
    current_user: User = Depends(get_current_user),
):
    """(Pour les RH) Récupère toutes les notes de frais, avec détails de l'employé."""
    try:
        return _expense_service.get_all_expenses(ListExpensesInput(status=status))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{expense_id}/status", response_model=Expense)
async def update_expense_status(
    expense_id: str,
    status_update: ExpenseStatusUpdateRequest,
    current_user: User = Depends(get_current_user),
):
    """(Pour les RH) Valide ou rejette une note de frais."""
    try:
        result = _expense_service.update_expense_status(
            UpdateExpenseStatusInput(expense_id=expense_id, status=status_update.status)
        )
        if result is None:
            raise HTTPException(status_code=404, detail="Note de frais non trouvée.")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
