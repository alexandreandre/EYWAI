# app/modules/recruitment/domain/interfaces.py
"""
Ports (interfaces) du domaine recruitment — pour l'infrastructure.
Implémentations à fournir dans infrastructure/ lors de la migration.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional


class IRecruitmentSettingsReader(ABC):
    """Lecture du paramètre 'module recrutement activé' par entreprise."""

    @abstractmethod
    def is_enabled(self, company_id: str) -> bool:
        pass


class IJobRepository(ABC):
    """Accès persistance aux jobs / offres."""

    @abstractmethod
    def get_by_id(self, company_id: str, job_id: str) -> Optional[dict[str, Any]]:
        pass

    @abstractmethod
    def list_by_company(
        self, company_id: str, status: Optional[str] = None
    ) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def create(self, company_id: str, data: dict[str, Any]) -> dict[str, Any]:
        pass

    @abstractmethod
    def update(
        self, job_id: str, company_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        pass


class ICandidateRepository(ABC):
    """Accès persistance aux candidats."""

    @abstractmethod
    def get_by_id(self, company_id: str, candidate_id: str) -> Optional[dict[str, Any]]:
        pass

    @abstractmethod
    def list_by_company(
        self,
        company_id: str,
        job_id: Optional[str] = None,
        stage_id: Optional[str] = None,
        search: Optional[str] = None,
        participant_user_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def create(self, company_id: str, data: dict[str, Any]) -> dict[str, Any]:
        pass

    @abstractmethod
    def update(
        self, candidate_id: str, company_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        pass

    @abstractmethod
    def delete(self, candidate_id: str, company_id: str) -> None:
        pass


class IPipelineStageRepository(ABC):
    """Accès aux étapes du pipeline."""

    @abstractmethod
    def list_by_job(self, company_id: str, job_id: str) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def create_default_for_job(
        self, company_id: str, job_id: str
    ) -> list[dict[str, Any]]:
        pass


class ITimelineEventWriter(ABC):
    """Écriture d'événements dans la timeline candidat."""

    @abstractmethod
    def add(
        self,
        company_id: str,
        candidate_id: str,
        event_type: str,
        description: str,
        actor_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        pass


class IEmployeeCreator(ABC):
    """Création d'un salarié à partir d'un candidat recruté (dépendance cross-module)."""

    @abstractmethod
    def create_from_candidate(
        self,
        company_id: str,
        candidate_id: str,
        hire_date: str,
        site: Optional[str] = None,
        service: Optional[str] = None,
        job_title: Optional[str] = None,
        contract_type: Optional[str] = None,
        actor_id: Optional[str] = None,
    ) -> dict[str, Any]:
        pass


class IDuplicateChecker(ABC):
    """Vérification doublon candidat / salarié."""

    @abstractmethod
    def check_duplicate_candidate(
        self,
        company_id: str,
        email: Optional[str],
        phone: Optional[str],
        exclude_candidate_id: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        pass

    @abstractmethod
    def check_duplicate_employee(
        self, company_id: str, email: Optional[str], phone: Optional[str]
    ) -> Optional[dict[str, Any]]:
        pass


class IParticipantChecker(ABC):
    """Vérification si un utilisateur est participant (intervieweur) pour un candidat."""

    @abstractmethod
    def is_participant(self, user_id: str, candidate_id: str) -> bool:
        pass


class IInterviewRepository(ABC):
    """Accès persistance aux entretiens (lecture, création, mise à jour)."""

    @abstractmethod
    def list_by_company(
        self,
        company_id: str,
        candidate_id: Optional[str] = None,
        participant_user_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def create(
        self, company_id: str, user_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        pass

    @abstractmethod
    def update(
        self,
        interview_id: str,
        company_id: str,
        data: dict[str, Any],
        is_rh: bool,
    ) -> None:
        pass


class INoteRepository(ABC):
    """Accès persistance aux notes candidat."""

    @abstractmethod
    def list_by_candidate(
        self, company_id: str, candidate_id: str
    ) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def create(
        self, company_id: str, author_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        pass


class IOpinionRepository(ABC):
    """Accès persistance aux avis candidat."""

    @abstractmethod
    def list_by_candidate(
        self, company_id: str, candidate_id: str
    ) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def create(
        self, company_id: str, author_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        pass


class ITimelineEventReader(ABC):
    """Lecture des événements timeline d'un candidat."""

    @abstractmethod
    def list_by_candidate(
        self, company_id: str, candidate_id: str
    ) -> list[dict[str, Any]]:
        pass
