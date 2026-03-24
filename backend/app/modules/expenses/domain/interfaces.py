"""
Ports (interfaces) du domaine expenses.

Implémentations dans infrastructure/. Aucune dépendance FastAPI ni DB ici.
Source : comportement actuel de api/routers/expenses.py (table expense_reports, bucket expense_receipts).
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class IExpenseRepository(ABC):
    """Accès persistance aux notes de frais (table expense_reports)."""

    @abstractmethod
    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Crée une note de frais. Retourne la ligne insérée."""
        ...

    @abstractmethod
    def get_by_id(self, expense_id: str) -> Optional[Dict[str, Any]]:
        """Retourne une note par id."""
        ...

    @abstractmethod
    def update_status(self, expense_id: str, status: str) -> Optional[Dict[str, Any]]:
        """Met à jour le statut. Retourne la ligne mise à jour."""
        ...

    @abstractmethod
    def list_by_employee_id(self, employee_id: str) -> List[Dict[str, Any]]:
        """Liste les notes d'un employé (ordre date desc)."""
        ...

    @abstractmethod
    def list_all(
        self, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Liste les notes avec join employee (RH), optionnellement filtré par status."""
        ...


class IExpenseStorageProvider(ABC):
    """
    Stockage des justificatifs (bucket expense_receipts).
    Source : api/routers/expenses.py (create_signed_upload_url, create_signed_urls).
    """

    @abstractmethod
    def create_signed_upload_url(self, path: str) -> Dict[str, str]:
        """Génère une URL signée pour l'upload. Retourne { signedUrl, path } ou équivalent."""
        ...

    @abstractmethod
    def create_signed_urls(
        self, paths: List[str], expires_in: int = 3600
    ) -> List[Dict[str, str]]:
        """Génère des URLs signées pour la lecture (ex. 1h). Retourne liste de { signedURL }."""
        ...
