"""Schémas de réponse — configuration e-mail plateforme."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

SmtpSecurityLiteral = Literal["starttls", "ssl", "none"]
ConfigSourceLiteral = Literal["database", "environment", "none"]


class EmailSettingsResponse(BaseModel):
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    has_smtp_password: bool = False
    smtp_security: SmtpSecurityLiteral = "starttls"
    from_email: Optional[str] = None
    from_name: str = "EYWAI"
    reply_to: Optional[str] = None
    support_recipients: List[str] = Field(default_factory=lambda: ["contact@eywai.fr"])
    is_active: bool = False
    is_configured: bool = False
    effective_source: ConfigSourceLiteral = "none"
    updated_at: Optional[str] = None


class EmailTestResponse(BaseModel):
    success: bool
    message: str
