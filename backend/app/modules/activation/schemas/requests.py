"""Schémas de requêtes du module activation."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ActivationVerifyRequest(BaseModel):
    token: str = Field(..., min_length=1, max_length=256)
    email: Optional[str] = Field(None, max_length=320)


class ActivationCompleteRequest(BaseModel):
    token: str = Field(..., min_length=1, max_length=256)
    password: str = Field(..., max_length=256)
    email: Optional[str] = Field(None, max_length=320)
