"""
Schémas Pydantic sortie API du module company_groups.

Définitions canoniques (migrées depuis api/routers/company_groups.py).
Contrat identique : groupe, groupe avec companies, liste.
Compatibilité : schemas.company_groups réexporte depuis ce module.
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class CompanyGroupBase(BaseModel):
    """Champs communs groupe (sans id, timestamps)."""
    group_name: str
    siren: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None


class CompanyGroup(CompanyGroupBase):
    """Réponse groupe (création, mise à jour)."""
    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CompanyInGroup(BaseModel):
    """Entreprise dans un groupe (pour GroupWithCompanies). Comportement identique au router."""
    id: str
    company_name: str
    siret: Optional[str]
    is_active: bool


class GroupWithCompanies(CompanyGroup):
    """Groupe avec liste des entreprises (GET my-groups, GET /{group_id})."""
    companies: List[CompanyInGroup]
