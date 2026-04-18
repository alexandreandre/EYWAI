"""Port persistance compétences."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class AbstractCompetenciesRepository(ABC):
    """Tables competency_referential, employee_competencies."""

    @abstractmethod
    def get_employee_id_for_user(self, user_id: str, company_id: str) -> Optional[str]:
        ...

    @abstractmethod
    def get_employee_row(self, employee_id: str, company_id: str) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    def get_all_refs(self, company_id: str, include_archived: bool = False) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def get_ref_by_id(self, ref_id: str, company_id: str) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    def create_ref(self, company_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        ...

    @abstractmethod
    def update_ref(self, ref_id: str, company_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        ...

    @abstractmethod
    def archive_ref(self, ref_id: str, company_id: str) -> None:
        ...

    @abstractmethod
    def count_evaluations_for_competency(self, competency_id: str, company_id: str) -> int:
        ...

    @abstractmethod
    def get_all_evaluations(
        self,
        company_id: str,
        employee_id: Optional[str] = None,
        competency_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def get_evaluation_by_id(
        self, evaluation_id: str, company_id: str
    ) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    def insert_evaluation(self, company_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        ...

    @abstractmethod
    def get_latest_evaluations(
        self, company_id: str, employee_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def get_matrix_payload(
        self,
        company_id: str,
        service_id: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        ...

    @abstractmethod
    def get_trainings_by_competency_ids(
        self, company_id: str, competency_ids: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        ...
