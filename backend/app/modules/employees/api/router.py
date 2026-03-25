"""
Router API du module employees.

Délègue toute la logique à la couche application. Aucune logique métier ni accès DB.
Comportement HTTP identique à api/routers/employees.py (legacy).
"""

import json
import traceback
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.core.security import get_current_user
from app.modules.employees.application import commands, queries
from app.modules.employees.application.dto import EmployeeCreateValidationError
from app.modules.employees.schemas.requests import NewFullEmployee, UpdateEmployee
from app.modules.employees.schemas.responses import (
    ContractResponse,
    EmployeeRhAccess,
    FullEmployee,
    NewEmployeeResponse,
    PromotionListItem,
)
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/employees", tags=["Employees"])


# ----- Liste et détail -----


@router.get("", response_model=List[FullEmployee])
def get_employees(current_user: User = Depends(get_current_user)):
    """Récupère la liste de tous les salariés de l'entreprise active."""
    try:
        company_id = current_user.active_company_id
        if not company_id:
            raise HTTPException(
                status_code=403,
                detail="Impossible de déterminer l'entreprise de l'utilisateur connecté.",
            )
        return queries.get_employees(company_id)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail=f"Erreur interne du serveur: {str(e)}"
        )


@router.get("/me/contract", response_model=ContractResponse)
def get_my_contract(current_user: User = Depends(get_current_user)):
    """(Espace Employé) URL signée de téléchargement du contrat de l'employé connecté."""
    try:
        url = queries.get_my_contract_url(str(current_user.id))
        if url is None:
            return ContractResponse(url=None)
        return ContractResponse(url=url)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@router.get("/me/published-exit-documents")
def get_my_published_exit_documents(
    current_user: User = Depends(get_current_user),
):
    """(Espace Employé) Liste des documents de sortie publiés pour l'employé connecté."""
    try:
        return queries.get_my_published_exit_documents(str(current_user.id))
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@router.get("/{employee_id}", response_model=FullEmployee)
def get_employee_details(
    employee_id: str, current_user: User = Depends(get_current_user)
):
    """Récupère les détails complets d'un salarié."""
    try:
        company_id = current_user.active_company_id
        if not company_id:
            raise HTTPException(
                status_code=403,
                detail="Impossible de déterminer l'entreprise.",
            )
        data = queries.get_employee_by_id(employee_id, company_id)
        if data is None:
            raise HTTPException(status_code=404, detail="Employé non trouvé.")
        return data
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail=f"Erreur interne du serveur: {str(e)}"
        )


# ----- Création (POST) -----


@router.post("", response_model=NewEmployeeResponse, status_code=201)
async def create_employee(
    data: str = Form(...),
    file: Optional[UploadFile] = File(None),
    identity_file: Optional[UploadFile] = File(None),
    generate_pdf_contract: str = Form("false"),
    current_user: User = Depends(get_current_user),
):
    """Crée un nouvel employé (Auth + profil + employees + storage + PDF + RIB)."""
    company_id = queries.get_company_id_for_creator(str(current_user.id))
    if not company_id:
        raise HTTPException(
            status_code=403,
            detail="Impossible de déterminer l'entreprise de l'utilisateur connecté.",
        )

    data_dict = json.loads(data)
    for key in (
        "residence_permit_expiry_date",
        "residence_permit_type",
        "residence_permit_number",
    ):
        if key in data_dict and data_dict[key] == "":
            data_dict[key] = None
    cleaned_data = json.dumps(data_dict)

    try:
        employee_data = NewFullEmployee.model_validate_json(cleaned_data)
    except ValidationError as ve:
        validation_errors = {}
        for error in ve.errors():
            field_path = ".".join(str(loc) for loc in error["loc"])
            validation_errors[field_path] = error["msg"]
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Erreur de validation des données JSON",
                "field_errors": validation_errors,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Données JSON invalides: {e}")

    contract_content: Optional[bytes] = None
    contract_content_type: Optional[str] = None
    if file:
        contract_content = await file.read()
        contract_content_type = file.content_type or "application/pdf"

    identity_content: Optional[bytes] = None
    identity_filename: Optional[str] = None
    identity_content_type: Optional[str] = None
    if identity_file:
        identity_content = await identity_file.read()
        identity_filename = identity_file.filename
        identity_content_type = identity_file.content_type

    try:
        result = await commands.create_employee(
            employee_data=employee_data.model_dump(),
            company_id=company_id,
            contract_file_content=contract_content,
            contract_content_type=contract_content_type,
            identity_file_content=identity_content,
            identity_filename=identity_filename,
            identity_content_type=identity_content_type,
            generate_pdf_contract=generate_pdf_contract.lower() == "true",
        )
        return result
    except EmployeeCreateValidationError as e:
        return JSONResponse(
            status_code=400,
            content={
                "detail": e.message,
                "field_errors": e.field_errors,
            },
        )
    except HTTPException:
        raise


