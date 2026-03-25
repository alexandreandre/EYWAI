"""
Ports (interfaces) du domaine schedules pour l'infrastructure.

Règles : pas de FastAPI, pas d'I/O concrète. Dépendances inversées :
l'application et l'infrastructure dépendent du domain, pas l'inverse.
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import Any, Dict, List, Optional, Tuple


class IScheduleRepository(ABC):
    """Port pour la persistance des plannings (table employee_schedules)."""

    @abstractmethod
    def get_planned_calendar(
        self, employee_id: str, year: int, month: int
    ) -> Optional[Dict[str, Any]]:
        """Récupère le calendrier prévu pour un employé / mois (ligne ou None)."""
        ...

    @abstractmethod
    def get_actual_hours(
        self, employee_id: str, year: int, month: int
    ) -> Optional[Dict[str, Any]]:
        """Récupère les heures réelles pour un employé / mois."""
        ...

    @abstractmethod
    def upsert_schedule(
        self,
        employee_id: str,
        company_id: str,
        year: int,
        month: int,
        *,
        planned_calendar: Optional[Dict[str, Any]] = None,
        actual_hours: Optional[Dict[str, Any]] = None,
        payroll_events: Optional[Dict[str, Any]] = None,
        cumuls: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Crée ou met à jour une ligne employee_schedules (upsert employee_id, year, month)."""
        ...

    @abstractmethod
    def get_schedules_for_months(
        self,
        employee_id: str,
        year_months: List[Tuple[int, int]],
    ) -> List[Dict[str, Any]]:
        """Récupère les lignes employee_schedules pour les (year, month) donnés."""
        ...

    @abstractmethod
    def get_latest_cumuls_row(self, employee_id: str) -> Optional[Dict[str, Any]]:
        """Dernière ligne avec cumuls non null (order year desc, month desc, limit 1)."""
        ...

    @abstractmethod
    def update_payroll_events(
        self, employee_id: str, year: int, month: int, payroll_events: Dict[str, Any]
    ) -> None:
        """Met à jour le champ payroll_events pour une ligne existante."""
        ...

    @abstractmethod
    def exists_schedule(self, employee_id: str, year: int, month: int) -> bool:
        """True si une ligne existe pour cet employé / mois."""
        ...

    @abstractmethod
    def insert_schedule(
        self,
        employee_id: str,
        company_id: str,
        year: int,
        month: int,
        planned_calendar: Dict[str, Any],
        actual_hours: Optional[Dict[str, Any]] = None,
        payroll_events: Optional[Dict[str, Any]] = None,
        cumuls: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Insère une nouvelle ligne employee_schedules (apply-model)."""
        ...

    @abstractmethod
    def update_planned_calendar_only(
        self, employee_id: str, year: int, month: int, planned_calendar: Dict[str, Any]
    ) -> None:
        """Met à jour uniquement planned_calendar pour une ligne existante."""
        ...


class IEmployeeCompanyReader(ABC):
    """Port pour la lecture employé / entreprise (tables employees, companies)."""

    @abstractmethod
    def get_company_and_statut(self, employee_id: str) -> Tuple[str, Optional[str]]:
        """Retourne (company_id, statut). Lève si employé absent ou sans company_id."""
        ...

    @abstractmethod
    def get_employee_folder_name(self, employee_id: str) -> str:
        """Retourne employee_folder_name. Lève si employé absent."""
        ...

    @abstractmethod
    def get_employee_for_payroll_events(self, employee_id: str) -> Dict[str, Any]:
        """
        Retourne dict avec employee_folder_name, duree_hebdomadaire, statut, company_id.
        Lève si employé absent.
        """
        ...

    @abstractmethod
    def get_company_parametres_paie(self, company_id: str) -> Optional[Dict[str, Any]]:
        """Retourne parametres_paie de l'entreprise ou None."""
        ...


class IPayrollAnalyzerProvider(ABC):
    """Port pour l'analyse des horaires (événements de paie, mode heures)."""

    @abstractmethod
    def analyser_horaires(
        self,
        planned_data_all_months: List[Dict[str, Any]],
        actual_data_all_months: List[Dict[str, Any]],
        duree_hebdo_contrat: float,
        annee: int,
        mois: int,
        employee_name: str,
    ) -> List[Dict[str, Any]]:
        """Retourne la liste des événements de paie (mode heures)."""
        ...


class IForfaitJourProvider(ABC):
    """Port pour le moteur forfait jour (app.modules.payroll)."""

    @abstractmethod
    def definir_periode_de_paie(
        self,
        parametres_paie: Dict[str, Any],
        employee_statut: Optional[str],
        year: int,
        month: int,
    ) -> Tuple[Optional[date], Optional[date]]:
        """Retourne (date_debut_periode, date_fin_periode) ou (None, None)."""
        ...

    @abstractmethod
    def analyser_jours_forfait_du_mois(
        self,
        planned_data_all_months: List[Dict[str, Any]],
        actual_data_all_months: List[Dict[str, Any]],
        annee: int,
        mois: int,
        employee_name: str,
        date_debut_periode: Optional[date] = None,
        date_fin_periode: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """Retourne la liste des événements de paie (forfait jour)."""
        ...


class IFileCalendarProvider(ABC):
    """Port pour la lecture des fichiers calendriers / horaires (moteur de paie)."""

    @abstractmethod
    def read_planned_calendar(
        self, employee_folder_name: str, year: int, month: int
    ) -> List[Dict[str, Any]]:
        """Lit calendriers/<month>.json, retourne calendrier_prevu (liste)."""
        ...

    @abstractmethod
    def read_actual_hours(
        self, employee_folder_name: str, year: int, month: int
    ) -> List[Dict[str, Any]]:
        """Lit horaires/<month>.json, retourne calendrier_reel (liste)."""
        ...
