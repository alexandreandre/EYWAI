"""Port persistance objectifs & KPI."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class AbstractObjectivesRepository(ABC):
    """Accès tables employee_objectives, objective_milestones, objective_checkins."""

    @abstractmethod
    def list_services(self, company_id: str) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def create_service(self, company_id: str, name: str) -> Dict[str, Any]:
        ...

    @abstractmethod
    def get_all(
        self,
        company_id: str,
        employee_id: Optional[str] = None,
        service_id: Optional[str] = None,
        period_year: Optional[int] = None,
        status: Optional[str] = None,
        include_inactive_employees: bool = False,
    ) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def get_by_id(self, objective_id: str, company_id: str) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    def create(
        self, company_id: str, payload: Dict[str, Any], created_by: str
    ) -> Dict[str, Any]:
        ...

    @abstractmethod
    def update(
        self,
        objective_id: str,
        company_id: str,
        payload: Dict[str, Any],
        last_modified_by: str,
    ) -> Dict[str, Any]:
        ...

    @abstractmethod
    def cancel(self, objective_id: str, company_id: str) -> None:
        ...

    @abstractmethod
    def evaluate(
        self, objective_id: str, company_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        ...

    @abstractmethod
    def decline_to_team(
        self,
        parent_id: str,
        company_id: str,
        employee_ids: List[str],
        created_by: str,
    ) -> int:
        ...

    @abstractmethod
    def add_milestone(
        self, objective_id: str, company_id: str, payload: Dict[str, Any], updated_by: str
    ) -> Dict[str, Any]:
        ...

    @abstractmethod
    def update_milestone(
        self,
        objective_id: str,
        milestone_id: str,
        company_id: str,
        payload: Dict[str, Any],
        updated_by: str,
    ) -> Dict[str, Any]:
        ...

    @abstractmethod
    def delete_milestone(
        self, objective_id: str, milestone_id: str, company_id: str
    ) -> None:
        ...

    @abstractmethod
    def add_checkin(
        self, objective_id: str, company_id: str, payload: Dict[str, Any], updated_by: str
    ) -> Dict[str, Any]:
        ...

    @abstractmethod
    def get_total_weight(
        self,
        company_id: str,
        employee_id: str,
        period_year: int,
        exclude_objective_id: Optional[str] = None,
    ) -> float:
        ...

    @abstractmethod
    def get_achievement_rate(self, company_id: str, period_year: int) -> Optional[float]:
        ...

    @abstractmethod
    def get_previous_year_rows(
        self, company_id: str, employee_id: str, reference_period_year: int
    ) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def get_employee_id_for_user(self, user_id: str, company_id: str) -> Optional[str]:
        ...

    @abstractmethod
    def get_active_employee_ids_for_service(
        self, company_id: str, service_id: str
    ) -> List[str]:
        ...
