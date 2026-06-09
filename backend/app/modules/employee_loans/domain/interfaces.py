"""Ports du domaine prêts employeur."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class AbstractEmployeeLoansRepository(ABC):
    @abstractmethod
    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        ...

    @abstractmethod
    def get_by_id(self, loan_id: str) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    def update(self, loan_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    def delete(self, loan_id: str) -> None:
        ...

    @abstractmethod
    def list_(
        self,
        company_id: str,
        *,
        employee_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        ...


class AbstractEmployeeLoanInstallmentsRepository(ABC):
    @abstractmethod
    def bulk_create(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def list_by_loan(self, loan_id: str) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def get_for_period(
        self, loan_id: str, year: int, month: int
    ) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    def update(self, installment_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        ...


class AbstractEmployeeLoanRepaymentsRepository(ABC):
    @abstractmethod
    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        ...

    @abstractmethod
    def list_by_loan(self, loan_id: str) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def get_existing(
        self, loan_id: str, payslip_id: str
    ) -> Optional[Dict[str, Any]]:
        ...
