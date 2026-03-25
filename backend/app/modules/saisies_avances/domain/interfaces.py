"""
Ports (interfaces) du domaine saisies et avances.

Implémentations dans infrastructure/. Aucune dépendance FastAPI ni DB ici.
"""
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any, Dict, List, Optional


class ISeizureRepository(ABC):
    """Accès à la table salary_seizures (CRUD + listes filtrées)."""

    @abstractmethod
    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        ...

    @abstractmethod
    def get_by_id(self, seizure_id: str) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    def list_(self, employee_id: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def update(self, seizure_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    def delete(self, seizure_id: str) -> None:
        ...


class IAdvanceRepository(ABC):
    """Accès à la table salary_advances (CRUD + listes filtrées)."""

    @abstractmethod
    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        ...

    @abstractmethod
    def get_by_id(self, advance_id: str) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    def list_(self, employee_id: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def update(self, advance_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        ...


class IAdvancePaymentRepository(ABC):
    """Accès à la table salary_advance_payments."""

    @abstractmethod
    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        ...

    @abstractmethod
    def list_by_advance_id(self, advance_id: str) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def get_total_paid_by_advance_id(self, advance_id: str) -> Decimal:
        ...

    @abstractmethod
    def delete(self, payment_id: str) -> None:
        ...


class ISeizuresAdvancesCalculator(ABC):
    """
    Calculs métier : quotité saisissable, avances à rembourser, déductions.
    Implémentation actuelle : services.saisies_avances_calculator (legacy).
    """

    @abstractmethod
    def calculate_seizable_amount(self, net_salary: Decimal, dependents_count: int = 0) -> Decimal:
        ...

    @abstractmethod
    def apply_priority_order(self, seizures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def calculate_advance_available(
        self, employee_id: str, year: int, month: int, daily_salary: Optional[Decimal] = None
    ) -> Dict[str, Any]:
        ...

    @abstractmethod
    def get_seizures_for_period(self, employee_id: str, year: int, month: int) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def get_advances_to_repay(self, employee_id: str, year: int, month: int) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def calculate_seizure_deduction(
        self,
        seizure: Dict[str, Any],
        net_salary: Decimal,
        seizable_amount: Decimal,
        dependents_count: int = 0,
    ) -> Decimal:
        ...


class IPayslipEnrichment(ABC):
    """
    Enrichissement du bulletin avec saisies et avances (post-traitement).
    Implémentation actuelle : services.saisies_avances_integration (legacy).
    """

    @abstractmethod
    def enrich_payslip_with_seizures_and_advances(
        self,
        payslip_json_data: Dict[str, Any],
        employee_id: str,
        year: int,
        month: int,
        payslip_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        ...


class IAdvancePaymentStorage(ABC):
    """Stockage des preuves de paiement (bucket advance_payments)."""

    @abstractmethod
    def create_signed_upload_url(self, path: str) -> Dict[str, str]:
        """Retourne path et signedURL."""
        ...

    @abstractmethod
    def create_signed_download_url(self, path: str, expiry_seconds: int = 3600) -> str:
        ...

    @abstractmethod
    def remove(self, path: str) -> None:
        ...


class IEmployeeCompanyProvider(ABC):
    """Fournit le company_id d'un employé (lecture table employees)."""

    @abstractmethod
    def get_company_id(self, employee_id: str) -> Optional[str]:
        ...
