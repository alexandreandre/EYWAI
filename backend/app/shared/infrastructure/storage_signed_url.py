"""Extraction d'URL signées Supabase Storage (formats de réponse variables)."""

from __future__ import annotations

from typing import Any, Optional


def extract_signed_url(response: Any) -> Optional[str]:
    """
    Normalise la réponse Supabase `create_signed_url` / entrée `create_signed_urls`.

    Le SDK peut renvoyer `signedURL`, `signedUrl`, ou un objet avec attribut `.data`.
    """
    if response is None:
        return None

    if isinstance(response, str):
        trimmed = response.strip()
        return trimmed or None

    data = response
    if not isinstance(data, dict):
        data = getattr(response, "data", None)
        if data is None:
            return None

    if not isinstance(data, dict):
        return None

    for key in ("signedURL", "signedUrl", "signed_url"):
        value = data.get(key)
        if value:
            return str(value).strip() or None

    return None
