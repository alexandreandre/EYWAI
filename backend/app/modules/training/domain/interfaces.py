"""Port persistance formations & inscriptions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class AbstractTrainingRepository(ABC):
    """Accès tables training_catalog et training_enrollments."""

    @abstractmethod
    def get_all_trainings(
        self, company_id: str, include_archived: bool = False
    ) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def get_training_by_id(self, training_id: str, company_id: str) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    def create_training(self, company_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        ...

    @abstractmethod
    def update_training(
        self, training_id: str, company_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        ...

    @abstractmethod
    def archive_training(self, training_id: str, company_id: str) -> None:
        ...

    @abstractmethod
    def count_active_enrollments_for_training(
        self, training_id: str, company_id: str
    ) -> int:
        ...

    @abstractmethod
    def get_enrollments(
        self,
        company_id: str,
        training_id: Optional[str] = None,
        employee_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def get_enrollment_by_id(
        self, enrollment_id: str, company_id: str
    ) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    def create_enrollment(self, company_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        ...

    @abstractmethod
    def update_enrollment(
        self, enrollment_id: str, company_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        ...

    @abstractmethod
    def cancel_enrollment(self, enrollment_id: str, company_id: str) -> None:
        ...

    @abstractmethod
    def has_active_enrollment_duplicate(
        self, company_id: str, training_id: str, employee_id: str
    ) -> bool:
        ...

    @abstractmethod
    def get_total_consumed(self, company_id: str, year: int) -> float:
        ...

    @abstractmethod
    def get_employee_id_for_user(self, user_id: str, company_id: str) -> Optional[str]:
        ...

    @abstractmethod
    def create_enrollment_request(
        self,
        employee_id: str,
        company_id: str,
        training_id: str,
        requested_by: str,
        preferred_date: Optional[str],
        motivation: Optional[str],
    ) -> Dict[str, Any]:
        ...

    @abstractmethod
    def approve_by_rh(
        self,
        enrollment_id: str,
        company_id: str,
        approved: bool,
        rejection_reason: Optional[str],
        planned_start_date: Optional[str],
        planned_end_date: Optional[str],
    ) -> Dict[str, Any]:
        ...

    @abstractmethod
    def list_pending_rh_approval(self, company_id: str) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def submit_evaluation(
        self,
        enrollment_id: str,
        company_id: str,
        actor_employee_id: Optional[str],
        rating: int,
        comment: Optional[str],
    ) -> Dict[str, Any]:
        ...

    @abstractmethod
    def upload_enrollment_certificate(
        self,
        enrollment_id: str,
        company_id: str,
        file_bytes: bytes,
        filename: str,
        content_type: str,
    ) -> str:
        ...

    @abstractmethod
    def get_evaluations_summary(self, company_id: str) -> List[Dict[str, Any]]:
        ...
