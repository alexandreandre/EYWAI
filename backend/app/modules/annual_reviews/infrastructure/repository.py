"""
Repository annual_reviews : implémentation IAnnualReviewRepository.

Délègue l'exécution DB à infrastructure/queries.py. Comportement identique au legacy.
"""

from typing import Any, Dict, List, Optional

from app.modules.annual_reviews.domain.interfaces import IAnnualReviewRepository
from app.modules.annual_reviews.infrastructure import queries as infra_queries


class SupabaseAnnualReviewRepository(IAnnualReviewRepository):
    """Implémentation Supabase pour annual_reviews (DB via queries)."""

    def list_by_company(
        self,
        company_id: str,
        year: Optional[int] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return infra_queries.query_list_by_company(company_id, year=year, status=status)

    def get_by_id(self, review_id: str) -> Optional[Dict[str, Any]]:
        return infra_queries.query_get_by_id(review_id)

    def list_by_employee(
        self, employee_id: str, company_id: str
    ) -> List[Dict[str, Any]]:
        return infra_queries.query_list_by_employee(employee_id, company_id)

    def get_my_current(
        self, employee_id: str, company_id: str, year: int
    ) -> Optional[Dict[str, Any]]:
        return infra_queries.query_get_my_current(employee_id, company_id, year)

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return infra_queries.query_insert(data)

    def update(self, review_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return infra_queries.query_update(review_id, data)

    def delete(self, review_id: str) -> None:
        infra_queries.query_delete(review_id)

    def get_employee_company_id(self, employee_id: str) -> Optional[str]:
        return infra_queries.query_employee_company_id(employee_id)

    def get_employee_by_id(self, employee_id: str) -> Optional[Dict[str, Any]]:
        return infra_queries.query_employee_by_id(employee_id)

    def get_company_by_id(self, company_id: str) -> Optional[Dict[str, Any]]:
        return infra_queries.query_company_by_id(company_id)


annual_review_repository: IAnnualReviewRepository = SupabaseAnnualReviewRepository()
