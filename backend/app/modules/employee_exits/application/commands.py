"""
Commandes (cas d'usage écriture) du module employee_exits.

Orchestration : domain (rules), infrastructure (repositories, queries, providers, mappers).
Comportement identique au router legacy.
"""
import sys
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from app.core.database import supabase

from app.modules.employee_exits.application.dto import (
    EmployeeExitApplicationError,
    build_exit_record,
    DOCUMENT_NAME_MAP,
    GENERATABLE_DOCUMENT_TYPES,
)
from app.modules.employee_exits.application.service import create_default_checklist_sync
from app.modules.employee_exits.domain.rules import get_initial_status, get_valid_status_transitions
from app.modules.employee_exits.infrastructure.queries import (
    get_employee_by_id,
    get_company_by_id,
    get_employee_full,
    get_exit_documents_storage_paths,
    update_employee_employment_status,
    get_employee_document_by_source_exit_document,
    insert_exit_document_publication,
    insert_employee_document,
    update_employee_document,
)
from app.modules.employee_exits.infrastructure.repository import (
    EmployeeExitRepository,
    ExitDocumentRepository,
    ExitChecklistRepository,
)
from app.modules.employee_exits.infrastructure.providers import (
    get_exit_document_generator,
    get_indemnity_calculator,
    get_exit_storage_provider,
)


def create_employee_exit(
    exit_data: Dict[str, Any],
    company_id: str,
    current_user_id: str,
    supabase_client: Any = None,
) -> Dict[str, Any]:
    """
    Crée une sortie : enregistrement, statut employé, checklist, calcul indemnités, génération 3 docs.
    Ne lève pas si calcul/génération échoue (log en stderr uniquement).
    """
    sb = supabase_client or supabase
    employee_id = str(exit_data["employee_id"])
    employee = get_employee_by_id(employee_id, sb)
    if not employee:
        raise EmployeeExitApplicationError(404, "Employé non trouvé")
    if employee["company_id"] != company_id:
        raise EmployeeExitApplicationError(404, "Employé non trouvé")
    if employee["employment_status"] in ("en_sortie", "parti"):
        raise EmployeeExitApplicationError(
            400,
            f"L'employé a déjà un processus de sortie actif (statut: {employee['employment_status']})",
        )

    exit_type = exit_data["exit_type"]
    initial_status = get_initial_status(exit_type)
    notice_start = None
    notice_end = None
    if exit_data.get("notice_period_days", 0) > 0 and not exit_data.get("is_gross_misconduct", False):
        exit_request_date = exit_data["exit_request_date"]
        notice_start = exit_request_date
        notice_end = exit_request_date + timedelta(days=exit_data["notice_period_days"])

    record = build_exit_record(
        company_id=company_id,
        employee_id=employee_id,
        exit_type=exit_type,
        initial_status=initial_status,
        exit_request_date=exit_data["exit_request_date"].isoformat() if hasattr(exit_data["exit_request_date"], "isoformat") else exit_data["exit_request_date"],
        last_working_day=exit_data["last_working_day"].isoformat() if hasattr(exit_data["last_working_day"], "isoformat") else exit_data["last_working_day"],
        notice_period_days=exit_data.get("notice_period_days", 0),
        is_gross_misconduct=exit_data.get("is_gross_misconduct", False),
        notice_indemnity_type=exit_data.get("notice_indemnity_type"),
        notice_start_date=notice_start.isoformat() if notice_start else None,
        notice_end_date=notice_end.isoformat() if notice_end else None,
        exit_reason=exit_data.get("exit_reason"),
        initiated_by=current_user_id,
    )
    exit_repo = EmployeeExitRepository(sb)
    created = exit_repo.create(record)
    exit_id = created["id"]
    print(f"✓ Sortie créée: {exit_id} (statut: {initial_status})", file=sys.stderr)

    update_employee_employment_status(employee_id, "en_sortie", exit_id, sb)
    print(f"✓ Employé {employee['first_name']} {employee['last_name']} marqué 'en_sortie'", file=sys.stderr)

    create_default_checklist_sync(exit_id, company_id, sb)

    try:
        _run_post_create_indemnities_and_docs(exit_id, company_id, current_user_id, sb)
    except Exception as e:
        print(f"⚠ Erreur lors du calcul automatique ou génération des documents: {e}", file=sys.stderr)
        if sys:
            import traceback
            traceback.print_exc()

    return created


