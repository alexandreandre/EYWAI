"""
Requêtes métier complexes : annual_reviews, employee_documents, URLs signées.

Utilise Supabase et le storage provider. Comportement identique au router legacy.
"""
from typing import Any, Dict, List, Optional

from app.core.database import supabase

from app.modules.employees.domain.interfaces import IAnnualReviewQuery
from app.modules.employees.infrastructure.providers import get_storage_provider


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
            .limit(1)
            .execute()
        )
        if not resp.data or len(resp.data) == 0:
            return None
        return dict(resp.data[0])


_annual_review_query = AnnualReviewQuery()


def get_annual_review_query() -> IAnnualReviewQuery:
    return _annual_review_query


def fetch_annual_review_for_employee(
    employee_id: str, company_id: str, year: int
) -> Optional[Dict[str, Any]]:
    """Entretien annuel d'un employé pour une année donnée."""
    return _annual_review_query.fetch_for_employee_year(
        employee_id, company_id, year
    )


def fetch_published_exit_documents(
    employee_id: str, company_id: str
) -> List[Dict[str, Any]]:
    """
    Documents de sortie publiés (employee_documents, category 'autres')
    avec URL signée pour chaque document. Comportement identique au router legacy.
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
    if not docs_response.data:
        return []
    storage = get_storage_provider()
    documents = []
    for doc in docs_response.data:
        try:
            url = storage.create_signed_url(
                "exit_documents",
                doc["storage_path"],
                expiry_seconds=3600,
                download=True,
            )
            if url:
                documents.append({
                    "id": doc["id"],
                    "name": doc.get("document_name", doc.get("filename", "Document")),
                    "url": url,
                    "date": doc.get("published_at", doc.get("created_at")),
                    "document_type": doc.get("document_type"),
                    "document_category": doc.get("document_category", "autres"),
                })
        except Exception as e:
            print(f"⚠ Erreur génération URL pour document {doc.get('id')}: {e}")
            continue
    return documents


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
