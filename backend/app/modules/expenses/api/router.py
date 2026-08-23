"""
Router API du module expenses.

Appelle uniquement la couche application (ExpenseApplicationService).
Aucune logique métier ni accès DB/storage ici. Comportement HTTP identique au legacy.
"""

import traceback
from typing import Annotated, List

from fastapi import APIRouter, Body, Depends, HTTPException

from app.core.security import get_current_user
from app.modules.access_control.application.service import access_control_service
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


def _require_my_employee_id(current_user: User) -> str:
    """employees.id pour création / upload (compte auth ≠ fiche si user_id renseigné)."""
    company_id = current_user.active_company_id
    if not company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active.")
    employee_id = _expense_service.resolve_employee_id_for_expense_account(
        str(current_user.id), company_id
    )
    if not employee_id:
        raise HTTPException(
            status_code=404,
            detail="Profil collaborateur sans employé associé.",
        )
    return employee_id


def _require_rh_or_admin(current_user: User) -> None:
    if current_user.is_platform_admin:
        return
    active_company_id = current_user.active_company_id
    if not active_company_id or not current_user.has_rh_access_in_company(active_company_id):
        raise HTTPException(
            status_code=403,
            detail="Accès réservé aux RH et administrateurs.",
        )


def _societe_active_ou_403(current_user: User) -> str:
    """Société active, sinon 403.

    Sans ce contrôle, `str(None)` partait en base et l'erreur SQL brute
    (« invalid input syntax for type uuid ») remontait au client en 500 —
    constaté en réel sur un compte administrateur sans société active.
    """
    company_id = current_user.active_company_id
    if not company_id:
        raise HTTPException(
            status_code=403, detail="Impossible de déterminer l'entreprise."
        )
    return str(company_id)


def _filter_expenses_in_scope(
    current_user: User, company_id: str, expenses: List[dict]
) -> List[dict]:
    """Ne conserve que les notes des salariés autorisés par le grant scoped."""
    if current_user.is_platform_admin:
        return expenses
    employee_ids = [
        str(exp.get("employee_id") or (exp.get("employees") or {}).get("id") or "")
        for exp in expenses
    ]
    allowed = set(
        access_control_service.filter_allowed_employee_ids(
            str(current_user.id), company_id, "expenses.view_all", employee_ids
        )
    )
    # Compatibilité des rôles RH historiques sans grants user_permissions.
    if not allowed and current_user.has_rh_access_in_company(company_id):
        return expenses
    return [
        exp
        for exp in expenses
        if str(exp.get("employee_id") or (exp.get("employees") or {}).get("id") or "")
        in allowed
    ]


@router.post("/get-upload-url", response_model=SignedUploadUrlResponse)
async def get_upload_url(
    filename: Annotated[str, Body(embed=True)],
    current_user: User = Depends(get_current_user),
):
    """Génère une URL signée pour uploader un justificatif avec son nom original."""
    try:
        employee_id = _require_my_employee_id(current_user)
        return _expense_service.get_signed_upload_url(employee_id, filename)
    except HTTPException:
        raise
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
        employee_id = _require_my_employee_id(current_user)
        input_ = CreateExpenseInput(
            employee_id=employee_id,
            date=expense_data.date,
            amount=expense_data.amount,
            vat_rate=expense_data.vat_rate,
            type=expense_data.type,
            description=expense_data.description,
            receipt_url=expense_data.receipt_url,
            filename=expense_data.filename,
            company_id=current_user.active_company_id,
        )
        return _expense_service.create_expense(input_)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me", response_model=List[Expense])
async def get_my_expenses(current_user: User = Depends(get_current_user)):
    """Récupère toutes les notes de frais de l'employé connecté, avec les URLs des justificatifs."""
    try:
        return _expense_service.get_my_expenses_for_user_account(
            str(current_user.id), current_user.active_company_id
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[ExpenseWithEmployee])
async def get_all_expenses(
    status: ExpenseStatus | None = None,
    current_user: User = Depends(get_current_user),
):
    """(Pour les RH) Récupère toutes les notes de frais, avec détails de l'employé."""
    try:
        _require_rh_or_admin(current_user)
        company_id = _societe_active_ou_403(current_user)
        expenses = _expense_service.get_all_expenses(
            company_id, ListExpensesInput(status=status)
        )
        return _filter_expenses_in_scope(current_user, company_id, expenses)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/receipt-url")
async def get_receipt_signed_url(
    path: str,
    current_user: User = Depends(get_current_user),
):
    """URL signée d'un justificatif (écran RH).

    Remplace l'URL publique que le frontend fabriquait lui-même : le bucket
    `expense_receipts` peut ainsi redevenir privé (audit sécurité 23/08/2026).
    """
    _require_rh_or_admin(current_user)

    # Le chemin vient du client : on refuse tout ce qui sort du bucket.
    chemin = (path or "").strip()
    if not chemin or chemin.startswith("/") or ".." in chemin:
        raise HTTPException(status_code=400, detail="Chemin de justificatif invalide.")

    try:
        url = _expense_service.get_receipt_signed_url(chemin)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    if not url:
        raise HTTPException(status_code=404, detail="Justificatif introuvable.")
    return {"url": url}


@router.patch("/{expense_id}/status", response_model=Expense)
async def update_expense_status(
    expense_id: str,
    status_update: ExpenseStatusUpdateRequest,
    current_user: User = Depends(get_current_user),
):
    """(Pour les RH) Valide ou rejette une note de frais."""
    try:
        _require_rh_or_admin(current_user)
        company_id = _societe_active_ou_403(current_user)
        expense = _expense_service.get_all_expenses(
            company_id, ListExpensesInput()
        )
        target = next((item for item in expense if str(item.get("id")) == expense_id), None)
        if not target:
            raise HTTPException(status_code=404, detail="Note de frais non trouvée.")
        employee_id = str(
            target.get("employee_id") or (target.get("employees") or {}).get("id") or ""
        )
        access_control_service.require_employee_access(
            current_user, company_id, "expenses.approve", employee_id
        )
        result = _expense_service.update_expense_status(
            UpdateExpenseStatusInput(expense_id=expense_id, status=status_update.status)
        )
        if result is None:
            raise HTTPException(status_code=404, detail="Note de frais non trouvée.")
        return result
    except HTTPException:
        raise
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
