"""Schémas de requête — configuration e-mail plateforme."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

SmtpSecurityLiteral = Literal["starttls", "ssl", "none"]


class EmailSettingsUpdate(BaseModel):
    """Body PUT /api/super-admin/email-settings."""

    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = Field(None, ge=1, le=65535)
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = Field(
        None,
        description="Mot de passe SMTP ; laisser vide pour conserver l'existant.",
    )
    smtp_security: Optional[SmtpSecurityLiteral] = None
    from_email: Optional[str] = None
    from_name: Optional[str] = None
    reply_to: Optional[str] = None
    support_recipients: Optional[List[str]] = None
    is_active: Optional[bool] = None

    model_config = {"extra": "ignore"}


class EmailSettingsTestRequest(BaseModel):
    """Body POST /api/super-admin/email-settings/test."""

    to_email: str = Field(..., min_length=3, description="Adresse de test")

    model_config = {"extra": "ignore"}
