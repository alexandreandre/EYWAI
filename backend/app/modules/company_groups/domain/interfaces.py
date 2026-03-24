"""
Ports (interfaces) du domaine company_groups.

Implémentations dans infrastructure/. Aucune dépendance FastAPI ni DB ici.
Contrat aligné sur l'usage par la couche application (comportement identique aux routeurs).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class ICompanyGroupRepository(ABC):
    """
    Port d'accès aux données : company_groups, companies (group_id),
    user_company_accesses, profiles.
    Implémentation : infrastructure/repository.py.
    """

    @abstractmethod
    def get_by_id_with_companies(self, group_id: str) -> Optional[Dict[str, Any]]:
        """Retourne un groupe par id avec ses entreprises (nested companies)."""
        ...

    @abstractmethod
    def list_groups_with_companies(
        self, company_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Liste les groupes avec leurs entreprises.
        company_ids is None ou vide : tous les groupes actifs. Sinon : filtre companies!inner.
        """
        ...

    @abstractmethod
    def list_all_active_ordered(self) -> List[Dict[str, Any]]:
        """Liste tous les groupes actifs triés par group_name."""
        ...

    @abstractmethod
    def create(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Crée un groupe. Retourne la ligne créée ou None."""
        ...

    @abstractmethod
    def update(
        self, group_id: str, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Met à jour un groupe. Retourne la ligne mise à jour ou None."""
        ...

    @abstractmethod
    def exists(self, group_id: str) -> bool:
        """Vérifie qu'un groupe existe."""
        ...

    @abstractmethod
    def set_company_group(
        self, company_id: str, group_id: Optional[str]
    ) -> bool:
        """Associe ou dissocie une entreprise à un groupe."""
        ...

    @abstractmethod
    def set_company_group_with_current(
        self,
        company_id: str,
        group_id: Optional[str],
        current_group_id: Optional[str],
    ) -> bool:
        """Met à jour group_id d'une entreprise en vérifiant current_group_id."""
        ...

    @abstractmethod
    def get_company_ids_by_group_id(self, group_id: str) -> List[str]:
        """Liste les IDs d'entreprises actives d'un groupe."""
        ...

    @abstractmethod
    def get_companies_by_group_id(
        self, group_id: str, columns: str = "id, company_name, siret, effectif, is_active"
    ) -> List[Dict[str, Any]]:
        """Liste les entreprises d'un groupe (colonnes configurables)."""
        ...

    @abstractmethod
    def get_companies_without_group(
        self, columns: str = "id, company_name, siret, effectif"
    ) -> List[Dict[str, Any]]:
        """Liste les entreprises sans groupe (group_id null)."""
        ...

    @abstractmethod
    def get_companies_for_group_stats(
        self, group_id: str, columns: str = "id, company_name, siret"
    ) -> List[Dict[str, Any]]:
        """Entreprises du groupe pour stats (consolidated, etc.)."""
        ...

    @abstractmethod
    def get_group_company_ids_for_permission_check(self, group_id: str) -> List[str]:
        """IDs des entreprises du groupe (toutes, pour vérification admin)."""
        ...

    @abstractmethod
    def get_groups_with_company_and_effectif(
        self, groups: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Enrichit chaque groupe avec company_count et total_employees (effectif)."""
        ...

    @abstractmethod
    def get_user_accesses_for_companies(
        self, company_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Accès user_company_accesses pour des company_ids (profiles, companies)."""
        ...

    @abstractmethod
    def get_existing_user_accesses(
        self, user_id: str, company_ids: List[str]
    ) -> Dict[str, str]:
        """Accès existants (company_id -> role) pour un user et des companies."""
        ...

    @abstractmethod
    def update_user_profile(
        self,
        user_id: str,
        first_name: Optional[str],
        last_name: Optional[str],
    ) -> None:
        """Met à jour first_name / last_name dans profiles."""
        ...

    @abstractmethod
    def insert_user_company_access(
        self,
        user_id: str,
        company_id: str,
        role: str,
        is_primary: bool,
    ) -> None:
        """Insère un accès user_company_accesses."""
        ...

    @abstractmethod
    def update_user_company_access_role(
        self, user_id: str, company_id: str, role: str
    ) -> None:
        """Met à jour le rôle d'un accès."""
        ...

    @abstractmethod
    def delete_user_company_accesses(
        self, user_id: str, company_ids: List[str]
    ) -> int:
        """Supprime les accès d'un utilisateur pour les companies. Retourne le nombre supprimé."""
        ...

    @abstractmethod
    def count_user_accesses(self, user_id: str) -> int:
        """Indique si l'utilisateur a au moins un accès (0 ou 1). Pour is_primary."""
        ...

    @abstractmethod
    def get_detailed_accesses_for_companies(
        self, company_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """user_company_accesses avec profiles pour detailed-user-accesses."""
        ...


class IGroupStatsProvider(ABC):
    """
    Port des appels RPC PostgreSQL d'agrégation groupe.
    Implémentation : infrastructure/providers.py.
    """

    @abstractmethod
    def get_consolidated_dashboard(
        self,
        company_ids: List[str],
        reference_year: Optional[int] = None,
        reference_month: Optional[int] = None,
    ) -> Any:
        """RPC get_group_consolidated_dashboard."""
        ...

    @abstractmethod
    def get_employees_stats(self, company_ids: List[str]) -> Any:
        """RPC get_group_employees_stats."""
        ...

    @abstractmethod
    def get_payroll_evolution(
        self,
        company_ids: List[str],
        start_year: int,
        start_month: int,
        end_year: int,
        end_month: int,
    ) -> Any:
        """RPC get_group_payroll_evolution."""
        ...

    @abstractmethod
    def get_company_comparison(
        self,
        company_ids: List[str],
        metric: str,
        year: Optional[int] = None,
        month: Optional[int] = None,
    ) -> Any:
        """RPC get_group_company_comparison."""
        ...


class IUserLookupProvider(ABC):
    """
    Port de recherche utilisateur par email et récupération des emails (auth.admin).
    Implémentation : infrastructure/repository.py (méthodes statiques) ou infrastructure/user_lookup.py.
    """

    @abstractmethod
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Recherche un utilisateur par email. Retourne {"id", "email"} ou None."""
        ...

    @abstractmethod
    def get_user_emails_map(self, user_ids: List[str]) -> Dict[str, str]:
        """Retourne un dict user_id -> email."""
        ...
