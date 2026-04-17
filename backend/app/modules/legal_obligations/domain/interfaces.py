"""Port persistance obligations légales."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class AbstractLegalObligationsRepository(ABC):
    """Accès employés, entretiens, overrides et agrégations."""

    @abstractmethod
    def get_active_employees(self, company_id: str) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def get_employee_row(self, company_id: str, employee_id: str) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    def get_completed_reviews_for_company(self, company_id: str) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def get_overrides_for_company(self, company_id: str) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def upsert_override(
        self,
        company_id: str,
        employee_id: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        ...

    @abstractmethod
    def get_employee_id_for_user(self, user_id: str, company_id: str) -> Optional[str]:
        ...
