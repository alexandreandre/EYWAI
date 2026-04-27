"""Schémas requête — module Équipes."""

from typing import Optional

from pydantic import BaseModel, field_validator

PALETTE_COLORS = [
    "#6366f1",
    "#8b5cf6",
    "#ec4899",
    "#ef4444",
    "#f97316",
    "#eab308",
    "#22c55e",
    "#14b8a6",
    "#06b6d4",
    "#3b82f6",
    "#64748b",
    "#78716c",
]


class TeamCreate(BaseModel):
    name: str
    description: Optional[str] = None
    color: Optional[str] = "#6366f1"
    manager_employee_id: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Le nom de l'équipe est obligatoire.")
        if len(v.strip()) > 80:
            raise ValueError("Le nom ne peut pas dépasser 80 caractères.")
        return v.strip()

    @field_validator("color")
    @classmethod
    def color_in_palette(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in PALETTE_COLORS:
            raise ValueError("Couleur non autorisée.")
        return v


class TeamUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    manager_employee_id: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v.strip():
                raise ValueError("Le nom ne peut pas être vide.")
            if len(v.strip()) > 80:
                raise ValueError("Le nom ne peut pas dépasser 80 caractères.")
            return v.strip()
        return v

    @field_validator("color")
    @classmethod
    def color_in_palette(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in PALETTE_COLORS:
            raise ValueError("Couleur non autorisée.")
        return v


class TeamArchiveRequest(BaseModel):
    reason: Optional[str] = None


class AssignEmployeeTeamBody(BaseModel):
    team_id: Optional[str] = None