def _run_post_create_indemnities_and_docs(exit_id: str, company_id: str, current_user_id: str, sb: Any) -> None:
    """Calcule les indemnités et génère les 3 documents après création. Utilise domain + infrastructure."""
    exit_repo = EmployeeExitRepository(sb)
    doc_repo = ExitDocumentRepository(sb)
    generator = get_exit_document_generator()
    calculator = get_indemnity_calculator()
    storage = get_exit_storage_provider(sb)
    company_data = get_company_by_id(company_id, sb) or {}

    print("[CREATE EXIT] Calcul automatique des indemnités...", file=sys.stderr)
    exit_full_data = exit_repo.get_with_employee(
        exit_id, company_id, "id, first_name, last_name, hire_date, salaire_de_base, job_title, date_naissance"
    )
    if not exit_full_data:
        return
    employee_full_data = exit_full_data.get("employees") or {}
    indemnities = calculator.calculate(employee_full_data, exit_full_data, sb)
    exit_repo.update(exit_id, company_id, {
        "calculated_indemnities": indemnities,
        "remaining_vacation_days": indemnities.get("indemnite_conges", {}).get("jours_restants", 0),
        "final_net_amount": indemnities.get("total_net_indemnities", 0),
    })
    print("✓ Indemnités calculées automatiquement", file=sys.stderr)

    print("[CREATE EXIT] Génération automatique des documents...", file=sys.stderr)
    for doc_type in ("certificat_travail", "attestation_pole_emploi", "solde_tout_compte"):
        try:
            if doc_type == "solde_tout_compte":
                pdf_bytes = generator.generate_solde_tout_compte(
                    employee_full_data, company_data, exit_full_data, indemnities, sb
                )
            elif doc_type == "certificat_travail":
                pdf_bytes = generator.generate_certificat_travail(
                    employee_full_data, company_data, exit_full_data
                )
            else:
                pdf_bytes = generator.generate_attestation_pole_emploi(
                    employee_full_data, company_data, exit_full_data
                )
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{doc_type}_{ts}.pdf"
            storage_path = f"exits/{exit_id}/{filename}"
            storage.upload(storage_path, pdf_bytes, "application/pdf")
            doc_repo.create({
                "exit_id": exit_id,
                "company_id": company_id,
                "document_type": doc_type,
                "document_category": "generated",
                "storage_path": storage_path,
                "filename": filename,
                "mime_type": "application/pdf",
                "file_size_bytes": len(pdf_bytes),
                "generation_template": f"template_{doc_type}",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "uploaded_by": current_user_id,
            })
            print(f"✓ {doc_type} généré", file=sys.stderr)
        except Exception as e:
            print(f"⚠ Erreur génération {doc_type}: {e}", file=sys.stderr)


def update_employee_exit(
    exit_id: str,
    company_id: str,
    update_data: Dict[str, Any],
    supabase_client: Any = None,
) -> Dict[str, Any]:
    """Met à jour une sortie. Retourne la ligne mise à jour."""
    sb = supabase_client or supabase
    exit_repo = EmployeeExitRepository(sb)
    existing = exit_repo.get_by_id(exit_id, company_id)
    if not existing:
        raise EmployeeExitApplicationError(404, "Sortie non trouvée")
    if not update_data:
        return existing
    updated = exit_repo.update(exit_id, company_id, update_data)
    return updated if updated is not None else existing


def update_exit_status(
    exit_id: str,
    company_id: str,
    new_status: str,
    notes: Optional[str],
    current_user_id: str,
    supabase_client: Any = None,
) -> Dict[str, Any]:
    """Met à jour le statut avec validation des transitions et règle 15j rupture."""
    sb = supabase_client or supabase
    exit_repo = EmployeeExitRepository(sb)
    exit_data = exit_repo.get_by_id(exit_id, company_id)
    if not exit_data:
        raise EmployeeExitApplicationError(404, "Sortie non trouvée")
    current_status = exit_data["status"]
    exit_type = exit_data["exit_type"]
    valid = get_valid_status_transitions(exit_type, current_status)
    if new_status not in valid:
        raise EmployeeExitApplicationError(
            400,
            f"Transition invalide de '{current_status}' vers '{new_status}'. Transitions valides: {', '.join(valid)}",
        )
    if exit_type == "rupture_conventionnelle" and current_status == "rupture_validee" and new_status == "rupture_effective":
        if exit_data.get("validation_date"):
            from datetime import datetime as dt
            vd = dt.fromisoformat(exit_data["validation_date"].replace("Z", "+00:00") if isinstance(exit_data["validation_date"], str) else exit_data["validation_date"])
            days = (datetime.now(timezone.utc) - vd).days
            if days < 15:
                raise EmployeeExitApplicationError(
                    400,
                    f"Période de rétractation de 15 jours non respectée (seulement {days} jours écoulés)",
                )
    update_payload = {"status": new_status}
    if new_status in ("rupture_validee", "licenciement_notifie"):
        update_payload["validated_by"] = current_user_id
        update_payload["validation_date"] = datetime.now(timezone.utc).isoformat()
    if new_status == "archivee":
        update_payload["archived_by"] = current_user_id
        update_payload["archived_at"] = datetime.now(timezone.utc).isoformat()
    if notes:
        exit_notes = exit_data.get("exit_notes") or {}
        exit_notes[new_status] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": current_user_id,
            "notes": notes,
        }
        update_payload["exit_notes"] = exit_notes
    updated = exit_repo.update(exit_id, company_id, update_payload)
    if new_status == "archivee":
        update_employee_employment_status(str(exit_data["employee_id"]), "parti", None, sb)
        print(f"✓ Employé {exit_data['employee_id']} marqué 'parti'", file=sys.stderr)
    return updated or exit_data


