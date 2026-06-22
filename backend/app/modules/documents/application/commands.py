"""Écriture — documents générés."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone
from typing import Any, Dict, Optional

from app.core.database import supabase
from app.modules.documents.infrastructure.repository import BUCKET, documents_repository
from app.modules.employees.infrastructure.providers import get_storage_provider
from app.modules.employees.infrastructure.repository import EmployeeRepository
from app.modules.documents.schemas.requests import (
    GenerateDocumentRequest,
    UpdateDocumentStatusRequest,
)
from app.modules.document_library.schemas.requests import (
    DOCUMENT_TYPE_LABELS,
    KNOWN_DOCUMENT_TYPES,
)
from app.services.document_variables import enrich_context_from_recruitment_job
from app.modules.notifications.application.employee_document_alerts import (
    notify_employee_new_document,
)
from app.services.document_service import document_service

_ALLOWED_STATUS = frozenset({"brouillon", "envoye", "signe", "archive"})
_CONTRACT_LIKE_TYPES = frozenset(
    {"cdi", "cdd", "convention_stage", "contrat_alternance"}
)
_TRANSMIT_DOCUMENT_TYPE = "document_transmis"
_MAX_TRANSMIT_BYTES = 10 * 1024 * 1024

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


def _salaire_valeur(employee_data: Dict[str, Any]) -> Optional[float]:
    sb = employee_data.get("salaire_de_base")
    if isinstance(sb, dict):
        val = sb.get("valeur", sb.get("amount"))
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                return None
    if sb is not None:
        try:
            return float(sb)
        except (TypeError, ValueError):
            return None
    return None


def _lieu_travail_str(employee_data: Dict[str, Any]) -> str:
    lt = employee_data.get("lieu_travail") or employee_data.get("workplace")
    if isinstance(lt, str):
        return lt.strip()
    if isinstance(lt, dict):
        return str(lt.get("libelle") or lt.get("label") or lt.get("name") or "").strip()
    return ""


def _duree_str(employee_data: Dict[str, Any]) -> str:
    v = employee_data.get("duree_hebdomadaire") or employee_data.get("weekly_hours")
    if v is None:
        return ""
    try:
        return f"{float(v):g} h"
    except (TypeError, ValueError):
        return str(v).strip()


def _enrichir_contexte_avenant(
    ctx: Dict[str, Any],
    employee_data: Dict[str, Any],
    request: GenerateDocumentRequest,
) -> None:
    """Remplit ancien_* depuis l'employé et nouveau_* depuis la requête (front prioritaire)."""
    if "ancien_salaire" not in ctx:
        sal = _salaire_valeur(employee_data)
        if request.ancien_salaire is not None:
            ctx["ancien_salaire"] = float(request.ancien_salaire)
        elif sal is not None:
            ctx["ancien_salaire"] = sal

    if "ancien_poste" not in ctx:
        if request.ancien_poste:
            ctx["ancien_poste"] = request.ancien_poste
        elif employee_data.get("job_title"):
            ctx["ancien_poste"] = str(employee_data["job_title"])

    if "ancienne_duree" not in ctx:
        if request.ancienne_duree:
            ctx["ancienne_duree"] = request.ancienne_duree
        else:
            d = _duree_str(employee_data)
            if d:
                ctx["ancienne_duree"] = d

    if "ancien_lieu" not in ctx:
        if request.ancien_lieu:
            ctx["ancien_lieu"] = request.ancien_lieu
        else:
            lieu = _lieu_travail_str(employee_data)
            if lieu:
                ctx["ancien_lieu"] = lieu

    if request.nouveau_poste is not None:
        ctx["nouveau_poste"] = request.nouveau_poste
    if request.nouvelle_duree is not None:
        ctx["nouvelle_duree"] = request.nouvelle_duree
    if request.nouveau_lieu is not None:
        ctx["nouveau_lieu"] = request.nouveau_lieu


def _load_recruitment_job(job_id: str, company_id: str) -> Dict[str, Any]:
    r = (
        supabase.table("recruitment_jobs")
        .select("*")
        .eq("id", job_id)
        .eq("company_id", company_id)
        .maybe_single()
        .execute()
    )
    row = _data(r)
    if not row:
        raise LookupError("Offre de recrutement introuvable.")
    return dict(row)


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

    if request.document_type == "fiche_poste":
        if not template_override:
            raise ValueError(
                "Un modèle de fiche de poste est obligatoire. "
                "Importez un fichier dans la bibliothèque de documents."
            )

    if request.document_type in ("bulletin_participation", "bulletin_interessement"):
        if not template_override:
            bundle = document_service.get_active_template(company_id, request.document_type)
            if not bundle:
                raise ValueError(
                    "Un modèle de bulletin d'option est obligatoire. "
                    "Importez un fichier dans la bibliothèque de documents."
                )

    employee_data = _load_employee(request.employee_id, company_id)
    company_data = _load_company(company_id)

    ctx: Dict[str, Any] = {}
    if request.custom_fields:
        ctx["custom_fields"] = {
            str(k): str(v) for k, v in request.custom_fields.items() if str(k).strip()
        }
    if request.recruitment_job_id:
        job = _load_recruitment_job(request.recruitment_job_id, company_id)
        ctx = enrich_context_from_recruitment_job(ctx, job)
    if request.date_effet is not None:
        ctx["date_effet"] = request.date_effet.isoformat()
    if request.motif:
        ctx["motif"] = request.motif
        ctx["motif_avenant"] = request.motif
    if "avenant" in request.document_type:
        ctx["type_avenant"] = request.document_type
        _enrichir_contexte_avenant(ctx, employee_data, request)
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


