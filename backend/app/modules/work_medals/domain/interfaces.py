"""Ports persistance médailles du travail."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class AbstractWorkMedalSettingsRepository(ABC):
    @abstractmethod
    def get_by_company(self, company_id: str) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    def upsert(self, company_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        ...


class AbstractWorkMedalCasesRepository(ABC):
    @abstractmethod
    def list_by_company(
        self,
        company_id: str,
        *,
        status: str | None = None,
        statuses: List[str] | None = None,
        medal_level: str | None = None,
    ) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def list_by_employee(self, employee_id: str) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def get_by_id(self, case_id: str) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    def get_by_employee_level(
        self, employee_id: str, medal_level: str
    ) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    def insert(self, data: Dict[str, Any]) -> Dict[str, Any]:
        ...

    @abstractmethod
    def update(self, case_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        ...

    @abstractmethod
    def count_by_status(self, company_id: str, statuses: List[str]) -> int:
        ...