def delete_employee_exit(exit_id: str, company_id: str, supabase_client: Any = None) -> None:
    """Supprime la sortie, les fichiers storage associés, et remet l'employé en actif."""
    sb = supabase_client or supabase
    exit_repo = EmployeeExitRepository(sb)
    existing = exit_repo.get_by_id(exit_id, company_id)
    if not existing:
        raise EmployeeExitApplicationError(404, "Sortie non trouvée")
    employee_id = existing["employee_id"]
    paths = get_exit_documents_storage_paths(exit_id, company_id, sb)
    if paths:
        try:
            get_exit_storage_provider(sb).remove(paths)
            print(f"✓ {len(paths)} fichier(s) supprimé(s) du bucket exit_documents", file=sys.stderr)
        except Exception as e:
            print(f"⚠ Erreur suppression bucket: {e}", file=sys.stderr)
    exit_repo.delete(exit_id, company_id)
    update_employee_employment_status(str(employee_id), "actif", None, sb)
    print(f"✓ Sortie {exit_id} supprimée", file=sys.stderr)


def create_exit_document(
    exit_id: str,
    company_id: str,
    document_data: Dict[str, Any],
    current_user_id: str,
    supabase_client: Any = None,
) -> Dict[str, Any]:
    """Associe un document uploadé à une sortie."""
    sb = supabase_client or supabase
    exit_repo = EmployeeExitRepository(sb)
    doc_repo = ExitDocumentRepository(sb)
    if not exit_repo.get_by_id(exit_id, company_id):
        raise EmployeeExitApplicationError(404, "Sortie non trouvée")
    doc_record = {
        "exit_id": exit_id,
        "company_id": company_id,
        "document_type": document_data["document_type"],
        "document_category": "uploaded",
        "storage_path": document_data["storage_path"],
        "filename": document_data["filename"],
        "mime_type": document_data.get("mime_type"),
        "file_size_bytes": document_data.get("file_size_bytes"),
        "uploaded_by": current_user_id,
        "upload_notes": document_data.get("upload_notes"),
    }
    return doc_repo.create(doc_record)


