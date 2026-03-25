"""
Router API du module employee_exits — sorties de salariés.

Délègue uniquement à la couche application (commands, queries).
Aucune logique métier lourde : auth, permissions, conversion erreurs → HTTP.
Comportement HTTP identique à api/routers/employee_exits.py.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.modules.access_control.application.service import get_access_control_service
from app.modules.users.schemas.responses import User

from app.modules.employee_exits.application import commands, queries
from app.modules.employee_exits.application.dto import EmployeeExitApplicationError
from app.modules.employee_exits.schemas import (
    ChecklistItem,
    ChecklistItemCreate,
    ChecklistItemUpdate,
    DocumentUploadUrlRequest,
    DocumentUploadUrlResponse,
    EmployeeExit,
    EmployeeExitCreate,
    EmployeeExitUpdate,
    EmployeeExitWithDetails,
    ExitDocument,
    ExitDocumentCreate,
    ExitDocumentDetails,
    ExitDocumentEditRequest,
    ExitDocumentEditResponse,
    ExitIndemnityCalculation,
    PublishExitDocumentsRequest,
    PublishExitDocumentsResponse,
    StatusTransitionResponse,
    StatusUpdateRequest,
)

router = APIRouter(
    prefix="/api/employee-exits",
    tags=["Employee Exits"],
)


# ---------------------------------------------------------------------------
# Helpers HTTP (auth, permissions) — pas de logique métier
# ---------------------------------------------------------------------------


def _company_id_required(user: User) -> str:
    cid = user.active_company_id
    if not cid:
        raise HTTPException(status_code=400, detail="Aucune entreprise active")
    return str(cid)


def _check_exit_permission(user: User, company_id: str, _permission: str) -> None:
    """Vérifie que l'utilisateur a le droit d'agir sur les sorties (admin/rh ou super_admin)."""
    if user.is_super_admin:
        return
    role = user.get_role_in_company(company_id)
    if role in ("admin", "rh"):
        return
    raise HTTPException(
        status_code=403,
        detail="Vous n'avez pas les permissions pour cette action sur les sorties de salariés",
    )


def _check_publish_permission(user: User, company_id: str) -> None:
    """Vérifie la permission de publication des documents (RH ou permission granulaire)."""
    if user.is_super_admin:
        return
    if getattr(user, "has_rh_access_in_company", lambda c: False)(company_id):
        return
    try:
        if get_access_control_service().check_user_has_permission(
            str(user.id), company_id, "employee_documents.publish_exit_documents"
        ):
            return
    except Exception:
        pass
    raise HTTPException(
        status_code=403,
        detail="Vous n'avez pas les permissions pour publier des documents de sortie",
    )


def _check_unpublish_permission(user: User, company_id: str) -> None:
    """Vérifie la permission de dépublication."""
    if user.is_super_admin:
        return
    role = user.get_role_in_company(company_id)
    if role in ("admin", "rh"):
        return
    try:
        if get_access_control_service().check_user_has_permission(
            str(user.id), company_id, "employee_exit.publish"
        ):
            return
    except Exception:
        pass
    raise HTTPException(
        status_code=403,
        detail="Vous n'avez pas les permissions pour dépublier des documents",
    )


def _to_http(e: EmployeeExitApplicationError) -> HTTPException:
    return HTTPException(status_code=e.status_code, detail=e.detail)


# ---------------------------------------------------------------------------
# Sorties
# ---------------------------------------------------------------------------


@router.post("/", response_model=EmployeeExit, status_code=201)
async def create_employee_exit(
    exit_data: EmployeeExitCreate,
    current_user: User = Depends(get_current_user),
):
    """Créer un nouveau processus de sortie de salarié."""
    try:
        company_id = queries.get_employee_company_id(str(exit_data.employee_id))
    except EmployeeExitApplicationError as e:
        raise _to_http(e)
    _check_exit_permission(current_user, company_id, "create")
    payload = exit_data.model_dump()
    payload["employee_id"] = str(payload["employee_id"])
    for k in ("exit_request_date", "last_working_day"):
        if payload.get(k) and hasattr(payload[k], "isoformat"):
            payload[k] = payload[k].isoformat()
    try:
        created = commands.create_employee_exit(
            payload,
            company_id,
            str(current_user.id),
        )
        return EmployeeExit(**created)
    except EmployeeExitApplicationError as e:
        raise _to_http(e)


@router.get("/", response_model=List[EmployeeExitWithDetails])
async def list_employee_exits(
    status: Optional[str] = None,
    exit_type: Optional[str] = None,
    employee_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """Liste toutes les sorties de l'entreprise active."""
    company_id = _company_id_required(current_user)
    _check_exit_permission(current_user, company_id, "view_all")
    try:
        items = queries.list_employee_exits(
            company_id, status=status, exit_type=exit_type, employee_id=employee_id
        )
        return items
    except EmployeeExitApplicationError as e:
        raise _to_http(e)


