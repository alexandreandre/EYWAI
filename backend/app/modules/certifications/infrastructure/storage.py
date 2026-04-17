"""Upload certificats vers Supabase Storage (bucket privé « certifications »)."""

from __future__ import annotations

import mimetypes
from typing import Optional

from app.core.database import supabase

BUCKET_CERTIFICATIONS = "certifications"


def _guess_content_type(filename: str) -> str:
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


def upload_certificate(
    company_id: str, cert_id: str, file_bytes: bytes, filename: str
) -> str:
    """
    Upload dans le bucket « certifications », chemin {company_id}/{cert_id}/{filename}.
    Retourne une URL signée (bucket privé, accès service_role côté API).
    """
    safe_name = filename.replace("..", "").replace("/", "_").strip() or "certificat"
    path = f"{company_id}/{cert_id}/{safe_name}"
    content_type = _guess_content_type(safe_name)

    supabase.storage.from_(BUCKET_CERTIFICATIONS).upload(
        path,
        file_bytes,
        file_options={"content-type": content_type, "x-upsert": "true"},
    )

    signed_r = supabase.storage.from_(BUCKET_CERTIFICATIONS).create_signed_url(
        path,
        31536000,
        options={"download": True},
    )
    signed_url: Optional[str] = None
    if isinstance(signed_r, dict):
        signed_url = signed_r.get("signedURL") or signed_r.get("signedUrl")
    if not signed_url:
        raise RuntimeError("Impossible de générer l’URL signée du certificat.")
    return signed_url