# ----- Mise à jour et suppression -----


@router.put("/{employee_id}", response_model=FullEmployee)
async def update_employee(
    employee_id: str,
    employee_data: UpdateEmployee,
    current_user: User = Depends(get_current_user),
):
    """Met à jour les informations d'un salarié."""
    try:
        update_data = employee_data.model_dump(exclude_unset=True)
        return commands.update_employee(employee_id, update_data)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail=f"Erreur interne du serveur: {str(e)}"
        )


@router.delete("/{employee_id}", status_code=204)
async def delete_employee(
    employee_id: str,
    current_user: User = Depends(get_current_user),
):
    """Supprime un employé, son profil et son utilisateur d'authentification."""
    try:
        commands.delete_employee(employee_id)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Erreur interne du serveur lors de la suppression: {str(e)}",
        )


# ----- URLs signées (contrat, credentials, pièce d'identité) -----


@router.get("/{employee_id}/credentials-pdf", response_model=ContractResponse)
def get_employee_credentials_pdf_url(
    employee_id: str,
    current_user: User = Depends(get_current_user),
):
    """(Espace RH) URL signée du PDF de création de compte."""
    try:
        url = queries.get_credentials_pdf_url(employee_id)
        return ContractResponse(url=url)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@router.get("/{employee_id}/identity-document", response_model=ContractResponse)
def get_employee_identity_document_url(
    employee_id: str, current_user: User = Depends(get_current_user)
):
    """(Espace RH) URL signée de la pièce d'identité."""
    try:
        url = queries.get_identity_document_url(employee_id)
        return ContractResponse(url=url)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@router.get("/{employee_id}/contract", response_model=ContractResponse)
def get_employee_contract_url(
    employee_id: str,
    current_user: User = Depends(get_current_user),
):
    """(Espace RH) URL signée du contrat PDF."""
    try:
        url = queries.get_contract_url(employee_id)
        return ContractResponse(url=url)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


# ----- Promotions et accès RH -----


@router.get("/{employee_id}/promotions", response_model=List[PromotionListItem])
def get_employee_promotions(
    employee_id: str,
    current_user: User = Depends(get_current_user),
):
    """Liste des promotions d'un employé."""
    try:
        company_id = queries.get_employee_company_id(employee_id)
        if not company_id:
            raise HTTPException(status_code=404, detail="Employé non trouvé.")
        if current_user.active_company_id != company_id and not getattr(
            current_user, "is_super_admin", False
        ):
            raise HTTPException(
                status_code=403, detail="Accès non autorisé à cet employé."
            )
        return queries.get_employee_promotions(company_id, employee_id)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@router.get("/{employee_id}/rh-access", response_model=EmployeeRhAccess)
def get_employee_rh_access_info(
    employee_id: str,
    current_user: User = Depends(get_current_user),
):
    """Accès RH actuel et rôles disponibles pour un employé (RH uniquement)."""
    try:
        company_id = queries.get_employee_company_id(employee_id)
        if not company_id:
            raise HTTPException(status_code=404, detail="Employé non trouvé.")
        if current_user.active_company_id != company_id and not getattr(
            current_user, "is_super_admin", False
        ):
            raise HTTPException(
                status_code=403, detail="Accès non autorisé à cet employé."
            )
        if not getattr(current_user, "has_rh_access_in_company", lambda _: False)(
            company_id
        ) and not getattr(current_user, "is_super_admin", False):
            raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
        return queries.get_employee_rh_access(employee_id, company_id)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")