@router.get("/{exit_id}", response_model=EmployeeExitWithDetails)
async def get_employee_exit(
    exit_id: str,
    current_user: User = Depends(get_current_user),
):
    """Récupère les détails complets d'une sortie."""
    company_id = _company_id_required(current_user)
    try:
        return queries.get_employee_exit(str(exit_id), company_id)
    except EmployeeExitApplicationError as e:
        raise _to_http(e)


@router.patch("/{exit_id}", response_model=EmployeeExit)
async def update_employee_exit(
    exit_id: str,
    exit_update: EmployeeExitUpdate,
    current_user: User = Depends(get_current_user),
):
    """Met à jour une sortie de salarié."""
    company_id = _company_id_required(current_user)
    update_data = exit_update.model_dump(exclude_unset=True)
    for k, v in list(update_data.items()):
        if hasattr(v, "isoformat"):
            update_data[k] = v.isoformat()
    try:
        updated = commands.update_employee_exit(str(exit_id), company_id, update_data)
        return EmployeeExit(**updated)
    except EmployeeExitApplicationError as e:
        raise _to_http(e)


@router.patch("/{exit_id}/status", response_model=StatusTransitionResponse)
async def update_exit_status(
    exit_id: str,
    status_request: StatusUpdateRequest,
    current_user: User = Depends(get_current_user),
):
    """Met à jour le statut d'une sortie (validation des transitions)."""
    company_id = _company_id_required(current_user)
    try:
        updated = commands.update_exit_status(
            str(exit_id),
            company_id,
            status_request.new_status,
            status_request.notes,
            str(current_user.id),
        )
        return StatusTransitionResponse(
            success=True,
            exit=EmployeeExit(**updated),
            message=f"Statut mis à jour vers '{status_request.new_status}'",
        )
    except EmployeeExitApplicationError as e:
        raise _to_http(e)


@router.delete("/{exit_id}", status_code=204)
async def delete_employee_exit(
    exit_id: str,
    current_user: User = Depends(get_current_user),
):
    """Supprime une sortie (et remet l'employé en actif)."""
    company_id = _company_id_required(current_user)
    _check_exit_permission(current_user, company_id, "delete")
    try:
        commands.delete_employee_exit(str(exit_id), company_id)
    except EmployeeExitApplicationError as e:
        raise _to_http(e)
    return None


# ---------------------------------------------------------------------------
# Indemnités
# ---------------------------------------------------------------------------


@router.post(
    "/{exit_id}/calculate-indemnities", response_model=ExitIndemnityCalculation
)
async def calculate_exit_indemnities(
    exit_id: str,
    current_user: User = Depends(get_current_user),
):
    """Calcule les indemnités de sortie et met à jour l'enregistrement."""
    company_id = _company_id_required(current_user)
    try:
        return queries.calculate_exit_indemnities(str(exit_id), company_id)
    except EmployeeExitApplicationError as e:
        raise _to_http(e)


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