def generate_exit_document(
    exit_id: str,
    company_id: str,
    document_type: str,
    current_user_id: str,
    supabase_client: Any = None,
) -> Dict[str, Any]:
    """Génère un document (certificat_travail, attestation_pole_emploi, solde_tout_compte) et l'enregistre."""
    if document_type not in GENERATABLE_DOCUMENT_TYPES:
        raise EmployeeExitApplicationError(400, f"Type de document non générable automatiquement: {document_type}")
    sb = supabase_client or supabase
    exit_repo = EmployeeExitRepository(sb)
    doc_repo = ExitDocumentRepository(sb)
    generator = get_exit_document_generator()
    storage = get_exit_storage_provider(sb)
    exit_data = exit_repo.get_with_employee(
        exit_id, company_id, "id, first_name, last_name, date_naissance, job_title, hire_date"
    )
    if not exit_data:
        raise EmployeeExitApplicationError(404, "Sortie non trouvée")
    employee_data = exit_data.get("employees") or {}
    company_data = get_company_by_id(company_id, sb)
    if not company_data:
        raise EmployeeExitApplicationError(404, "Entreprise non trouvée")
    if document_type == "certificat_travail":
        pdf_bytes = generator.generate_certificat_travail(employee_data, company_data, exit_data)
    elif document_type == "attestation_pole_emploi":
        pdf_bytes = generator.generate_attestation_pole_emploi(employee_data, company_data, exit_data)
    elif document_type == "solde_tout_compte":
        indemnities = exit_data.get("calculated_indemnities")
        if not indemnities or indemnities == {}:
            raise EmployeeExitApplicationError(
                400,
                "Les indemnités doivent être calculées avant de générer le solde de tout compte. Veuillez d'abord calculer les indemnités dans l'onglet 'Indemnités'.",
            )
        pdf_bytes = generator.generate_solde_tout_compte(employee_data, company_data, exit_data, indemnities, sb)
    else:
        raise EmployeeExitApplicationError(400, "Type de document non supporté")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{document_type}_{ts}.pdf"
    storage_path = f"exits/{exit_id}/{filename}"
    storage.upload(storage_path, pdf_bytes, "application/pdf")
    created = doc_repo.create({
        "exit_id": exit_id,
        "company_id": company_id,
        "document_type": document_type,
        "document_category": "generated",
        "storage_path": storage_path,
        "filename": filename,
        "mime_type": "application/pdf",
        "file_size_bytes": len(pdf_bytes),
        "generation_template": f"template_{document_type}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "uploaded_by": current_user_id,
    })
    return {
        "success": True,
        "message": f"Document {document_type} généré avec succès",
        "document_type": document_type,
        "document_id": created["id"],
        "filename": filename,
    }


def delete_exit_document(exit_id: str, document_id: str, company_id: str, supabase_client: Any = None) -> None:
    """Supprime un document (storage + enregistrement)."""
    sb = supabase_client or supabase
    doc_repo = ExitDocumentRepository(sb)
    storage = get_exit_storage_provider(sb)
    doc = doc_repo.get_by_id(document_id, exit_id, company_id)
    if not doc:
        raise EmployeeExitApplicationError(404, "Document non trouvé")
    try:
        storage.remove([doc["storage_path"]])
    except Exception:
        pass
    doc_repo.delete(document_id, exit_id, company_id)


def add_checklist_item(
    exit_id: str,
    company_id: str,
    item_data: Dict[str, Any],
    supabase_client: Any = None,
) -> Dict[str, Any]:
    """Ajoute un item personnalisé à la checklist."""
    sb = supabase_client or supabase
    exit_repo = EmployeeExitRepository(sb)
    checklist_repo = ExitChecklistRepository(sb)
    if not exit_repo.get_by_id(exit_id, company_id):
        raise EmployeeExitApplicationError(404, "Sortie non trouvée")
    item_record = {
        "exit_id": exit_id,
        "company_id": company_id,
        "item_code": item_data["item_code"],
        "item_label": item_data["item_label"],
        "item_description": item_data.get("item_description"),
        "item_category": item_data.get("item_category", "autre"),
        "is_required": item_data.get("is_required", True),
        "due_date": item_data.get("due_date").isoformat() if item_data.get("due_date") and hasattr(item_data.get("due_date"), "isoformat") else item_data.get("due_date"),
        "display_order": item_data.get("display_order", 0),
    }
    return checklist_repo.add_item(item_record)


def mark_checklist_item_complete(
    exit_id: str,
    item_id: str,
    company_id: str,
    item_update: Dict[str, Any],
    current_user_id: str,
    supabase_client: Any = None,
) -> Dict[str, Any]:
    """Marque un item comme complété ou non, et met à jour notes/due_date."""
    sb = supabase_client or supabase
    checklist_repo = ExitChecklistRepository(sb)
    item = checklist_repo.get_item(item_id, exit_id, company_id)
    if not item:
        raise EmployeeExitApplicationError(404, "Item de checklist non trouvé")
    update_data = {}
    if item_update.get("is_completed") is not None:
        update_data["is_completed"] = item_update["is_completed"]
        if item_update["is_completed"]:
            update_data["completed_by"] = current_user_id
            update_data["completed_at"] = datetime.now(timezone.utc).isoformat()
        else:
            update_data["completed_by"] = None
            update_data["completed_at"] = None
    if item_update.get("completion_notes") is not None:
        update_data["completion_notes"] = item_update["completion_notes"]
    if item_update.get("due_date") is not None:
        update_data["due_date"] = item_update["due_date"].isoformat() if hasattr(item_update["due_date"], "isoformat") else item_update["due_date"]
    if update_data:
        updated = checklist_repo.update_item(item_id, exit_id, company_id, update_data)
        return updated if updated is not None else item
    return item


