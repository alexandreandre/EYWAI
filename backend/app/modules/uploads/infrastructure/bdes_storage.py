"""Stockage des fichiers BDES (bucket Supabase dédié)."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from app.core.database import get_supabase_admin_client

BUCKET_BDES = "cse-documents"


def _safe_filename(name: str) -> str:
    base = Path(name).name
    cleaned = re.sub(r"[^a-zA-Z0-9._-]", "_", base)
    return (cleaned[:180] or "document").lower()


def upload_bdes_file(
    content: bytes,
    content_type: str | None,
    filename: str,
    company_id: str,
) -> str:
    sb = get_supabase_admin_client()
    safe = _safe_filename(filename)
    path = f"bdes/{company_id}/{uuid.uuid4().hex}_{safe}"
    sb.storage.from_(BUCKET_BDES).upload(
        path=path,
        file=content,
        file_options={
            "content-type": content_type or "application/octet-stream",
            "x-upsert": "true",
        },
    )
    return path
