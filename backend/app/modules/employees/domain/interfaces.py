"""
Ports (interfaces) du domaine employees.

Aucune dépendance FastAPI. Implémentés dans infrastructure.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class IEmployeeRepository(ABC):
    """Port pour la persistance des employés."""

    @abstractmethod
    def get_by_company(self, company_id: str) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_by_id(
        self, employee_id: str, company_id: str
    ) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_by_id_only(self, employee_id: str) -> Optional[Dict[str, Any]]:
        """Lecture par id sans filtre company (ex. pour RIB update)."""
        pass

    @abstractmethod
    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def update(
        self, employee_id: str, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def delete(self, employee_id: str) -> bool:
        pass


class IProfileRepository(ABC):
    """Port pour l'upsert du profil utilisateur (table profiles)."""

    @abstractmethod
    def upsert(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        pass


class IAuthProvider(ABC):
    """Port pour la création et suppression d'utilisateurs Auth."""

    @abstractmethod
    def create_user(self, email: str, password: str) -> str:
        """Crée un utilisateur Auth, retourne l'id."""
        pass

    @abstractmethod
    def delete_user(self, user_id: str) -> None:
        pass


class IStorageProvider(ABC):
    """Port pour le stockage (buckets Supabase : list, signed URL, upload)."""

    @abstractmethod
    def list_files(self, bucket: str, path: str) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def create_signed_url(
        self,
        bucket: str,
        path: str,
        expiry_seconds: int = 3600,
        download: bool = True,
    ) -> Optional[str]:
        """Retourne l'URL signée ou None."""
        pass

    @abstractmethod
    def upload(
        self,
        bucket: str,
        path: str,
        content: bytes,
        content_type: str,
    ) -> None:
        pass


class ICompanyReader(ABC):
    """Port pour la lecture des données entreprise (company_name, siret, email)."""

    @abstractmethod
    def get_company_data(self, company_id: str) -> Optional[Dict[str, Any]]:
        pass


class IAnnualReviewQuery(ABC):
    """Port pour la lecture de l'entretien annuel d'un employé pour une année."""

    @abstractmethod
    def fetch_for_employee_year(
        self, employee_id: str, company_id: str, year: int
    ) -> Optional[Dict[str, Any]]:
        pass


class IResidencePermitStatusCalculator(ABC):
    """Port pour le calcul du statut titre de séjour."""

    @abstractmethod
    def calculate(
        self,
        is_subject_to_residence_permit: bool,
        residence_permit_expiry_date: Optional[Any],
        employment_status: str,
        reference_date: Optional[Any] = None,
    ) -> Dict[str, Any]:
        pass


__all__ = [
    "IEmployeeRepository",
    "IProfileRepository",
    "IAuthProvider",
    "IStorageProvider",
    "ICompanyReader",
    "IAnnualReviewQuery",
    "IResidencePermitStatusCalculator",
]