def delete_checklist_item(exit_id: str, item_id: str, company_id: str, supabase_client: Any = None) -> None:
    """Supprime un item de checklist (non requis uniquement)."""
    sb = supabase_client or supabase
    checklist_repo = ExitChecklistRepository(sb)
    item = checklist_repo.get_item(item_id, exit_id, company_id)
    if not item:
        raise EmployeeExitApplicationError(404, "Item de checklist non trouvé")
    if item.get("is_required"):
        raise EmployeeExitApplicationError(400, "Impossible de supprimer un item obligatoire")
    checklist_repo.delete_item(item_id, exit_id, company_id)


def edit_exit_document(
    exit_id: str,
    document_id: str,
    company_id: str,
    edit_request: Dict[str, Any],
    current_user_id: str,
    supabase_client: Any = None,
) -> Dict[str, Any]:
    """Édite un document généré : fusion des données, régénération PDF, mise à jour version."""
    sb = supabase_client or supabase
    doc_repo = ExitDocumentRepository(sb)
    exit_repo = EmployeeExitRepository(sb)
    generator = get_exit_document_generator()
    storage = get_exit_storage_provider(sb)
    doc = doc_repo.get_by_id(document_id, exit_id, company_id)
    if not doc:
        raise EmployeeExitApplicationError(404, "Document non trouvé")
    if doc.get("document_category") != "generated":
        raise EmployeeExitApplicationError(400, "Seuls les documents générés automatiquement peuvent être édités")
    document_type = doc["document_type"]
    current_version = doc.get("version", 1)
    exit_data = exit_repo.get_by_id(exit_id, company_id)
    if not exit_data:
        raise EmployeeExitApplicationError(404, "Sortie non trouvée")
    emp_id = exit_data.get("employee_id")
    employee_data = get_employee_full(str(emp_id), sb) if emp_id else {}
    company_data = get_company_by_id(company_id, sb) or {}
    merged_data = {**doc.get("generation_data", {}), **edit_request.get("document_data", {})}
    gen_employee = {**employee_data, **merged_data.get("employee", {})}
    gen_company = {**company_data, **merged_data.get("company", {})}
    gen_exit = {**exit_data, **merged_data.get("exit", {})}
    if document_type == "certificat_travail":
        pdf_bytes = generator.generate_certificat_travail(gen_employee, gen_company, gen_exit)
    elif document_type == "attestation_pole_emploi":
        pdf_bytes = generator.generate_attestation_pole_emploi(gen_employee, gen_company, gen_exit)
    elif document_type == "solde_tout_compte":
        indemnities = merged_data.get("indemnities") or exit_data.get("calculated_indemnities", {})
        pdf_bytes = generator.generate_solde_tout_compte(gen_employee, gen_company, gen_exit, indemnities, sb)
    else:
        raise EmployeeExitApplicationError(400, f"Type de document non supporté pour l'édition: {document_type}")
    storage.upload(doc["storage_path"], pdf_bytes, "application/pdf")
    new_version = current_version + 1
    doc_repo.update(document_id, exit_id, company_id, {
        "document_data": merged_data,
        "version": new_version,
        "manually_edited": True,
        "last_edited_by": current_user_id,
        "last_edited_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    return {
        "success": True,
        "message": "Document édité avec succès",
        "document_id": document_id,
        "version": new_version,
        "edited_at": datetime.now(timezone.utc),
    }


def unpublish_exit_document(exit_id: str, document_id: str, company_id: str, supabase_client: Any = None) -> Dict[str, Any]:
    """Marque un document comme non publié (published_to_employee=False, etc.)."""
    sb = supabase_client or supabase
    doc_repo = ExitDocumentRepository(sb)
    doc = doc_repo.get_by_id(document_id, exit_id, company_id)
    if not doc:
        raise EmployeeExitApplicationError(404, "Document non trouvé")
    updated = doc_repo.update(document_id, exit_id, company_id, {
        "published_to_employee": False,
        "published_at": None,
        "published_by": None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    if updated is None:
        raise EmployeeExitApplicationError(500, "Échec de la dépublication du document")
    return updated


def publish_exit_documents(
    exit_id: str,
    company_id: str,
    document_ids: Optional[List[str]],
    force_update: bool,
    current_user_id: str,
    supabase_client: Any = None,
) -> Dict[str, Any]:
    """
    Publie des documents de sortie vers employee_documents (section autres).
    document_ids=None => tous les documents générés. Gère idempotence et force_update.
    """
    from uuid import UUID
    sb = supabase_client or supabase
    exit_repo = EmployeeExitRepository(sb)
    doc_repo = ExitDocumentRepository(sb)
    storage = get_exit_storage_provider(sb)
    exit_data = exit_repo.get_with_employee(exit_id, company_id, "id, first_name, last_name")
    if not exit_data:
        raise EmployeeExitApplicationError(404, "Sortie non trouvée")
    employee_id = exit_data["employee_id"]
    all_docs = doc_repo.list_by_exit(exit_id, company_id)
    if document_ids:
        documents = [d for d in all_docs if str(d["id"]) in document_ids]
    else:
        documents = [d for d in all_docs if d.get("document_category") == "generated"]
    if not documents:
        raise EmployeeExitApplicationError(404, "Aucun document trouvé à publier")
    published_docs = []
    total_published = total_updated = total_failed = total_already_published = 0
    for doc in documents:
        doc_status = {
            "exit_document_id": UUID(doc["id"]),
            "document_type": doc["document_type"],
            "filename": doc["filename"],
            "status": "failed",
            "employee_document_id": None,
            "url": None,
            "error_message": None,
            "published_at": None,
        }
        try:
            try:
                storage.create_signed_url(doc["storage_path"], 1)
            except Exception:
                doc_status["status"] = "file_missing"
                doc_status["error_message"] = "Le fichier n'existe pas dans le stockage"
                published_docs.append(doc_status)
                total_failed += 1
                continue
            existing = get_employee_document_by_source_exit_document(str(employee_id), doc["id"], sb)
            if existing and not force_update:
                doc_status["status"] = "already_published"
                doc_status["employee_document_id"] = UUID(existing["id"])
                doc_status["published_at"] = datetime.fromisoformat(existing["published_at"].replace("Z", "+00:00")) if existing.get("published_at") else None
                published_docs.append(doc_status)
                total_already_published += 1
                continue
            try:
                file_bytes = storage.download(doc["storage_path"])
            except Exception as e:
                raise Exception(f"Impossible de télécharger le fichier source: {str(e)}")
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest_path = f"employees/{employee_id}/documents/{doc['document_type']}_{ts}.pdf"
            storage.upload(dest_path, file_bytes, doc.get("mime_type", "application/pdf"))
            document_name = DOCUMENT_NAME_MAP.get(doc["document_type"], doc["filename"])
            if existing and force_update:
                update_employee_document(existing["id"], {
                    "storage_path": dest_path,
                    "filename": doc["filename"],
                    "file_size_bytes": doc.get("file_size_bytes"),
                    "mime_type": doc.get("mime_type"),
                    "published_by": current_user_id,
                    "published_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }, sb)
                employee_doc_id = existing["id"]
                status = "updated"
                total_updated += 1
            else:
                insert_data = {
                    "employee_id": str(employee_id),
                    "company_id": company_id,
                    "document_category": "autres",
                    "document_name": document_name,
                    "document_type": doc["document_type"],
                    "storage_path": dest_path,
                    "filename": doc["filename"],
                    "mime_type": doc.get("mime_type"),
                    "file_size_bytes": doc.get("file_size_bytes"),
                    "published_by": current_user_id,
                    "published_at": datetime.now(timezone.utc).isoformat(),
                    "source_exit_id": str(exit_id),
                    "source_exit_document_id": doc["id"],
                }
                inserted = insert_employee_document(insert_data, sb)
                employee_doc_id = inserted["id"]
                status = "published"
                total_published += 1
            insert_exit_document_publication(
                exit_id, doc["id"], str(employee_doc_id), company_id, str(employee_id),
                current_user_id, status, sb,
            )
            try:
                url = storage.create_signed_url(dest_path, 3600, download=True)
                doc_status["url"] = url
            except Exception:
                doc_status["url"] = None
            doc_status["status"] = status
            doc_status["employee_document_id"] = UUID(employee_doc_id)
            doc_status["published_at"] = datetime.now(timezone.utc)
            published_docs.append(doc_status)
        except Exception as e:
            doc_status["error_message"] = str(e)
            published_docs.append(doc_status)
            total_failed += 1
    return {
        "exit_id": UUID(exit_id),
        "employee_id": UUID(employee_id),
        "success": total_failed == 0,
        "documents": published_docs,
        "total_published": total_published,
        "total_updated": total_updated,
        "total_failed": total_failed,
        "total_already_published": total_already_published,
    }
