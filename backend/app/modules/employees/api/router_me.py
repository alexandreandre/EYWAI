"""Routes espace collaborateur (/me/*) — inclus par router principal."""

from __future__ import annotations

import traceback

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.modules.employees.api.deps import resolve_my_employee_id
from app.modules.employees.application import queries
from app.modules.employees.schemas.responses import ContractResponse, FullEmployee
from app.modules.users.schemas.responses import User

me_router = APIRouter()


@me_router.get("/me", response_model=FullEmployee)
def get_my_employee_details(current_user: User = Depends(get_current_user)):
    """(Espace employé) Fiche collaborateur liée au compte connecté."""
    try:
        company_id = current_user.active_company_id
        if not company_id:
            raise HTTPException(
                status_code=403,
                detail="Impossible de déterminer l'entreprise.",
            )
        data = queries.get_my_employee_profile(str(current_user.id), company_id)
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


@me_router.get("/me/contract", response_model=ContractResponse)
def get_my_contract(current_user: User = Depends(get_current_user)):
    """(Espace Employé) URL signée de téléchargement du contrat de l'employé connecté."""
    try:
        employee_id = resolve_my_employee_id(current_user)
        url = queries.get_my_contract_url(employee_id)
        if url is None:
            return ContractResponse(url=None)
        return ContractResponse(url=url)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@me_router.get("/me/identity-document", response_model=ContractResponse)
def get_my_identity_document(current_user: User = Depends(get_current_user)):
    """(Espace Employé) URL signée de la pièce d'identité / titre de séjour."""
    try:
        employee_id = resolve_my_employee_id(current_user)
        url = queries.get_identity_document_url(employee_id)
        if url is None:
            return ContractResponse(url=None)
        return ContractResponse(url=url)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@me_router.get("/me/published-exit-documents")
def get_my_published_exit_documents(
    current_user: User = Depends(get_current_user),
):
    """(Espace Employé) Liste des documents de sortie publiés pour l'employé connecté."""
    try:
        employee_id = resolve_my_employee_id(current_user)
        return queries.get_my_published_exit_documents(employee_id)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")
