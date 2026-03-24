"""
Providers externes du module saisies_avances.

Implémentation de IAdvancePaymentStorage (bucket Supabase advance_payments).
Comportement identique au router legacy.
"""
from typing import Dict

from app.core.database import supabase

from app.modules.saisies_avances.domain.interfaces import IAdvancePaymentStorage


BUCKET_NAME = "advance_payments"


class AdvancePaymentStorage(IAdvancePaymentStorage):
    """Stockage des preuves de paiement (bucket advance_payments)."""

    def __init__(self, bucket: str = BUCKET_NAME):
        self._bucket = bucket

    def create_signed_upload_url(self, path: str) -> Dict[str, str]:
        r = supabase.storage.from_(self._bucket).create_signed_upload_url(path)
        if "signedUrl" not in r:
            raise ValueError(f"Clé 'signedUrl' non trouvée: {r}")
        return {"path": path, "signedURL": r["signedUrl"]}

    def create_signed_download_url(
        self, path: str, expiry_seconds: int = 3600
    ) -> str:
        r = supabase.storage.from_(self._bucket).create_signed_url(
            path, expiry_seconds, options={"download": True}
        )
        return r["signedURL"]

    def remove(self, path: str) -> None:
        supabase.storage.from_(self._bucket).remove([path])


advance_payment_storage = AdvancePaymentStorage()
