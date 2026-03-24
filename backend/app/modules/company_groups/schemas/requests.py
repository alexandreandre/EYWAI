"""
Schémas Pydantic entrée API du module company_groups.

Définitions canoniques (migrées depuis api/routers/company_groups.py).
Contrat identique : create/update groupe, bulk add, manage user access.
Compatibilité : schemas.company_groups réexporte depuis ce module.
"""
from typing import List, Optional

from pydantic import BaseModel


class CompanyGroupCreate(BaseModel):
    """Body pour POST / et PATCH /{group_id}."""
    group_name: str
    siren: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None


class BulkAddCompaniesRequest(BaseModel):
    """Body pour POST /{group_id}/companies/bulk."""
    company_ids: List[str]


class UserCompanyAccess(BaseModel):
    """Un accès utilisateur à une entreprise (pour manage-user-access)."""
    company_id: str
    role: str  # 'admin', 'rh', 'collaborateur', 'collaborateur_rh'


class ManageUserAccessRequest(BaseModel):
    """Body pour POST /{group_id}/manage-user-access."""
    user_email: str
    accesses: List[UserCompanyAccess]
    first_name: Optional[str] = None
    last_name: Optional[str] = None
