"""
Entités du domaine company_groups.

Structure cible pour la migration. Alignée sur la table company_groups
et les réponses API (api/routers/company_groups.py).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class CompanyGroup:
    """
    Agrégat groupe d'entreprises.
    Champs alignés sur la table company_groups (id, group_name, siren, description,
    logo_url, logo_scale, settings, is_active, created_at, updated_at).
    """

    id: str
    group_name: str
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    siren: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    logo_scale: float = 1.0
    settings: Optional[Dict[str, Any]] = None


@dataclass
class CompanyInGroupRef:
    """Référence à une entreprise dans un groupe (pour agrégat)."""

    id: str
    company_name: str
    siret: Optional[str] = None
    is_active: bool = True
