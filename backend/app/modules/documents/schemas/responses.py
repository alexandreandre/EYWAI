"""Réponses API — documents générés."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class GeneratedDocument(BaseModel):
    id: str
    company_id: str
    employee_id: Optional[str] = None
    document_type: str
    category: str
    template_id: Optional[str] = None
    template_version_id: Optional[str] = None
    is_eywai_template: bool
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    status: str
    generation_context: Dict[str, Any] = Field(default_factory=dict)
    generated_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    employee_name: Optional[str] = None
    template_name: Optional[str] = None

    class Config:
        from_attributes = True


class DownloadUrlResponse(BaseModel):
    signed_url: str
