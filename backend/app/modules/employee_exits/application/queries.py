"""
Requêtes (cas d'usage lecture) du module employee_exits.

Délèguent à domain + infrastructure. Comportement identique au router legacy.
"""

import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.database import supabase

from app.modules.employee_exits.application.dto import EmployeeExitApplicationError
from app.modules.employee_exits.application.service import (
    enrich_exit_with_documents_and_checklist,
)
from app.modules.employee_exits.infrastructure.mappers import (
    build_document_data_from_exit,
)
from app.modules.employee_exits.infrastructure.providers import (
    get_exit_storage_provider,
    get_indemnity_calculator,
)
from app.modules.employee_exits.infrastructure.queries import (
    get_company_by_id,
    get_employee_by_id as infra_get_employee_by_id,
    get_employee_full,
)
from app.modules.employee_exits.infrastructure.repository import (
    EmployeeExitRepository,
    ExitDocumentRepository,
    ExitChecklistRepository,
)


def get_employee_company_id(employee_id: str, supabase_client: Any = None) -> str:
    """Retourne le company_id d'un employé. Lève EmployeeExitApplicationError(404) si non trouvé."""
    sb = supabase_client or supabase
    employee = infra_get_employee_by_id(employee_id, sb)
    if not employee:
        raise EmployeeExitApplicationError(404, "Employé non trouvé")
    return str(employee["company_id"])


def list_employee_exits(
    company_id: str,
    status: Optional[str] = None,
    exit_type: Optional[str] = None,
    employee_id: Optional[str] = None,
    supabase_client: Any = None,
) -> List[Dict[str, Any]]:
    """Liste les sorties enrichies (documents, checklist, completion_rate)."""
    sb = supabase_client or supabase
    exit_repo = EmployeeExitRepository(sb)
    rows = exit_repo.list(
        company_id,
        status=status,
        exit_type=exit_type,
        employee_id=employee_id,
    )
    enriched = []
    for exit_record in rows:
        enrich_exit_with_documents_and_checklist(exit_record, 3600, sb)
        enriched.append(exit_record)
    return enriched


def get_employee_exit(
    exit_id: str,
    company_id: str,
    supabase_client: Any = None,
) -> Dict[str, Any]:
    """Récupère une sortie par id avec documents et checklist."""
    sb = supabase_client or supabase
    exit_repo = EmployeeExitRepository(sb)
    exit_record = exit_repo.get_with_employee(
        exit_id, company_id, "id, first_name, last_name, email, job_title, hire_date"
    )
    if not exit_record:
        raise EmployeeExitApplicationError(404, "Sortie non trouvée")
    enrich_exit_with_documents_and_checklist(exit_record, 3600, sb)
    return exit_record


def calculate_exit_indemnities(
    exit_id: str,
    company_id: str,
    supabase_client: Any = None,
) -> Dict[str, Any]:
    """Calcule les indemnités et met à jour l'enregistrement sortie. Retourne le dict indemnités."""
    sb = supabase_client or supabase
    exit_repo = EmployeeExitRepository(sb)
    calculator = get_indemnity_calculator()
    exit_data = exit_repo.get_with_employee(
        exit_id,
        company_id,
        "id, first_name, last_name, hire_date, salaire_de_base, job_title",
    )
    if not exit_data:
        raise EmployeeExitApplicationError(404, "Sortie non trouvée")
    employee_data = exit_data.get("employees") or {}
    try:
        indemnities = calculator.calculate(employee_data, exit_data, sb)
    except ImportError as e:
        raise EmployeeExitApplicationError(
            500, f"Module de calcul non disponible: {str(e)}"
        )
    except Exception as e:
        print(f"✗ Erreur calcul: {e}", file=sys.stderr)
        raise EmployeeExitApplicationError(
            500, f"Erreur lors du calcul des indemnités: {str(e)}"
        )
    exit_repo.update(
        exit_id,
        company_id,
        {
            "calculated_indemnities": indemnities,
            "remaining_vacation_days": indemnities.get("indemnite_conges", {}).get(
                "jours_restants", 0
            ),
            "final_net_amount": indemnities.get("total_net_indemnities", 0),
        },
    )
    return indemnities


