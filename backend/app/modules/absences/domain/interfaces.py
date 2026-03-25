"""
Ports (interfaces) du domaine absences.

Implémentations dans infrastructure/. Aucune dépendance FastAPI ni DB ici.
Source : comportement actuel de api/routers/absences.py et services/evenements_familiaux.py.
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import Any, Dict, List, Optional


class IAbsenceRepository(ABC):
    """Accès persistance aux demandes d'absence (table absence_requests)."""

    @abstractmethod
    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Crée une demande d'absence. Retourne la ligne insérée."""
        ...

    @abstractmethod
    def get_by_id(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Retourne une demande par id."""
        ...

    @abstractmethod
    def update(self, request_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Met à jour une demande. Retourne la ligne mise à jour."""
        ...

    @abstractmethod
    def list_by_status(self, status: Optional[str]) -> List[Dict[str, Any]]:
        """Liste les demandes (optionnellement filtrées par status) avec join employee."""
        ...

    @abstractmethod
    def list_validated_for_employees(
        self, employee_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Liste les demandes validées (type, selected_days, jours_payes) pour calcul soldes."""
        ...

    @abstractmethod
    def list_by_employee_id(self, employee_id: str) -> List[Dict[str, Any]]:
        """Historique des demandes pour un employé (ordre created_at desc)."""
        ...


class IEvenementFamilialQuotaProvider(ABC):
    """
    Quota et solde événements familiaux (convention collective + référentiel).
    Source : services/evenements_familiaux.py (get_events_disponibles, get_solde_evenement).
    """

    @abstractmethod
    def get_events_disponibles(self, employee_id: str) -> List[Dict[str, Any]]:
        """Liste des événements familiaux disponibles avec quota et solde restant."""
        ...

    @abstractmethod
    def get_solde_evenement(
        self,
        employee_id: str,
        event_code: str,
        hire_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Solde restant pour un événement (quota, taken, solde_restant, cycles_completed)."""
        ...


class ISalaryCertificateProvider(ABC):
    """
    Génération et enregistrement des attestations de salaire (arrêts maladie, AT, etc.).
    Source : api/routers/absences._generate_salary_certificate_for_absence + SalaryCertificateGenerator.
    """

    @abstractmethod
    def generate_for_absence(
        self,
        absence_request_id: str,
        generated_by: Optional[str] = None,
    ) -> Optional[str]:
        """Génère l'attestation pour une demande validée. Retourne certificate_id ou None."""
        ...


class IStorageProvider(ABC):
    """
    URLs signées (upload justificatifs, lecture attestations).
    Buckets : leave_attachments, salary_certificates.
    """

    @abstractmethod
    def create_signed_upload_url(self, path: str, bucket: str) -> str:
        """Retourne l'URL signée pour upload (justificatif congé)."""
        ...

    @abstractmethod
    def create_signed_urls(
        self, paths: List[str], bucket: str, expiry_seconds: int = 3600
    ) -> Dict[str, str]:
        """Retourne un mapping path -> signedURL pour plusieurs fichiers."""
        ...

    @abstractmethod
    def create_signed_url(
        self,
        path: str,
        bucket: str,
        expiry_seconds: int = 3600,
        download: bool = False,
    ) -> Optional[str]:
        """Retourne une URL signée pour lecture (view ou download)."""
        ...

    @abstractmethod
    def download(self, bucket: str, path: str) -> Any:
        """Télécharge le fichier. Retourne bytes ou dict d'erreur."""
        ...


class ICalendarUpdateService(ABC):
    """
    Mise à jour du calendrier planifié (employee_schedules) après validation d'une absence.
    Source : api/routers/absences.update_calendar_from_days.
    """

    @abstractmethod
    def update_calendar_from_days(
        self,
        employee_id: str,
        days: List[date],
        absence_type_str: str,
    ) -> None:
        """Met à jour ou crée les plannings pour les mois concernés (type conge/rtt)."""
        ...