@router.post(
    "/{exit_id}/documents/upload-url", response_model=DocumentUploadUrlResponse
)
async def get_document_upload_url(
    exit_id: str,
    request: DocumentUploadUrlRequest,
    current_user: User = Depends(get_current_user),
):
    """Génère une URL signée pour uploader un document."""
    company_id = _company_id_required(current_user)
    try:
        result = queries.get_document_upload_url(
            str(exit_id), company_id, request.filename
        )
        return DocumentUploadUrlResponse(**result)
    except EmployeeExitApplicationError as e:
        raise _to_http(e)


@router.post("/{exit_id}/documents", response_model=ExitDocument, status_code=201)
async def create_exit_document(
    exit_id: str,
    document_data: ExitDocumentCreate,
    current_user: User = Depends(get_current_user),
):
    """Associe un document uploadé à une sortie."""
    company_id = _company_id_required(current_user)
    data = document_data.model_dump()
    try:
        created = commands.create_exit_document(
            str(exit_id),
            company_id,
            data,
            str(current_user.id),
        )
        return ExitDocument(**created)
    except EmployeeExitApplicationError as e:
        raise _to_http(e)


@router.get("/{exit_id}/documents", response_model=List[ExitDocument])
async def list_exit_documents(
    exit_id: str,
    current_user: User = Depends(get_current_user),
):
    """Liste les documents d'une sortie."""
    company_id = _company_id_required(current_user)
    try:
        return queries.list_exit_documents(str(exit_id), company_id)
    except EmployeeExitApplicationError as e:
        raise _to_http(e)


@router.post("/{exit_id}/documents/generate/{document_type}")
async def generate_exit_document(
    exit_id: str,
    document_type: str,
    current_user: User = Depends(get_current_user),
):
    """Génère un document (certificat de travail, attestation Pôle Emploi, solde de tout compte)."""
    company_id = _company_id_required(current_user)
    try:
        return commands.generate_exit_document(
            str(exit_id),
            company_id,
            document_type,
            str(current_user.id),
        )
    except EmployeeExitApplicationError as e:
        raise _to_http(e)


@router.delete("/{exit_id}/documents/{document_id}", status_code=204)
async def delete_exit_document(
    exit_id: str,
    document_id: str,
    current_user: User = Depends(get_current_user),
):
    """Supprime un document de sortie."""
    company_id = _company_id_required(current_user)
    try:
        commands.delete_exit_document(str(exit_id), str(document_id), company_id)
    except EmployeeExitApplicationError as e:
        raise _to_http(e)
    return None


@router.post(
    "/{exit_id}/documents/publish", response_model=PublishExitDocumentsResponse
)
async def publish_exit_documents(
    exit_id: str,
    request: PublishExitDocumentsRequest,
    current_user: User = Depends(get_current_user),
):
    """Publie des documents de sortie vers l'espace Documents du salarié."""
    company_id = _company_id_required(current_user)
    _check_publish_permission(current_user, company_id)
    doc_ids = [str(d) for d in request.document_ids] if request.document_ids else None
    try:
        result = commands.publish_exit_documents(
            str(exit_id),
            company_id,
            doc_ids,
            request.force_update,
            str(current_user.id),
        )
        return PublishExitDocumentsResponse(**result)
    except EmployeeExitApplicationError as e:
        raise _to_http(e)


@router.post(
    "/{exit_id}/documents/{document_id}/unpublish", response_model=ExitDocument
)
async def unpublish_exit_document(
    exit_id: str,
    document_id: str,
    current_user: User = Depends(get_current_user),
):
    """Dépublie un document de sortie."""
    company_id = _company_id_required(current_user)
    _check_unpublish_permission(current_user, company_id)
    try:
        updated = commands.unpublish_exit_document(
            str(exit_id), str(document_id), company_id
        )
        return ExitDocument(**updated)
    except EmployeeExitApplicationError as e:
        raise _to_http(e)


@router.get(
    "/{exit_id}/documents/{document_id}/details", response_model=ExitDocumentDetails
)
async def get_exit_document_details(
    exit_id: str,
    document_id: str,
    current_user: User = Depends(get_current_user),
):
    """Détails complets d'un document avec données éditables."""
    company_id = _company_id_required(current_user)
    try:
        return queries.get_exit_document_details(
            str(exit_id), str(document_id), company_id
        )
    except EmployeeExitApplicationError as e:
        raise _to_http(e)


