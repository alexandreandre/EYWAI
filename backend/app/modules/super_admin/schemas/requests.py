"""
Schémas requête API du module super_admin.

Définitions canoniques pour les routes super_admin.
- CompanyCreate, CompanyCreateWithAdmin, CompanyUpdate : définis localement
  (contrat identique à POST/PATCH companies, module autonome).
- UserCreate, ReductionFillonRequest : spécifiques super_admin.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, EmailStr

__all__ = [
    "CompanyCreate",
    "CompanyCreateWithAdmin",
    "CompanyUpdate",
    "UserCreate",
    "ReductionFillonRequest",
    "RunTestsRequest",
]


# ----- Schémas company (locaux pour autonomie du module, contrat HTTP inchangé) -----


class CompanyCreate(BaseModel):
    """Création d'une entreprise (sans admin)."""
    company_name: str
    siret: Optional[str] = None
    siren: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[Dict[str, str]] = None
    logo_url: Optional[str] = None
    logo_scale: Optional[float] = 1.0


class CompanyCreateWithAdmin(BaseModel):
    """Création d'une entreprise avec un admin associé."""
    company_name: str
    siret: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    logo_url: Optional[str] = None
    logo_scale: Optional[float] = 1.0
    admin_email: Optional[EmailStr] = None
    admin_password: Optional[str] = None
    admin_first_name: Optional[str] = None
    admin_last_name: Optional[str] = None


class CompanyUpdate(BaseModel):
    """Mise à jour partielle d'une entreprise."""
    company_name: Optional[str] = None
    siret: Optional[str] = None
    siren: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[Dict[str, str]] = None
    logo_url: Optional[str] = None
    logo_scale: Optional[float] = None
    is_active: Optional[bool] = None


# ----- Schémas spécifiques super_admin -----


class UserCreate(BaseModel):
    """Body POST /companies/{company_id}/users — création utilisateur par super admin."""
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    role: str


class ReductionFillonRequest(BaseModel):
    """Body POST /reduction-fillon/calculate."""
    employee_id: str
    month: int
    year: int


class RunTestsRequest(BaseModel):
    """Body POST /tests/run — cibles pytest (relatif à backend_api) ou Playwright (préfixe ``pw:``)."""
    targets: list[str]