def _resolve_fiche_poste_template_id(
    company_id: str, template_id: Optional[str]
) -> str:
    override = _validate_template_choice(company_id, "fiche_poste", template_id)
    if override:
        return override
    bundle = document_service.get_active_template(company_id, "fiche_poste")
    if bundle and bundle.get("template"):
        return str(bundle["template"]["id"])
    raise ValueError(
        "Aucun modèle de fiche de poste configuré — importez un fichier "
        "dans la bibliothèque de documents."
    )


def generate_job_fiche_poste_pdf(
    company_id: str,
    job_id: str,
    template_id: Optional[str] = None,
) -> bytes:
    job = _load_recruitment_job(job_id, company_id)
    company_data = _load_company(company_id)
    ctx = enrich_context_from_recruitment_job({}, job)
    tid = _resolve_fiche_poste_template_id(company_id, template_id)
    result = document_service.generate_document(
        company_id=company_id,
        employee_id="",
        document_type="fiche_poste",
        category="attestation_courante",
        employee_data={},
        company_data=company_data,
        context=ctx,
        template_id_override=tid,
        persist=False,
    )
    pdf = result.get("pdf_bytes")
    if not pdf:
        raise RuntimeError("Génération PDF impossible.")
    return bytes(pdf)


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

    from app.modules.employees.application.commands import apply_salary_update

    apply_salary_update(
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


def _document_display_label(document: Dict[str, Any]) -> str:
    gc = document.get("generation_context") or {}
    if isinstance(gc, dict):
        custom = gc.get("custom_label")
        if custom is not None and str(custom).strip():
            return str(custom).strip()
    document_type = str(document.get("document_type") or "")
    if document_type in DOCUMENT_TYPE_LABELS:
        return DOCUMENT_TYPE_LABELS[document_type]
    return document_type.replace("_", " ").strip().title() or "Document"


def _validate_transmit_file(
    file_content: bytes,
    filename: str,
) -> None:
    if not file_content:
        raise ValueError("Fichier vide.")
    if len(file_content) > _MAX_TRANSMIT_BYTES:
        raise ValueError("Le fichier dépasse la taille maximale autorisée (10 Mo).")
    name = (filename or "").lower().strip()
    if not name.endswith(".pdf"):
        raise ValueError("Seuls les fichiers PDF sont acceptés.")


def transmit_employee_document(
    company_id: str,
    current_user_id: str,
    employee_id: str,
    document_label: str,
    file_content: bytes,
    filename: str,
    *,
    send_immediately: bool = True,
    content_type: Optional[str] = None,
) -> dict:
    """Dépose un PDF RH et l'enregistre dans generated_documents (optionnellement envoyé)."""
    label = document_label.strip()
    if len(label) < 2:
        raise ValueError("L'intitulé du document doit contenir au moins 2 caractères.")

    _validate_transmit_file(file_content, filename)
    _load_employee(employee_id, company_id)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    storage_path = f"{company_id}/{employee_id}/{_TRANSMIT_DOCUMENT_TYPE}_{ts}.pdf"
    storage = get_storage_provider()
    try:
        storage.upload(
            BUCKET,
            storage_path,
            file_content,
            content_type or "application/pdf",
        )
    except Exception as exc:
        logger.warning("transmit_employee_document upload failed: %s", exc)
        raise RuntimeError("Impossible d'enregistrer le fichier PDF.") from exc

    original_name = (filename or "document.pdf").strip() or "document.pdf"
    safe_name = re.sub(r"[^\w.\- ]+", "_", original_name)[:200]
    status = "envoye" if send_immediately else "brouillon"
    row = documents_repository.insert(
        {
            "company_id": company_id,
            "employee_id": employee_id,
            "document_type": _TRANSMIT_DOCUMENT_TYPE,
            "category": "attestation_courante",
            "template_id": None,
            "template_version_id": None,
            "is_eywai_template": False,
            "file_url": storage_path,
            "file_name": safe_name,
            "status": status,
            "generation_context": {
                "custom_label": label,
                "transmitted_by_rh": True,
            },
            "generated_by": current_user_id,
        }
    )
    if send_immediately:
        _notify_document_sent_to_employee(row, company_id)
    return row


def _notify_document_sent_to_employee(document: Dict[str, Any], company_id: str) -> None:
    employee_id = document.get("employee_id")
    if not employee_id:
        return
    label = _document_display_label(document)
    try:
        notify_employee_new_document(str(employee_id), company_id, label)
    except Exception as exc:
        logger.info("[doc_notif] Non bloquant envoi document %s: %s", document.get("id"), exc)


def update_document_status(
    document_id: str,
    company_id: str,
    body: UpdateDocumentStatusRequest,
    *,
    updated_by_user_id: Optional[str] = None,
) -> dict:
    if body.status not in _ALLOWED_STATUS:
        raise ValueError(f"Statut invalide : {body.status}")
    previous = documents_repository.get_by_id(document_id, company_id)
    previous_status = str((previous or {}).get("status") or "")
    updated_row = documents_repository.update_status(document_id, company_id, body.status)
    if body.status == "envoye" and previous_status == "brouillon":
        _notify_document_sent_to_employee(updated_row, company_id)
    if body.status == "signe":
        _handle_avenant_signe(updated_row, company_id, updated_by_user_id or "")
    return updated_row


def delete_document(document_id: str, company_id: str) -> None:
    documents_repository.delete(document_id, company_id)
