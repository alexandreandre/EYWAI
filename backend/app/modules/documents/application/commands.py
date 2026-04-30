"""Écriture — documents générés."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, Optional

from app.core.database import supabase
from app.modules.documents.infrastructure.repository import documents_repository
from app.modules.employees.infrastructure.repository import EmployeeRepository
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

logger = logging.getLogger(__name__)
_employees_repo_avenants = EmployeeRepository()


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
    if request.nouveau_salaire is not None:
        ctx["nouveau_salaire"] = float(request.nouveau_salaire)

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


def _effective_date_str_from_context(context: Dict[str, Any]) -> str:
    raw = context.get("date_effet")
    if isinstance(raw, str) and raw.strip():
        s = raw.strip()
        return s.split("T")[0].split(" ")[0]
    return date.today().isoformat()


def _apply_salary_from_avenant(
    employee_id: str,
    company_id: str,
    context: Dict[str, Any],
    updated_by: str,
) -> None:
    nouveau_val = context.get("nouveau_salaire") or context.get("nouveau_salaire_brut")
    if nouveau_val is None:
        return
    try:
        nouveau_float = float(nouveau_val)
    except (TypeError, ValueError):
        return

    emp = (
        supabase.table("employees")
        .select("salaire_de_base")
        .eq("id", employee_id)
        .eq("company_id", company_id)
        .maybe_single()
        .execute()
    )
    row = emp.data if emp else None
    if not row:
        return

    ancien = row.get("salaire_de_base") or {"valeur": 0.0}
    eff = _effective_date_str_from_context(context)
    motif_raw = context.get("motif") or context.get("motif_avenant")
    motif = str(motif_raw).strip() if motif_raw else "Avenant signé"

    _employees_repo_avenants.update_salary(
        employee_id=employee_id,
        company_id=company_id,
        ancien_salaire=ancien if isinstance(ancien, dict) else {"valeur": 0.0},
        nouveau_salaire={"valeur": nouveau_float},
        motif=motif,
        effective_date=eff,
        created_by=updated_by,
    )


def _notify_employee_avenant_signe(
    employee_id: str,
    company_id: str,
    document_type: str,
    context: Dict[str, Any],
) -> None:
    LABELS = {
        "avenant_salaire": "avenant de salaire",
        "avenant_poste": "avenant de poste",
        "avenant_temps": "avenant de temps de travail",
        "avenant_lieu": "avenant de lieu de travail",
        "avenant_general": "avenant",
    }
    label = LABELS.get(document_type, "avenant")
    date_effet = ""
    raw_de = context.get("date_effet")
    if isinstance(raw_de, str) and raw_de.strip():
        date_effet = raw_de.strip()
    message = (
        f"Votre {label} a été signé"
        + (f" et prend effet le {date_effet}." if date_effet else ".")
    )

    try:
        supabase.table("notifications").insert(
            {
                "employee_id": employee_id,
                "company_id": company_id,
                "type": "avenant_signe",
                "message": message,
                "is_read": False,
            }
        ).execute()
    except Exception:
        logger.info("[notify] Notification non insérée pour %s", employee_id)


def _handle_avenant_signe(
    document: Dict[str, Any],
    company_id: str,
    updated_by: str,
) -> None:
    """
    Best effort — ne jamais faire échouer le changement de statut.
    """
    try:
        document_type = str(document.get("document_type") or "")
        employee_id = document.get("employee_id")
        gc = document.get("generation_context") or {}
        context: Dict[str, Any] = gc if isinstance(gc, dict) else {}

        if not employee_id:
            return

        if document_type == "avenant_salaire":
            _apply_salary_from_avenant(str(employee_id), company_id, context, updated_by)

        _notify_employee_avenant_signe(str(employee_id), company_id, document_type, context)

    except Exception as e:
        logger.error("[avenant_signe] Erreur non bloquante : %s", e)


def update_document_status(
    document_id: str,
    company_id: str,
    body: UpdateDocumentStatusRequest,
    *,
    updated_by_user_id: Optional[str] = None,
) -> dict:
    if body.status not in _ALLOWED_STATUS:
        raise ValueError(f"Statut invalide : {body.status}")
    updated_row = documents_repository.update_status(document_id, company_id, body.status)
    if body.status == "signe":
        _handle_avenant_signe(updated_row, company_id, updated_by_user_id or "")
    return updated_row


def delete_document(document_id: str, company_id: str) -> None:
    documents_repository.delete(document_id, company_id)
