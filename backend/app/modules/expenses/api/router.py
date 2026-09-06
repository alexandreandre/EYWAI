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
    UpdateExpenseInput,
    UpdateExpenseStatusInput,
)
from app.modules.expenses.application.service import ExpenseApplicationService
from app.modules.expenses.schemas.requests import (
    ExpenseBase,
    ExpenseStatus,
    ExpenseStatusUpdateRequest,
    ExpenseUpdateRequest,
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


def _is_rh(current_user: User) -> bool:
    company_id = current_user.active_company_id
    return current_user.is_platform_admin or (
        company_id is not None
        and current_user.has_rh_access_in_company(str(company_id))
    )


def _resolve_rh_target_employee(current_user: User, employee_id: str) -> str:
    """Valide qu'une saisie RH cible un salarié de l'entreprise active."""
    emp_company = _expense_service.get_employee_company_id(str(employee_id))
    if not emp_company:
        raise HTTPException(status_code=404, detail="Employé non trouvé.")
    company_id = current_user.active_company_id
    if (
        company_id
        and str(emp_company) != str(company_id)
        and not current_user.is_platform_admin
    ):
        raise HTTPException(
            status_code=403,
            detail="Cet employé n'appartient pas à l'entreprise active.",
        )
    return str(employee_id)


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
def get_upload_url(
    filename: Annotated[str, Body(embed=True)],
    employee_id: Annotated[str | None, Body(embed=True)] = None,
    current_user: User = Depends(get_current_user),
):
    """Génère une URL signée pour uploader un justificatif avec son nom original.

    `employee_id` est réservé aux RH : le justificatif est alors rangé sous le
    dossier du salarié cible.
    """
    try:
        if employee_id and _is_rh(current_user):
            target_id = _resolve_rh_target_employee(current_user, employee_id)
        else:
            target_id = _require_my_employee_id(current_user)
        return _expense_service.get_signed_upload_url(target_id, filename)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur de stockage Supabase: {e}")


@router.post("/", response_model=Expense, status_code=201)
def create_expense_report(
    expense_data: ExpenseBase,
    current_user: User = Depends(get_current_user),
):
    """Crée une note de frais.

    Collaborateur : pour lui-même, statut initial « pending ».
    RH avec `employee_id` : saisie directe pour un salarié de l'entreprise
    active, validée immédiatement (la RH enregistre un fait, pas une demande).
    """
    try:
        rh_saisie_directe = bool(expense_data.employee_id) and _is_rh(current_user)
        if rh_saisie_directe:
            employee_id = _resolve_rh_target_employee(
                current_user, str(expense_data.employee_id)
            )
        else:
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
            # Repli sur la société du salarié : une NDF sans company_id est
            # invisible de toutes les listes RH (filtre strict eq(company_id)).
            company_id=current_user.active_company_id
            or _expense_service.get_employee_company_id(employee_id),
            initial_status="validated" if rh_saisie_directe else None,
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
def get_my_expenses(current_user: User = Depends(get_current_user)):
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
def get_all_expenses(
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
def get_receipt_signed_url(
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


def _charger_note_rh(expense_id: str, current_user: User) -> tuple[str, dict]:
    """Garde commune des actions RH sur une note : rôle, société, périmètre.

    Retourne (company_id, ligne) — la ligne chargée sert aux commandes pour
    éviter une seconde lecture.
    """
    _require_rh_or_admin(current_user)
    company_id = _societe_active_ou_403(current_user)
    target = _expense_service.get_expense(expense_id)
    if not target or str(target.get("company_id") or "") != str(company_id):
        raise HTTPException(status_code=404, detail="Note de frais non trouvée.")
    access_control_service.require_employee_access(
        current_user, company_id, "expenses.approve", str(target["employee_id"])
    )
    return company_id, target


@router.patch("/{expense_id}", response_model=Expense)
def update_expense(
    expense_id: str,
    update: ExpenseUpdateRequest,
    current_user: User = Depends(get_current_user),
):
    """(Pour les RH) Modifie une note de frais — HT/TVA recalculés."""
    try:
        _company_id, target = _charger_note_rh(expense_id, current_user)
        result = _expense_service.update_expense(
            UpdateExpenseInput(
                expense_id=expense_id,
                date=update.date,
                amount=update.amount,
                vat_rate=update.vat_rate,
                type=update.type,
                description=update.description,
                # None explicite = effacer ; absent = inchangé.
                description_definie="description" in update.model_fields_set,
            ),
            existing=target,
        )
        if result is None:
            raise HTTPException(status_code=404, detail="Note de frais non trouvée.")
        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{expense_id}", status_code=204)
def delete_expense(
    expense_id: str,
    current_user: User = Depends(get_current_user),
):
    """(Pour les RH) Supprime une note de frais."""
    try:
        company_id, _target = _charger_note_rh(expense_id, current_user)
        if not _expense_service.delete_expense(expense_id, company_id=company_id):
            raise HTTPException(status_code=404, detail="Note de frais non trouvée.")
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{expense_id}/status", response_model=Expense)
def update_expense_status(
    expense_id: str,
    status_update: ExpenseStatusUpdateRequest,
    current_user: User = Depends(get_current_user),
):
    """(Pour les RH) Valide ou rejette une note de frais."""
    try:
        _charger_note_rh(expense_id, current_user)
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
