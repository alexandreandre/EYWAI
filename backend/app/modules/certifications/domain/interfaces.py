"""Port persistance certifications (référentiel + habilitations collaborateurs)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class AbstractCertificationRepository(ABC):
    """Accès tables certification_referential et employee_certifications."""

    @abstractmethod
    def get_all_refs(self, company_id: str) -> List[Dict[str, Any]]:
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
    def count_active_employee_certs_for_ref(self, ref_id: str, company_id: str) -> int:
        ...

    @abstractmethod
    def get_all_employee_certs(
        self,
        company_id: str,
        employee_id: Optional[str] = None,
        include_archived: bool = False,
    ) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def get_employee_cert_by_id(
        self, cert_row_id: str, company_id: str
    ) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    def create_employee_cert(self, company_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        ...

    @abstractmethod
    def update_employee_cert(
        self, cert_row_id: str, company_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        ...

    @abstractmethod
    def archive_employee_cert(self, cert_row_id: str, company_id: str) -> None:
        ...

    @abstractmethod
    def get_employee_id_for_user(self, user_id: str, company_id: str) -> Optional[str]:
        ...

    @abstractmethod
    def get_expiring_count(self, company_id: str) -> int:
        ...

    @abstractmethod
    def get_expired_count(self, company_id: str) -> int:
        ...
