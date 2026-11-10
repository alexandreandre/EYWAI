"""Corps des requêtes de la relecture IA."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LancerRelectureBody(BaseModel):
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    company_ids: list[str]
    # Vide : tous les salariés à relire des sociétés cochées.
    employee_ids: list[str] | None = Field(default=None, max_length=2000)


class MarquerVuBody(BaseModel):
    bulletin_relu_id: str
    ligne: str = Field(min_length=1, max_length=500)
