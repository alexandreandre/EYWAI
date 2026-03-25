# app/modules/cse/domain/interfaces.py
"""
Ports (interfaces) CSE — à implémenter en infrastructure.
Migration : les repositories délégueront d'abord aux services existants si besoin.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class IElectedMemberRepository(ABC):
    """Accès persistance aux élus CSE."""

    @abstractmethod
    def list_by_company(
        self, company_id: str, active_only: bool = True
    ) -> List[Any]: ...
    @abstractmethod
    def get_by_id(self, member_id: str) -> Any: ...
    @abstractmethod
    def get_by_employee(self, company_id: str, employee_id: str) -> Optional[Any]: ...
    @abstractmethod
    def is_elected(self, company_id: str, employee_id: str) -> bool:
        """True si l'employé est élu actif."""
        ...

    @abstractmethod
    def get_mandate_alerts(self, company_id: str, months_before: int = 3) -> List[Any]:
        """Alertes de fin de mandat."""
        ...


class IMeetingRepository(ABC):
    """Accès persistance aux réunions CSE."""

    @abstractmethod
    def list_by_company(
        self,
        company_id: str,
        status: Optional[str] = None,
        meeting_type: Optional[str] = None,
        participant_id: Optional[str] = None,
    ) -> List[Any]: ...
    @abstractmethod
    def get_by_id(self, meeting_id: str, company_id: str) -> Any: ...
    @abstractmethod
    def get_participants(self, meeting_id: str) -> List[Any]:
        """Participants d'une réunion."""
        ...


class IRecordingRepository(ABC):
    """Accès persistance aux enregistrements CSE."""

    @abstractmethod
    def get_status(self, meeting_id: str) -> Any: ...
    @abstractmethod
    def get_minutes_path(self, meeting_id: str, company_id: str) -> Optional[str]:
        """Chemin du PV (minutes_pdf_path) pour une réunion. None si absent."""
        ...


class IDelegationRepository(ABC):
    """Accès persistance aux quotas et heures de délégation."""

    @abstractmethod
    def get_quota(self, company_id: str, employee_id: str) -> Optional[Any]: ...
    @abstractmethod
    def list_quotas(self, company_id: str) -> List[Any]:
        """Liste des quotas par convention collective pour l'entreprise."""
        ...

    @abstractmethod
    def list_hours(
        self,
        company_id: str,
        employee_id: str,
        period_start: Optional[Any] = None,
        period_end: Optional[Any] = None,
    ) -> List[Any]: ...
    @abstractmethod
    def get_summary(
        self, company_id: str, period_start: Any, period_end: Any
    ) -> List[Any]:
        """Récapitulatif heures de délégation par élu."""
        ...


class IBDESDocumentRepository(ABC):
    """Accès persistance aux documents BDES."""

    @abstractmethod
    def list_by_company(
        self,
        company_id: str,
        year: Optional[int] = None,
        document_type: Optional[str] = None,
        visible_to_elected_only: bool = False,
    ) -> List[Any]: ...
    @abstractmethod
    def get_by_id(self, document_id: str, company_id: str) -> Any: ...


class IElectionCycleRepository(ABC):
    """Accès persistance aux cycles électoraux."""

    @abstractmethod
    def list_by_company(self, company_id: str) -> List[Any]: ...
    @abstractmethod
    def get_by_id(self, cycle_id: str, company_id: str) -> Any: ...
    @abstractmethod
    def get_election_alerts(self, company_id: str) -> List[Any]:
        """Alertes électorales (J-180, J-90, J-30)."""
        ...


class ICSEPdfProvider(ABC):
    """Génération PDF (convocations, PV, calendrier électoral)."""

    @abstractmethod
    def generate_convocation(self, meeting_data: Dict[str, Any]) -> bytes: ...
    @abstractmethod
    def generate_minutes(
        self,
        meeting_data: Dict[str, Any],
        transcription: Optional[str] = None,
        summary: Optional[Dict] = None,
    ) -> bytes: ...
    @abstractmethod
    def generate_election_calendar(
        self, cycle_data: Dict[str, Any], timeline: List[Dict[str, Any]]
    ) -> bytes: ...


class ICSEExportProvider(ABC):
    """Exports Excel (élus, heures délégation, historique réunions)."""

    @abstractmethod
    def export_elected_members(self, members: List[Dict[str, Any]]) -> bytes: ...
    @abstractmethod
    def export_delegation_hours(
        self, hours: List[Dict], summary: List[Dict]
    ) -> bytes: ...
    @abstractmethod
    def export_meetings_history(self, meetings: List[Dict[str, Any]]) -> bytes: ...


class ICSERecordingAIProvider(ABC):
    """Traitement IA des enregistrements (transcription, synthèse, tâches)."""

    @abstractmethod
    def process_recording(self, meeting_id: str) -> Dict[str, Any]: ...
