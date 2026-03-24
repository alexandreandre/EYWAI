"""
Ports (interfaces) du domaine users.

Implémentations dans infrastructure/. Aucune dépendance FastAPI ni DB ici.
"""
from abc import ABC, abstractmethod
from typing import Any, List, Optional


class IUserRepository(ABC):
    """Accès au profil utilisateur (table profiles)."""
    @abstractmethod
    def get_by_id(self, user_id: str) -> Optional[dict]:
        ...

    @abstractmethod
    def get_by_email(self, email: str) -> Optional[dict]:
        ...

    @abstractmethod
    def create(self, data: dict) -> None:
        ...

    @abstractmethod
    def update(self, user_id: str, data: dict) -> None:
        ...


class IUserCompanyAccessRepository(ABC):
    """Accès aux accès utilisateur-entreprise (user_company_accesses)."""
    @abstractmethod
    def get_accesses_for_user(self, user_id: str) -> List[dict]:
        ...

    @abstractmethod
    def get_access_with_companies(self, user_id: str) -> List[dict]:
        """Accès + jointure companies (id, company_name, siret, group_id)."""
        ...

    @abstractmethod
    def get_by_user_and_company(self, user_id: str, company_id: str) -> Optional[dict]:
        ...

    @abstractmethod
    def get_by_user_and_company_with_template(self, user_id: str, company_id: str) -> Optional[dict]:
        """Accès + role_templates(*)."""
        ...

    @abstractmethod
    def create(self, data: dict) -> dict:
        ...

    @abstractmethod
    def update(self, user_id: str, company_id: str, data: dict) -> dict:
        ...

    @abstractmethod
    def delete(self, user_id: str, company_id: str) -> Optional[dict]:
        ...

    @abstractmethod
    def set_primary(self, user_id: str, company_id: str) -> None:
        """Met is_primary=True pour (user_id, company_id) et False pour les autres."""
        ...

    @abstractmethod
    def count_admins(self, company_id: str) -> int:
        ...


class ICompanyRepository(ABC):
    """Lecture companies (pour listes, noms)."""
    @abstractmethod
    def get_active_with_groups(self) -> List[dict]:
        """Companies actives + company_groups(group_name, logo_url, logo_scale)."""
        ...

    @abstractmethod
    def get_active_ids_and_names(self) -> List[dict]:
        """Pour super_admin accessible-companies."""
        ...

    @abstractmethod
    def get_name(self, company_id: str) -> Optional[str]:
        ...


class IRoleTemplateRepository(ABC):
    """Templates de rôles (role_templates, role_template_permissions)."""
    @abstractmethod
    def get_default_system_template_id(self, base_role: str) -> Optional[str]:
        """Template système par nom (Administrateur, Responsable RH, etc.)."""
        ...

    @abstractmethod
    def get_template_permission_ids(self, template_id: str) -> List[str]:
        ...


class IUserPermissionRepository(ABC):
    """Permissions utilisateur (user_permissions)."""
    @abstractmethod
    def has_any_rh_permission(self, user_id: str, company_id: str) -> bool:
        ...

    @abstractmethod
    def get_permission_ids(
        self, user_id: str, company_id: str, role_template_id: Optional[str] = None
    ) -> List[str]:
        """IDs des permissions (directes + via template si role_template_id fourni)."""
        ...

    @abstractmethod
    def copy_from_template(
        self, template_id: str, user_id: str, company_id: str, granted_by: str
    ) -> None:
        ...

    @abstractmethod
    def delete_for_user_company(self, user_id: str, company_id: str) -> None:
        ...

    @abstractmethod
    def upsert(self, user_id: str, company_id: str, permission_id: str, granted_by: str) -> None:
        ...


class IAuthProvider(ABC):
    """Création / lecture utilisateur Supabase Auth (admin API)."""
    @abstractmethod
    def create_user(self, email: str, password: str, metadata: dict) -> Any:
        ...

    @abstractmethod
    def get_user_by_id(self, user_id: str) -> Any:
        ...

    @abstractmethod
    def delete_user(self, user_id: str) -> None:
        ...


class ICredentialsPdfProvider(ABC):
    """Génération du PDF de création de compte."""
    @abstractmethod
    def get_logo_path(self) -> str:
        ...

    @abstractmethod
    def generate(
        self,
        first_name: str,
        last_name: str,
        username: str,
        password: str,
        logo_path: str,
    ) -> bytes:
        ...


class IStorageProvider(ABC):
    """Upload de fichiers (ex: PDF credentials)."""
    @abstractmethod
    def upload_credentials_pdf(self, company_id: str, user_id: str, content: bytes) -> str:
        """Upload et retourne le path ou bucket path."""
        ...
