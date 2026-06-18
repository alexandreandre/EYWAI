"""
Schémas Pydantic entrée API du module companies.

Définitions canoniques : settings, CRUD entreprise (create/update).
Comportement identique aux anciennes définitions (api/routers/company, api/routers/super_admin).
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# ----- Company settings (PATCH /api/company/settings) -----


class PublicHolidaysSettingsUpdate(BaseModel):
    """Jours fériés légaux chômés par l'entreprise."""

    observed_holiday_ids: Optional[List[str]] = Field(
        None,
        description="IDs des fériés légaux chômés (catalogue France métropolitaine).",
    )


class CompanySettingsUpdate(BaseModel):
    """
    Body pour PATCH /api/company/settings.
    Compatible avec le comportement actuel (dict avec medical_follow_up_enabled, etc.).
    """

    medical_follow_up_enabled: Optional[bool] = Field(
        None, description="Activation du module suivi médical"
    )
    public_holidays: Optional[PublicHolidaysSettingsUpdate] = Field(
        None, description="Jours fériés légaux observés au planning"
    )
    model_config = {"extra": "allow"}

    @field_validator("public_holidays", mode="before")
    @classmethod
    def coerce_public_holidays(cls, value: Any) -> Any:
        if value is None or isinstance(value, PublicHolidaysSettingsUpdate):
            return value
        if isinstance(value, dict):
            return PublicHolidaysSettingsUpdate(**value)
        raise ValueError("public_holidays doit être un objet.")

    def to_settings_delta(self) -> Dict[str, Any]:
        """Retourne un dict des champs fournis (non-None) pour merge avec settings existants."""
        data = self.model_dump(exclude_none=True)
        if "public_holidays" in data and isinstance(data["public_holidays"], dict):
            ph = data["public_holidays"]
            if ph.get("observed_holiday_ids") is None and "observed_holiday_ids" in ph:
                data["public_holidays"] = {}
            elif not ph:
                data.pop("public_holidays", None)
        return data


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


class CompanyDetailsUpdate(BaseModel):
    """Mise à jour administrative depuis Mon Entreprise (RH / admin)."""

    company_name: Optional[str] = None
    raison_sociale: Optional[str] = None
    siret: Optional[str] = None
    siren: Optional[str] = None
    code_naf: Optional[str] = None
    naf_ape: Optional[str] = None
    legal_form: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    website: Optional[str] = None
    urssaf_number: Optional[str] = None
    adresse_rue: Optional[str] = None
    adresse_code_postal: Optional[str] = None
    adresse_ville: Optional[str] = None
    nom_signataire_rh: Optional[str] = None
    qualite_signataire_rh: Optional[str] = None
    service_sante_travail_nom: Optional[str] = None
    service_sante_travail_adresse_rue: Optional[str] = None
    service_sante_travail_adresse_code_postal: Optional[str] = None
    service_sante_travail_adresse_ville: Optional[str] = None
    service_sante_travail_telephone: Optional[str] = None
    service_sante_travail_email: Optional[str] = None
    dsn_sync_mode: Optional[str] = Field(
        None,
        description="external | native | transition — source paie pour alertes DSN",
    )

    def to_update_dict(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=True)


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
