"""Commandes écriture — bibliothèque de modèles."""

from __future__ import annotations

import os
from typing import Optional

from app.modules.document_library.infrastructure.repository import (
    document_library_repository,
)
from app.modules.document_library.schemas.requests import (
    DocumentTemplateCreate,
    DocumentTemplateUpdate,
)

_MAX_BYTES = 5 * 1024 * 1024
_ALLOWED_EXT = {"docx", "html"}


def _infer_format(filename: str) -> Optional[str]:
    ext = os.path.splitext(filename.lower())[1].lstrip(".")
    if ext in _ALLOWED_EXT:
        return ext
    return None


def create_template(
    company_id: str, data: DocumentTemplateCreate, created_by: Optional[str]
) -> dict:
    return document_library_repository.create(company_id, data, created_by)


def update_template(
    template_id: str, company_id: str, data: DocumentTemplateUpdate
) -> dict:
    return document_library_repository.update(template_id, company_id, data)


def archive_template(template_id: str, company_id: str) -> dict:
    return document_library_repository.archive(template_id, company_id)


def validate_template_bytes(file_bytes: bytes, file_name: str) -> dict:
    """Analyse un fichier modèle et retourne les variables inconnues."""
    from app.services.document_engine import document_engine
    from app.services.document_variables import build_variables, list_document_variables

    fmt = _infer_format(file_name)
    if fmt not in _ALLOWED_EXT:
        raise ValueError("Format non autorisé : seuls .docx et .html sont acceptés.")
    known = {v["key"]: "" for v in list_document_variables()}
    known.update(build_variables({}, {}, {}))
    return document_engine.preview_variables(file_bytes, fmt or "", known)


def upload_template_file(
    company_id: str,
    template_id: str,
    file_bytes: bytes,
    file_name: str,
    created_by: Optional[str],
) -> dict:
    if len(file_bytes) > _MAX_BYTES:
        raise ValueError("Le fichier dépasse la taille maximale (5 Mo).")
    fmt = _infer_format(file_name)
    if fmt not in _ALLOWED_EXT:
        raise ValueError("Format non autorisé : seuls .docx et .html sont acceptés.")
    tpl = document_library_repository.get_by_id(template_id, company_id)
    if not tpl:
        raise LookupError("Modèle introuvable")
    next_v = document_library_repository.max_version(template_id) + 1
    path = document_library_repository.upload_template_file(
        company_id,
        template_id,
        next_v,
        file_bytes,
        file_name,
        fmt,
    )
    row = document_library_repository.add_version(
        template_id,
        path,
        file_name,
        fmt,
        len(file_bytes),
        created_by,
    )
    preview = validate_template_bytes(file_bytes, file_name)
    row["unknown_variables"] = preview.get("unknown_variables") or []
    return row


def restore_version(
    template_id: str, company_id: str, version_id: str, uploaded_by: Optional[str]
) -> dict:
    row = document_library_repository.get_version_row(
        template_id, version_id, company_id
    )
    current_max = document_library_repository.max_version(template_id)
    if int(row.get("version") or 0) >= current_max:
        raise ValueError("Cette version est déjà la plus récente.")
    return document_library_repository.add_version(
        template_id,
        str(row["file_url"]),
        str(row["file_name"]),
        str(row["file_format"]),
        int(row["file_size"]) if row.get("file_size") is not None else None,
        uploaded_by,
    )
