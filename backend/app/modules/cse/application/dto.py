# app/modules/cse/application/dto.py
"""
DTOs CSE — objets de transfert pour la couche application.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ExportFile:
    """Résultat d'un export fichier (Excel/PDF) — contenu, nom, type MIME."""
    content: bytes
    filename: str
    media_type: str


@dataclass(frozen=True)
class MinutesPathResult:
    """Résultat de la récupération du chemin PV d'une réunion."""
    pdf_path: Optional[str]
