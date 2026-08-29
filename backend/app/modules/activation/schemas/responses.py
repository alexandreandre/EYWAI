"""Schémas de réponses du module activation."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class InvitationSentResponse(BaseModel):
    invited_at: str
    email: str  # toujours masqué
    expires_at: str


class InvitationStatusResponse(BaseModel):
    status: str  # jamais_invite | invite | active
    invited_at: Optional[str] = None
    expires_at: Optional[str] = None
    expired: bool = False
    email: Optional[str] = None  # toujours masqué


class ActivationVerifyResponse(BaseModel):
    prenom: str
    societe: str
    email_requise: bool = False


class ActivationCompleteResponse(BaseModel):
    message: str
