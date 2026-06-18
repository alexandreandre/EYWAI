"""Stockage temporaire des PDF relevés de pointages (bucket Supabase)."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from app.core.database import get_supabase_admin_client

BUCKET_SCHEDULE_IMPORTS = "schedule-imports"


def _safe_filename(name: str) -> str:
    base = Path(name).name
    cleaned = re.sub(r"[^a-zA-Z0-9._-]", "_", base)
    return (cleaned[:180] or "document").lower()


def upload_schedule_import_file(
    content: bytes,
    content_type: str | None,
    filename: str,
    company_id: str,
    job_id: str,
) -> str:
    sb = get_supabase_admin_client()
    safe = _safe_filename(filename)
    path = f"{company_id}/{job_id}/{uuid.uuid4().hex}_{safe}"
    sb.storage.from_(BUCKET_SCHEDULE_IMPORTS).upload(
        path=path,
        file=content,
        file_options={
            "content-type": content_type or "application/pdf",
            "x-upsert": "true",
        },
    )
    return path


def download_schedule_import_file(path: str) -> bytes:
    sb = get_supabase_admin_client()
    return sb.storage.from_(BUCKET_SCHEDULE_IMPORTS).download(path)


__all__ = [
    "BUCKET_SCHEDULE_IMPORTS",
    "download_schedule_import_file",
    "upload_schedule_import_file",
]
