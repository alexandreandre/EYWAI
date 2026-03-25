"""
Providers expenses (stockage justificatifs).

Logique extraite de api/routers/expenses.py — comportement identique.
"""

from typing import Any, List

from app.modules.expenses.domain.interfaces import IExpenseStorageProvider

BUCKET_NAME = "expense_receipts"


class ExpenseStorageProvider(IExpenseStorageProvider):
    """Implémentation Supabase Storage pour expense_receipts."""

    def __init__(self, supabase_client: Any = None):
        if supabase_client is None:
            from app.core.database import supabase

            supabase_client = supabase
        self._client = supabase_client

    def create_signed_upload_url(self, path: str) -> dict:
        signed_url_response = self._client.storage.from_(
            BUCKET_NAME
        ).create_signed_upload_url(path)
        if "signedUrl" not in signed_url_response:
            raise KeyError(f"Clé 'signedUrl' non trouvée: {signed_url_response}")
        return signed_url_response

    def create_signed_urls(
        self, paths: List[str], expires_in: int = 3600
    ) -> List[dict]:
        result = self._client.storage.from_(BUCKET_NAME).create_signed_urls(
            paths, expires_in
        )
        if isinstance(result, dict) and result.get("error"):
            raise RuntimeError(
                f"Erreur Supabase Storage (receipts): {result.get('message')}"
            )
        return result
