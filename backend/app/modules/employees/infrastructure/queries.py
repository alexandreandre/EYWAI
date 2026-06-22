"""
Requêtes métier complexes : annual_reviews, employee_documents, URLs signées.

Utilise Supabase et le storage provider. Comportement identique au router legacy.
"""
from app.core.logging import get_logger

from typing import Any, Dict, List, Optional

from app.core.database import supabase

from app.modules.employees.domain.interfaces import IAnnualReviewQuery
from app.modules.employees.infrastructure.providers import get_storage_provider


logger = get_logger("modules.employees.infrastructure.queries")

class AnnualReviewQuery(IAnnualReviewQuery):
    """Implémentation Supabase de IAnnualReviewQuery (table annual_reviews)."""

    def fetch_for_employee_year(
        self, employee_id: str, company_id: str, year: int
    ) -> Optional[Dict[str, Any]]:
        resp = (
            supabase.table("annual_reviews")
            .select("status, planned_date, completed_date")
            .eq("employee_id", employee_id)
            .eq("company_id", company_id)
            .eq("year", year)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if not resp.data or len(resp.data) == 0:
            return None
        return dict(resp.data[0])


_annual_review_query = AnnualReviewQuery()


def fetch_exit_summary_for_employee(
    exit_id: str, company_id: str
) -> Optional[Dict[str, Any]]:
    """Résumé du départ lié à un collaborateur (pour enrichissement fiche RH)."""
    if not exit_id or not company_id:
        return None
    try:
        resp = (
            supabase.table("employee_exits")
            .select("id, exit_type, status, last_working_day")
            .eq("id", exit_id)
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        return dict(resp.data) if resp.data else None
    except Exception:
        logger.exception("Exception")
        return None


def get_annual_review_query() -> IAnnualReviewQuery:
    return _annual_review_query


def fetch_annual_review_for_employee(
    employee_id: str, company_id: str, year: int
) -> Optional[Dict[str, Any]]:
    """Entretien annuel d'un employé pour une année donnée."""
    return _annual_review_query.fetch_for_employee_year(employee_id, company_id, year)


def _storage_signed_urls(
    bucket: str, path: str, *, expiry_seconds: int = 3600
) -> tuple[Optional[str], Optional[str]]:
    storage = get_storage_provider()
    return (
        storage.create_signed_url(
            bucket, path, expiry_seconds=expiry_seconds, download=True
        ),
        storage.create_signed_url(
            bucket, path, expiry_seconds=expiry_seconds, download=False
        ),
    )


def _exit_document_display_name(doc: Dict[str, Any]) -> str:
    from app.modules.employee_exits.infrastructure.mappers import DOCUMENT_NAME_MAP

    doc_type = str(doc.get("document_type") or "")
    return DOCUMENT_NAME_MAP.get(doc_type, doc.get("filename") or "Document")


def _fetch_active_exit_procedure_documents(
    employee_id: str,
    company_id: str,
    *,
    exclude_exit_document_ids: set[str],
) -> List[Dict[str, Any]]:
    """
    Documents générés dans la procédure de départ en cours, visibles dès son ouverture
    (sans attendre une publication RH explicite).
    """
    emp_resp = (
        supabase.table("employees")
        .select("employment_status, current_exit_id")
        .eq("id", employee_id)
        .eq("company_id", company_id)
        .maybe_single()
        .execute()
    )
    emp = emp_resp.data if emp_resp else None
    if not emp:
        return []
    if str(emp.get("employment_status") or "").lower() != "en_sortie":
        return []
    exit_id = emp.get("current_exit_id")
    if not exit_id:
        return []

    exit_docs_resp = (
        supabase.table("exit_documents")
        .select("*")
        .eq("exit_id", str(exit_id))
        .eq("company_id", company_id)
        .eq("document_category", "generated")
        .order("generated_at", desc=True)
        .execute()
    )
    documents: List[Dict[str, Any]] = []
    for doc in exit_docs_resp.data or []:
        doc_id = str(doc.get("id") or "")
        if not doc_id or doc_id in exclude_exit_document_ids:
            continue
        storage_path = doc.get("storage_path")
        if not storage_path:
            continue
        try:
            download_url, preview_url = _storage_signed_urls(
                "exit_documents", storage_path
            )
            if not download_url:
                continue
            documents.append(
                {
                    "id": doc_id,
                    "name": _exit_document_display_name(doc),
                    "url": download_url,
                    "preview_url": preview_url or download_url,
                    "date": doc.get("generated_at", doc.get("created_at")),
                    "document_type": doc.get("document_type"),
                    "document_category": "autres",
                    "is_published": False,
                }
            )
        except Exception as e:
            logger.warning(
                f"⚠ Erreur génération URL pour document de sortie {doc_id}: {e}"
            )
            continue
    return documents


def fetch_published_exit_documents(
    employee_id: str, company_id: str
) -> List[Dict[str, Any]]:
    """
    Documents de sortie pour l'espace employé :
    - publiés dans employee_documents ;
    - plus, pendant une procédure en cours (statut en_sortie), les documents générés
      dès l'ouverture du départ (sans attendre le dernier jour travaillé).
    """
    docs_response = (
        supabase.table("employee_documents")
        .select("*")
        .eq("employee_id", employee_id)
        .eq("company_id", company_id)
        .eq("document_category", "autres")
        .order("published_at", desc=True)
        .execute()
    )
    documents: List[Dict[str, Any]] = []
    published_exit_document_ids: set[str] = set()
    for doc in docs_response.data or []:
        source_exit_doc_id = doc.get("source_exit_document_id")
        if source_exit_doc_id:
            published_exit_document_ids.add(str(source_exit_doc_id))
        try:
            download_url, preview_url = _storage_signed_urls(
                "exit_documents", doc["storage_path"]
            )
            if download_url:
                documents.append(
                    {
                        "id": doc["id"],
                        "name": doc.get(
                            "document_name", doc.get("filename", "Document")
                        ),
                        "url": download_url,
                        "preview_url": preview_url or download_url,
                        "date": doc.get("published_at", doc.get("created_at")),
                        "document_type": doc.get("document_type"),
                        "document_category": doc.get("document_category", "autres"),
                        "is_published": True,
                    }
                )
        except Exception as e:
            logger.warning(f"⚠ Erreur génération URL pour document {doc.get('id')}: {e}")
            continue

    procedure_docs = _fetch_active_exit_procedure_documents(
        employee_id,
        company_id,
        exclude_exit_document_ids=published_exit_document_ids,
    )
    documents.extend(procedure_docs)
    return documents


def _employee_id_from_row_response(res: Any) -> Optional[str]:
    if res and res.data and res.data.get("id"):
        return str(res.data["id"])
    return None


def _resolve_employee_id_by_auth_email(user_id: str, company_id: str) -> Optional[str]:
    """Dernier recours : même e-mail Auth que la fiche employees."""
    try:
        auth_user = supabase.auth.admin.get_user_by_id(str(user_id))
        email = (
            (auth_user.user.email or "").strip().lower()
            if auth_user and auth_user.user
            else ""
        )
    except Exception:
        logger.debug("resolve_employee: email auth indisponible pour %s", user_id)
        return None
    if not email:
        return None
    res = (
        supabase.table("employees")
        .select("id")
        .eq("company_id", str(company_id))
        .ilike("email", email)
        .maybe_single()
        .execute()
    )
    return _employee_id_from_row_response(res)


def resolve_employee_id_for_user_account(
    user_id: str, company_id: str
) -> Optional[str]:
    """
    Résout l'id employé pour un compte utilisateur dans une entreprise.

    - Liaison explicite via employees.user_id
    - Sinon employees.id == user_id (convention à la création : id = uid auth)
    - Sinon même e-mail que le compte Auth (fiches sans user_id renseigné)
    """
    uid = str(user_id)
    cid = str(company_id)

    by_user_id = (
        supabase.table("employees")
        .select("id")
        .eq("user_id", uid)
        .eq("company_id", cid)
        .maybe_single()
        .execute()
    )
    found = _employee_id_from_row_response(by_user_id)
    if found:
        return found

    by_primary_id = (
        supabase.table("employees")
        .select("id")
        .eq("id", uid)
        .eq("company_id", cid)
        .maybe_single()
        .execute()
    )
    found = _employee_id_from_row_response(by_primary_id)
    if found:
        return found

    return _resolve_employee_id_by_auth_email(uid, cid)


def get_employee_company_id(employee_id: str) -> Optional[str]:
    """Retourne le company_id d'un employé (pour les URLs storage)."""
    response = (
        supabase.table("employees")
        .select("company_id")
        .eq("id", employee_id)
        .single()
        .execute()
    )
    if not response.data:
        return None
    return response.data.get("company_id")


def get_company_id_for_user_from_profile(user_id: str) -> Optional[str]:
    """Retourne le company_id du profil utilisateur (créateur d'employé)."""
    response = (
        supabase.table("profiles")
        .select("company_id")
        .eq("id", str(user_id))
        .single()
        .execute()
    )
    if not response.data:
        return None
    return response.data.get("company_id")
