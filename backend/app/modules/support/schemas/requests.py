from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, field_validator


class TicketCreate(BaseModel):
    module: str
    request_type: str
    urgency: Literal["critique", "elevee", "normale", "faible"]
    description: str
    context: Optional[str] = None

    @field_validator("description")
    @classmethod
    def description_length(cls, v: str) -> str:
        if len(v) < 30:
            raise ValueError("La description doit contenir au minimum 30 caractères.")
        if len(v) > 2000:
            raise ValueError("La description ne peut pas dépasser 2000 caractères.")
        return v


class TicketStatusUpdate(BaseModel):
    status: Literal["en_cours", "resolu", "cloture"]
