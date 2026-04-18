"""Écriture — documents générés."""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.core.database import supabase
from app.modules.documents.infrastructure.repository import documents_repository
from app.modules.documents.schemas.requests import (
    GenerateDocumentRequest,
    UpdateDocumentStatusRequest,
)
from app.modules.document_library.schemas.requests import KNOWN_DOCUMENT_TYPES
from app.services.document_service import document_service

_ALLOWED_STATUS = frozenset({"brouillon", "envoye", "signe", "archive"})
_CONTRACT_LIKE_TYPES = frozenset(
    {"cdi", "cdd", "convention_stage", "contrat_alternance"}
)


def _data(resp: Any) -> Any:
    return resp.data if resp else None


def _load_employee(employee_id: str, company_id: str) -> Dict[str, Any]:
    r = (
        supabase.table("employees")
        .select("*")
        .eq("id", employee_id)
        .eq("company_id", company_id)
        .maybe_single()
        .execute()
    )
    row = _data(r)
    if not row:
        raise LookupError("Collaborateur introuvable dans cette entreprise.")
    return dict(row)


def _load_company(company_id: str) -> Dict[str, Any]:
    r = (
        supabase.table("companies")
        .select("*")
        .eq("id", company_id)
        .maybe_single()
        .execute()
    )
    row = _data(r)
    if not row:
        raise LookupError("Entreprise introuvable.")
    return dict(row)


def _validate_template_choice(
    company_id: str, document_type: str, template_id: Optional[str]
) -> Optional[str]:
    if not template_id or template_id.strip() in ("", "__eywai__"):
        return None
    tid = template_id.strip()
    tr = (
        supabase.table("document_templates")
        .select("id, document_type, status")
        .eq("id", tid)
        .eq("company_id", company_id)
        .eq("status", "active")
        .maybe_single()
        .execute()
    )
    row = _data(tr)
    if not row:
        raise ValueError("Modèle sélectionné introuvable ou inactif.")
    if str(row.get("document_type") or "") != document_type:
        raise ValueError("Le modèle choisi ne correspond pas au type de document.")
    return tid


def generate_document(
    company_id: str,
    current_user_id: str,
    request: GenerateDocumentRequest,
) -> dict:
    if request.document_type not in KNOWN_DOCUMENT_TYPES:
        raise ValueError(f"Type de document inconnu : {request.document_type}")

    needs_date_effet = (
        request.document_type in _CONTRACT_LIKE_TYPES
        or "avenant" in request.document_type
    )
    if needs_date_effet and request.date_effet is None:
        raise ValueError("La date d'effet est obligatoire pour ce type de document.")

    template_override = _validate_template_choice(
        company_id, request.document_type, request.template_id
    )

    employee_data = _load_employee(request.employee_id, company_id)
    company_data = _load_company(company_id)

    ctx: Dict[str, Any] = {}
    if request.date_effet is not None:
        ctx["date_effet"] = request.date_effet.isoformat()
    if request.motif:
        ctx["motif"] = request.motif
        ctx["motif_avenant"] = request.motif
    if "avenant" in request.document_type:
        ctx["type_avenant"] = request.document_type

    gen = document_service.generate_document(
        company_id=company_id,
        employee_id=request.employee_id,
        document_type=request.document_type,
        category=request.category,
        employee_data=employee_data,
        company_data=company_data,
        context=ctx,
        generated_by=current_user_id,
        template_id_override=template_override,
    )
    doc_id = str(gen.get("document_id") or "")
    if not doc_id:
        raise RuntimeError("Génération sans identifiant document.")
    row = documents_repository.get_by_id(doc_id, company_id)
    if not row:
        raise RuntimeError("Document créé mais non relisible.")
    return row


def update_document_status(
    document_id: str, company_id: str, body: UpdateDocumentStatusRequest
) -> dict:
    if body.status not in _ALLOWED_STATUS:
        raise ValueError(f"Statut invalide : {body.status}")
    return documents_repository.update_status(document_id, company_id, body.status)


def delete_document(document_id: str, company_id: str) -> None:
    documents_repository.delete(document_id, company_id)
