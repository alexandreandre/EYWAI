"""
Requêtes métier complexes (enrichissement, jointures, lectures multi-tables).

Comportement identique à api/routers/employee_exits.py et application/service.py.
Aucune dépendance FastAPI.
"""

from typing import Any, Dict, List, Optional

from app.core.database import supabase


def enrich_exit_with_documents_and_checklist(
    exit_record: Dict[str, Any],
    signed_url_expiry_seconds: int = 3600,
    supabase_client: Any = None,
) -> None:
    """
    Enrichit sur place une sortie avec documents (download_url), checklist_items, checklist_completion_rate.
    Remplace la clé 'employees' par 'employee'. Comportement identique au router.
    """
    sb = supabase_client or supabase
    exit_id = exit_record["id"]
    docs_response = (
        sb.table("exit_documents").select("*").eq("exit_id", exit_id).execute()
    )
    documents = docs_response.data or []
    for doc in documents:
        try:
            signed_url_response = sb.storage.from_("exit_documents").create_signed_url(
                doc["storage_path"], signed_url_expiry_seconds
            )
            doc["download_url"] = (
                signed_url_response.get("signedURL")
                if isinstance(signed_url_response, dict)
                else signed_url_response
            )
        except Exception:
            doc["download_url"] = None
    exit_record["documents"] = documents

    checklist_response = (
        sb.table("exit_checklist_items")
        .select("*")
        .eq("exit_id", exit_id)
        .order("display_order")
        .execute()
    )
    exit_record["checklist_items"] = checklist_response.data or []

    if exit_record["checklist_items"]:
        completed = sum(
            1 for item in exit_record["checklist_items"] if item.get("is_completed")
        )
        total = len(exit_record["checklist_items"])
        exit_record["checklist_completion_rate"] = (completed / total) * 100
    else:
        exit_record["checklist_completion_rate"] = 0.0

    if exit_record.get("employees") is not None:
        exit_record["employee"] = exit_record.pop("employees")


def get_employee_by_id(
    employee_id: str, supabase_client: Any = None
) -> Optional[Dict[str, Any]]:
    """Récupère un employé par id (colonnes de base). Retourne None si non trouvé."""
    sb = supabase_client or supabase
    r = (
        sb.table("employees")
        .select("id, company_id, employment_status, first_name, last_name")
        .eq("id", employee_id)
        .maybe_single()
        .execute()
    )
    return r.data if r.data else None


def get_employee_full(
    employee_id: str, supabase_client: Any = None
) -> Optional[Dict[str, Any]]:
    """Récupère un employé avec toutes les colonnes."""
    sb = supabase_client or supabase
    r = sb.table("employees").select("*").eq("id", employee_id).maybe_single().execute()
    return r.data if r.data else None


def get_company_by_id(
    company_id: str, supabase_client: Any = None
) -> Optional[Dict[str, Any]]:
    """Récupère une entreprise par id."""
    sb = supabase_client or supabase
    r = sb.table("companies").select("*").eq("id", company_id).maybe_single().execute()
    return r.data if r.data else None


def get_exit_documents_storage_paths(
    exit_id: str, company_id: str, supabase_client: Any = None
) -> List[str]:
    """Liste les storage_path des documents d'une sortie (pour suppression bucket)."""
    sb = supabase_client or supabase
    r = (
        sb.table("exit_documents")
        .select("storage_path")
        .eq("exit_id", exit_id)
        .eq("company_id", company_id)
        .execute()
    )
    return [d["storage_path"] for d in (r.data or []) if d.get("storage_path")]


def update_employee_employment_status(
    employee_id: str,
    employment_status: str,
    current_exit_id: Optional[str] = None,
    supabase_client: Any = None,
) -> None:
    """Met à jour employment_status et current_exit_id d'un employé."""
    sb = supabase_client or supabase
    payload = {"employment_status": employment_status}
    if current_exit_id is not None:
        payload["current_exit_id"] = current_exit_id
    sb.table("employees").update(payload).eq("id", employee_id).execute()


def insert_exit_document_publication(
    exit_id: str,
    exit_document_id: str,
    employee_document_id: str,
    company_id: str,
    employee_id: str,
    published_by: str,
    status: str,
    supabase_client: Any = None,
) -> None:
    """Insère une ligne dans exit_document_publications (audit)."""
    sb = supabase_client or supabase
    from datetime import datetime, timezone

    sb.table("exit_document_publications").insert(
        {
            "exit_id": str(exit_id),
            "exit_document_id": exit_document_id,
            "employee_document_id": employee_document_id,
            "company_id": company_id,
            "employee_id": str(employee_id),
            "published_by": published_by,
            "published_at": datetime.now(timezone.utc).isoformat(),
            "status": status,
        }
    ).execute()


def get_employee_document_by_source_exit_document(
    employee_id: str, source_exit_document_id: str, supabase_client: Any = None
) -> Optional[Dict[str, Any]]:
    """Récupère l'enregistrement employee_documents lié à un document de sortie (idempotence)."""
    sb = supabase_client or supabase
    r = (
        sb.table("employee_documents")
        .select("id, published_at")
        .eq("employee_id", str(employee_id))
        .eq("source_exit_document_id", source_exit_document_id)
        .maybe_single()
        .execute()
    )
    return r.data if r.data else None


def insert_employee_document(
    data: Dict[str, Any], supabase_client: Any = None
) -> Dict[str, Any]:
    """Insère un enregistrement dans employee_documents. Retourne la ligne insérée."""
    sb = supabase_client or supabase
    resp = sb.table("employee_documents").insert(data).execute()
    if not resp.data:
        raise RuntimeError("Échec de l'insertion employee_documents")
    return resp.data[0] if isinstance(resp.data, list) else resp.data


def update_employee_document(
    document_id: str, data: Dict[str, Any], supabase_client: Any = None
) -> Optional[Dict[str, Any]]:
    """Met à jour un enregistrement employee_documents."""
    sb = supabase_client or supabase
    resp = sb.table("employee_documents").update(data).eq("id", document_id).execute()
    if not resp.data:
        return None
    return resp.data[0] if isinstance(resp.data, list) else resp.data
