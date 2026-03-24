"""
Providers (services externes) du module employee_exits.

Implémentations des ports domain : générateur de documents, calcul d'indemnités, stockage.
Le générateur de documents est fourni via app.shared.compat (sans import legacy direct).
Aucune dépendance FastAPI.
"""
from typing import Any, Dict, List, Optional

from app.core.database import supabase

from app.modules.employee_exits.domain.interfaces import (
    IExitDocumentGenerator,
    IIndemnityCalculator,
    IExitStorageProvider,
)
from app.shared.compat.employee_exit_document_generator import (
    get_employee_exit_document_generator,
)

BUCKET_EXIT_DOCUMENTS = "exit_documents"


def get_exit_document_generator() -> IExitDocumentGenerator:
    """
    Retourne l'implémentation du générateur de documents (via wrapper app.shared.compat).
    """
    return get_employee_exit_document_generator()


def get_indemnity_calculator() -> IIndemnityCalculator:
    """
    Retourne l'implémentation du calcul d'indemnités (app.modules.payroll.application).
    """
    return _IndemnityCalculatorAdapter()


class _IndemnityCalculatorAdapter(IIndemnityCalculator):
    """Délègue à app.modules.payroll.application.indemnites_commands."""

    def calculate(
        self,
        employee_data: Dict[str, Any],
        exit_data: Dict[str, Any],
        supabase_client: Any = None,
    ) -> Dict[str, Any]:
        from app.modules.payroll.application.indemnites_commands import (
            calculer_indemnites_sortie,
        )
        return calculer_indemnites_sortie(
            employee_data=employee_data,
            exit_data=exit_data,
            supabase_client=supabase_client,
        )


def get_exit_storage_provider(supabase_client: Any = None) -> IExitStorageProvider:
    """
    Retourne le provider de stockage pour le bucket exit_documents.
    Délègue à supabase.storage.from_('exit_documents').
    """
    return _SupabaseExitStorageProvider(supabase_client or supabase)


class _SupabaseExitStorageProvider(IExitStorageProvider):
    """Implémentation Supabase du stockage des documents de sortie."""

    def __init__(self, client: Any):
        self._sb = client

    def _bucket(self):
        return self._sb.storage.from_(BUCKET_EXIT_DOCUMENTS)

    def upload(self, path: str, content: bytes, content_type: str) -> None:
        self._bucket().upload(path, content, {"content-type": content_type})

    def create_signed_upload_url(self, path: str) -> str:
        resp = self._bucket().create_signed_upload_url(path)
        return resp.get("signedURL") if isinstance(resp, dict) else resp

    def create_signed_url(
        self, path: str, expiry_seconds: int = 3600, download: bool = False
    ) -> Optional[str]:
        try:
            options = {"download": True} if download else {}
            resp = self._bucket().create_signed_url(path, expiry_seconds, options)
            return resp.get("signedURL") or resp.get("url") if isinstance(resp, dict) else str(resp)
        except Exception:
            return None

    def download(self, path: str) -> bytes:
        data = self._bucket().download(path)
        if hasattr(data, "read"):
            return data.read()
        if isinstance(data, bytes):
            return data
        return bytes(data) if data else b""

    def remove(self, paths: List[str]) -> None:
        if paths:
            self._bucket().remove(paths)
