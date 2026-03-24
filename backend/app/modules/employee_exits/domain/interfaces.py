"""
Ports (interfaces) du domaine employee_exits.

Implémentations dans infrastructure/. Source : api/routers/employee_exits.py,
services/document_generator.py ; calcul indemnités via le moteur paie (app / adaptateur).
Aucune dépendance FastAPI ni DB ici.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class IEmployeeExitRepository(ABC):
    """Accès persistance aux sorties (table employee_exits)."""

    @abstractmethod
    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Crée une sortie. Retourne la ligne insérée."""
        ...

    @abstractmethod
    def get_by_id(self, exit_id: str, company_id: str) -> Optional[Dict[str, Any]]:
        """Retourne une sortie par id et company_id."""
        ...

    @abstractmethod
    def get_with_employee(
        self, exit_id: str, company_id: str, employee_columns: str
    ) -> Optional[Dict[str, Any]]:
        """Retourne une sortie avec jointure employee (colonnes optionnelles)."""
        ...

    @abstractmethod
    def list(
        self,
        company_id: str,
        status: Optional[str] = None,
        exit_type: Optional[str] = None,
        employee_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Liste les sorties (filtres optionnels), avec join employee."""
        ...

    @abstractmethod
    def update(self, exit_id: str, company_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Met à jour une sortie. Retourne la ligne mise à jour."""
        ...

    @abstractmethod
    def delete(self, exit_id: str, company_id: str) -> bool:
        """Supprime une sortie. Retourne True si supprimé."""
        ...


class IExitDocumentRepository(ABC):
    """Accès persistance aux documents de sortie (table exit_documents)."""

    @abstractmethod
    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Crée un enregistrement document. Retourne la ligne insérée."""
        ...

    @abstractmethod
    def list_by_exit(self, exit_id: str, company_id: str) -> List[Dict[str, Any]]:
        """Liste les documents d'une sortie."""
        ...

    @abstractmethod
    def get_by_id(
        self, document_id: str, exit_id: str, company_id: str
    ) -> Optional[Dict[str, Any]]:
        """Retourne un document par id, exit_id, company_id."""
        ...

    @abstractmethod
    def update(
        self, document_id: str, exit_id: str, company_id: str, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Met à jour un document."""
        ...

    @abstractmethod
    def delete(self, document_id: str, exit_id: str, company_id: str) -> bool:
        """Supprime un document."""
        ...


class IExitChecklistRepository(ABC):
    """Accès persistance à la checklist (table exit_checklist_items)."""

    @abstractmethod
    def create_many(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Crée les items de checklist par défaut. Retourne les lignes insérées."""
        ...

    @abstractmethod
    def list_by_exit(self, exit_id: str, company_id: str) -> List[Dict[str, Any]]:
        """Liste les items d'une sortie (ordre display_order)."""
        ...

    @abstractmethod
    def get_item(
        self, item_id: str, exit_id: str, company_id: str
    ) -> Optional[Dict[str, Any]]:
        """Retourne un item par id, exit_id, company_id."""
        ...

    @abstractmethod
    def add_item(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Ajoute un item personnalisé."""
        ...

    @abstractmethod
    def update_item(
        self, item_id: str, exit_id: str, company_id: str, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Met à jour un item (complété, notes, due_date)."""
        ...

    @abstractmethod
    def delete_item(self, item_id: str, exit_id: str, company_id: str) -> bool:
        """Supprime un item (non requis uniquement)."""
        ...


class IExitDocumentGenerator(ABC):
    """
    Génération des PDF de sortie (certificat de travail, attestation Pôle Emploi, solde de tout compte).
    Implémentation : app.modules.payroll.solde_de_tout_compte (via app.shared.compat).
    """

    @abstractmethod
    def generate_certificat_travail(
        self,
        employee_data: Dict[str, Any],
        company_data: Dict[str, Any],
        exit_data: Dict[str, Any],
    ) -> bytes:
        """Génère le certificat de travail (Article L1234-19)."""
        ...

    @abstractmethod
    def generate_attestation_pole_emploi(
        self,
        employee_data: Dict[str, Any],
        company_data: Dict[str, Any],
        exit_data: Dict[str, Any],
    ) -> bytes:
        """Génère l'attestation Pôle Emploi."""
        ...

    @abstractmethod
    def generate_solde_tout_compte(
        self,
        employee_data: Dict[str, Any],
        company_data: Dict[str, Any],
        exit_data: Dict[str, Any],
        indemnities: Dict[str, Any],
        supabase_client: Any = None,
    ) -> bytes:
        """Génère le solde de tout compte (dispatch par exit_type)."""
        ...


class IIndemnityCalculator(ABC):
    """
    Calcul des indemnités de sortie.
    Implémentation : app.modules.payroll.application.indemnites_commands (via providers).
    """

    @abstractmethod
    def calculate(
        self,
        employee_data: Dict[str, Any],
        exit_data: Dict[str, Any],
        supabase_client: Any = None,
    ) -> Dict[str, Any]:
        """Retourne les indemnités calculées (total_gross_indemnities, indemnite_conges, etc.)."""
        ...


class IExitStorageProvider(ABC):
    """
    Stockage des documents de sortie (bucket exit_documents).
    Upload, URLs signées, suppression.
    """

    @abstractmethod
    def upload(self, path: str, content: bytes, content_type: str) -> None:
        """Upload un fichier dans le bucket exit_documents."""
        ...

    @abstractmethod
    def create_signed_upload_url(self, path: str) -> str:
        """Retourne une URL signée pour upload (client-side)."""
        ...

    @abstractmethod
    def create_signed_url(
        self, path: str, expiry_seconds: int = 3600, download: bool = False
    ) -> Optional[str]:
        """Retourne une URL signée pour lecture."""
        ...

    @abstractmethod
    def download(self, path: str) -> bytes:
        """Télécharge le fichier. Retourne les bytes."""
        ...

    @abstractmethod
    def remove(self, paths: List[str]) -> None:
        """Supprime les fichiers (liste de storage_path)."""
        ...
