"""
Schémas Pydantic entrée API du module companies.

Définitions canoniques : settings, CRUD entreprise (create/update).
Comportement identique aux anciennes définitions (api/routers/company, api/routers/super_admin).
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel, EmailStr, Field


# ----- Company settings (PATCH /api/company/settings) -----


class CompanySettingsUpdate(BaseModel):
    """
    Body pour PATCH /api/company/settings.
    Compatible avec le comportement actuel (dict avec medical_follow_up_enabled, etc.).
    """

    medical_follow_up_enabled: Optional[bool] = Field(
        None, description="Activation du module suivi médical"
    )
    model_config = {"extra": "allow"}

    def to_settings_delta(self) -> Dict[str, Any]:
        """Retourne un dict des champs fournis (non-None) pour merge avec settings existants."""
        return self.model_dump(exclude_none=True)


# ----- CRUD entreprise (Super Admin) -----


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
