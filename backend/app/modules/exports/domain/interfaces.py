# Interfaces (ports) du domaine exports — préparation migration.
# L'application dépendra de ces abstractions ; l'infrastructure les implémentera.
from typing import Any, Dict, List, Optional, Protocol


class ExportGeneratorPort(Protocol):
    """Port pour un générateur d'export (par type : journal_paie, virement_salaires, od_*, cabinet, dsn)."""

    def preview(
        self, company_id: str, period: str, **kwargs: Any
    ) -> Dict[str, Any]: ...
    def generate(self, company_id: str, period: str, **kwargs: Any) -> bytes: ...


class ExportStoragePort(Protocol):
    """Port pour le stockage des fichiers d'export (Supabase Storage)."""

    def upload(
        self, bucket: str, path: str, content: bytes, content_type: str
    ) -> str: ...
    def create_signed_url(self, path: str, expires_sec: int = 3600) -> str: ...


class ExportHistoryRepositoryPort(Protocol):
    """Port pour l'historique des exports (table exports_history)."""

    def insert(self, record: Dict[str, Any]) -> Optional[str]: ...  # retourne export_id
    def get_by_id(
        self, export_id: str, company_id: str
    ) -> Optional[Dict[str, Any]]: ...
    def list_by_company(
        self,
        company_id: str,
        export_type: Optional[str],
        period: Optional[str],
        limit: int,
    ) -> List[Dict[str, Any]]: ...