@router.post(
    "/{exit_id}/documents/{document_id}/edit", response_model=ExitDocumentEditResponse
)
async def edit_exit_document(
    exit_id: str,
    document_id: str,
    edit_request: ExitDocumentEditRequest,
    current_user: User = Depends(get_current_user),
):
    """Édite un document généré et régénère le PDF."""
    company_id = _company_id_required(current_user)
    edit_data = edit_request.model_dump()
    if edit_data.get("document_data"):
        for section in ("employee", "company", "exit"):
            if (
                section in edit_data["document_data"]
                and edit_data["document_data"][section]
            ):
                for k, v in list(edit_data["document_data"][section].items()):
                    if hasattr(v, "isoformat"):
                        edit_data["document_data"][section][k] = v.isoformat()
    try:
        result = commands.edit_exit_document(
            str(exit_id),
            str(document_id),
            company_id,
            edit_data,
            str(current_user.id),
        )
        return ExitDocumentEditResponse(**result)
    except EmployeeExitApplicationError as e:
        raise _to_http(e)


@router.get("/{exit_id}/documents/{document_id}/history")
async def get_document_edit_history(
    exit_id: str,
    document_id: str,
    current_user: User = Depends(get_current_user),
):
    """Historique des modifications d'un document."""
    company_id = _company_id_required(current_user)
    try:
        return queries.get_document_edit_history(
            str(exit_id), str(document_id), company_id
        )
    except EmployeeExitApplicationError as e:
        raise _to_http(e)


# ---------------------------------------------------------------------------
# Checklist
# ---------------------------------------------------------------------------


@router.get("/{exit_id}/checklist", response_model=List[ChecklistItem])
async def get_exit_checklist(
    exit_id: str,
    current_user: User = Depends(get_current_user),
):
    """Récupère la checklist d'une sortie."""
    company_id = _company_id_required(current_user)
    try:
        return queries.get_exit_checklist(str(exit_id), company_id)
    except EmployeeExitApplicationError as e:
        raise _to_http(e)


@router.post("/{exit_id}/checklist", response_model=ChecklistItem, status_code=201)
async def add_checklist_item(
    exit_id: str,
    item_data: ChecklistItemCreate,
    current_user: User = Depends(get_current_user),
):
    """Ajoute un item personnalisé à la checklist."""
    company_id = _company_id_required(current_user)
    data = item_data.model_dump()
    if data.get("due_date") and hasattr(data["due_date"], "isoformat"):
        data["due_date"] = data["due_date"].isoformat()
    try:
        created = commands.add_checklist_item(str(exit_id), company_id, data)
        return ChecklistItem(**created)
    except EmployeeExitApplicationError as e:
        raise _to_http(e)


@router.patch("/{exit_id}/checklist/{item_id}/complete")
async def mark_checklist_item_complete(
    exit_id: str,
    item_id: str,
    item_update: ChecklistItemUpdate,
    current_user: User = Depends(get_current_user),
):
    """Marque un item de checklist comme complété ou non."""
    company_id = _company_id_required(current_user)
    update_data = item_update.model_dump(exclude_unset=True)
    if update_data.get("due_date") and hasattr(update_data["due_date"], "isoformat"):
        update_data["due_date"] = update_data["due_date"].isoformat()
    try:
        updated = commands.mark_checklist_item_complete(
            str(exit_id),
            str(item_id),
            company_id,
            update_data,
            str(current_user.id),
        )
        return ChecklistItem(**updated)
    except EmployeeExitApplicationError as e:
        raise _to_http(e)


@router.delete("/{exit_id}/checklist/{item_id}", status_code=204)
async def delete_checklist_item(
    exit_id: str,
    item_id: str,
    current_user: User = Depends(get_current_user),
):
    """Supprime un item de checklist (non obligatoire uniquement)."""
    company_id = _company_id_required(current_user)
    try:
        commands.delete_checklist_item(str(exit_id), str(item_id), company_id)
    except EmployeeExitApplicationError as e:
        raise _to_http(e)
    return None
