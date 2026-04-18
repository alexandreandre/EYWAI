"""Requêtes lecture — bibliothèque de modèles."""

from __future__ import annotations

from typing import List, Optional

from app.modules.document_library.infrastructure.repository import (
    document_library_repository,
)
from app.modules.document_library.schemas.requests import KNOWN_DOCUMENT_TYPES


def get_templates(company_id: str, status: Optional[str] = None) -> List[dict]:
    return document_library_repository.get_all(company_id, status=status)


def get_template(template_id: str, company_id: str) -> Optional[dict]:
    return document_library_repository.get_by_id(template_id, company_id)


def get_versions(template_id: str, company_id: str) -> List[dict]:
    return document_library_repository.get_versions(template_id, company_id)


def get_missing_types(company_id: str) -> List[str]:
    rows = document_library_repository.get_all(company_id, status="active")
    covered = {str(r["document_type"]) for r in rows}
    return sorted(KNOWN_DOCUMENT_TYPES - covered)


def get_version_download_url(
    template_id: str, company_id: str, version_id: str
) -> str:
    row = document_library_repository.get_version_row(
        template_id, version_id, company_id
    )
    path = str(row.get("file_url") or "")
    if not path:
        raise ValueError("Fichier de version manquant")
    return document_library_repository.create_signed_download_url(path)
