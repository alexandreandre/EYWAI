"""Schémas de réponse — bibliothèque de modèles documents."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class DocumentTemplateVersion(BaseModel):
    id: str
    template_id: str
    version: int
    file_url: str
    file_name: str
    file_format: str
    file_size: Optional[int] = None
    uploaded_by: Optional[str] = None
    created_at: datetime


class DocumentTemplate(BaseModel):
    id: str
    company_id: str
    document_type: str
    name: str
    is_default: bool
    status: str
    created_at: datetime
    updated_at: datetime
    current_version: Optional[DocumentTemplateVersion] = None
    versions_count: int = 0


class SignedVersionDownload(BaseModel):
    signed_url: str