def get_document_upload_url(
    exit_id: str,
    company_id: str,
    filename: str,
    supabase_client: Any = None,
) -> Dict[str, Any]:
    """Génère une URL signée pour upload. Retourne upload_url, storage_path, expires_in."""
    sb = supabase_client or supabase
    exit_repo = EmployeeExitRepository(sb)
    if not exit_repo.get_by_id(exit_id, company_id):
        raise EmployeeExitApplicationError(404, "Sortie non trouvée")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    storage_path = f"exits/{exit_id}/{ts}_{filename}"
    try:
        upload_url = get_exit_storage_provider(sb).create_signed_upload_url(
            storage_path
        )
        return {
            "upload_url": upload_url,
            "storage_path": storage_path,
            "expires_in": 3600,
        }
    except Exception as e:
        print(f"✗ Erreur génération URL upload: {e}", file=sys.stderr)
        raise EmployeeExitApplicationError(500, f"Erreur génération URL: {str(e)}")


def list_exit_documents(
    exit_id: str,
    company_id: str,
    supabase_client: Any = None,
) -> List[Dict[str, Any]]:
    """Liste les documents d'une sortie avec download_url."""
    sb = supabase_client or supabase
    doc_repo = ExitDocumentRepository(sb)
    storage = get_exit_storage_provider(sb)
    documents = doc_repo.list_by_exit(exit_id, company_id)
    for doc in documents:
        try:
            doc["download_url"] = storage.create_signed_url(doc["storage_path"], 3600)
        except Exception:
            doc["download_url"] = None
    return documents


def get_exit_document_details(
    exit_id: str,
    document_id: str,
    company_id: str,
    supabase_client: Any = None,
) -> Dict[str, Any]:
    """Détails complets d'un document avec document_data (éditable) et download_url."""
    sb = supabase_client or supabase
    doc_repo = ExitDocumentRepository(sb)
    exit_repo = EmployeeExitRepository(sb)
    storage = get_exit_storage_provider(sb)
    doc = doc_repo.get_by_id(document_id, exit_id, company_id)
    if not doc:
        raise EmployeeExitApplicationError(404, "Document non trouvé")
    document_data = doc.get("document_data") or doc.get("generation_data")
    if not document_data:
        exit_data = exit_repo.get_by_id(exit_id, company_id)
        if not exit_data:
            raise EmployeeExitApplicationError(404, "Sortie non trouvée")
        emp_id = exit_data.get("employee_id")
        employee_data = get_employee_full(str(emp_id), sb) if emp_id else {}
        company_data = get_company_by_id(company_id, sb) or {}
        document_data = build_document_data_from_exit(
            employee_data,
            company_data,
            exit_data,
            include_indemnities=(doc.get("document_type") == "solde_tout_compte"),
        )
    edit_history = []
    download_url = None
    if doc.get("storage_path"):
        try:
            download_url = storage.create_signed_url(doc["storage_path"], 3600)
        except Exception as e:
            print(f"⚠ Erreur génération URL signée: {e}", file=sys.stderr)
    result = dict(doc)
    result["document_data"] = document_data
    result["edit_history"] = edit_history if edit_history else None
    result["download_url"] = download_url
    result.setdefault("version", 1)
    result.setdefault("manually_edited", False)
    result.setdefault("last_edited_by", None)
    result.setdefault("last_edited_at", None)
    return result


def get_document_edit_history(
    exit_id: str,
    document_id: str,
    company_id: str,
    supabase_client: Any = None,
) -> Dict[str, Any]:
    """Historique des modifications d'un document (métadonnées)."""
    sb = supabase_client or supabase
    doc_repo = ExitDocumentRepository(sb)
    doc = doc_repo.get_by_id(document_id, exit_id, company_id)
    if not doc:
        raise EmployeeExitApplicationError(404, "Document non trouvé")
    history = []
    if doc.get("manually_edited") and doc.get("last_edited_at"):
        history.append(
            {
                "version": doc.get("version", 1),
                "edited_by": doc.get("last_edited_by"),
                "edited_at": doc.get("last_edited_at"),
                "changes_summary": "Document modifié",
            }
        )
    return {
        "document_id": document_id,
        "total_versions": doc.get("version", 1),
        "history": history,
    }


def get_exit_checklist(
    exit_id: str,
    company_id: str,
    supabase_client: Any = None,
) -> List[Dict[str, Any]]:
    """Récupère la checklist d'une sortie (ordre display_order)."""
    sb = supabase_client or supabase
    checklist_repo = ExitChecklistRepository(sb)
    return checklist_repo.list_by_exit(exit_id, company_id)
