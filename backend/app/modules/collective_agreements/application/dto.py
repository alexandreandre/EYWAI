"""
DTOs applicatifs pour collective_agreements.

Entrées/sorties des commandes et requêtes (sans dépendance aux schémas API).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, List, Optional


# --- Entrées commandes ---


@dataclass
class CatalogCreateInput:
    """Entrée création d'une entrée catalogue."""

    name: str
    idcc: str
    description: Optional[str]
    sector: Optional[str]
    effective_date: Optional[date]
    is_active: bool
    rules_pdf_path: Optional[str]
    rules_pdf_filename: Optional[str]


@dataclass
class CatalogUpdateInput:
    """Entrée mise à jour partielle catalogue."""

    name: Optional[str] = None
    idcc: Optional[str] = None
    description: Optional[str] = None
    sector: Optional[str] = None
    effective_date: Optional[date] = None
    rules_pdf_path: Optional[str] = None
    rules_pdf_filename: Optional[str] = None
    is_active: Optional[bool] = None


# --- Sorties (pour réponse API) ---


@dataclass
class CatalogItemOutput:
    """Sortie catalogue (avec rules_pdf_url si présent)."""

    data: dict[str, Any]


@dataclass
class AssignmentsOutput:
    """Liste assignations avec détails (my-company ou all-assignments)."""

    items: List[dict[str, Any]]


@dataclass
class QuestionOutput:
    """Réponse à une question chat (answer + agreement_name)."""

    answer: str
    agreement_name: str


@dataclass
class UploadUrlOutput:
    """URL signée d'upload (path + signedURL)."""

    path: str
    signed_url: str
