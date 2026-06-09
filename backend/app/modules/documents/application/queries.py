"""Lecture — documents générés."""

from __future__ import annotations

from typing import List, Optional

from app.modules.certifications.infrastructure.repository import certification_repository
from app.modules.documents.infrastructure.repository import documents_repository


def get_documents(
    company_id: str,
    employee_id: Optional[str] = None,
    document_type: Optional[str] = None,
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[dict]:
    return documents_repository.get_all(
        company_id,
        employee_id=employee_id,
        document_type=document_type,
        status=status,
        date_from=date_from,
        date_to=date_to,
    )


def get_document(document_id: str, company_id: str) -> Optional[dict]:
    return documents_repository.get_by_id(document_id, company_id)


def get_employee_id_for_user_scope(user_id: str, company_id: str) -> Optional[str]:
    """Même résolution employé que le module certifications (table employees)."""
    return certification_repository.get_employee_id_for_user(user_id, company_id)


def _signed_url_for_document_row(
    row: dict, *, download: bool
) -> str:
    path = row.get("file_url") or ""
    if not path or str(path).lower().startswith("http"):
        raise ValueError("Aucun fichier PDF associé à ce document.")
    if download:
        return documents_repository.create_signed_download_url(str(path))
    return documents_repository.create_signed_preview_url(str(path))


def get_download_url(document_id: str, company_id: str) -> str:
    row = documents_repository.get_by_id(document_id, company_id)
    if not row:
        raise LookupError("Document introuvable")
    return _signed_url_for_document_row(row, download=True)


def get_preview_url(document_id: str, company_id: str) -> str:
    row = documents_repository.get_by_id(document_id, company_id)
    if not row:
        raise LookupError("Document introuvable")
    return _signed_url_for_document_row(row, download=False)
