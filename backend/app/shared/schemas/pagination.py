"""
Pagination : paramètres et réponses génériques.

Réutilisables par tout module qui expose des listes paginées.
"""
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

from app.shared.schemas.base import SharedBaseModel

T = TypeVar("T")


class PaginationParams(SharedBaseModel):
    """Paramètres de pagination (query)."""

    page: int = Field(1, ge=1, description="Numéro de page")
    page_size: int = Field(20, ge=1, le=100, description="Taille de page")


class PaginatedResponse(BaseModel, Generic[T]):
    """Réponse paginée générique."""

    items: list[T]
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        if self.page_size <= 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size
