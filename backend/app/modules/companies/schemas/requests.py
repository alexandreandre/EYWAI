"""
Schémas Pydantic entrée API du module companies.

Définitions canoniques : settings, CRUD entreprise (create/update).
Comportement identique aux anciennes définitions (api/routers/company, api/routers/super_admin).
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator
from pydantic_core import PydanticCustomError

from app.modules.companies.domain.parametres_paie import (
    CLES_SETTINGS,
    valider_date_paiement,
    valider_effectif,
    valider_jour_solidarite,
    valider_taux_assurance_chomage,
)


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
    compensation_heures_entre_semaines: Optional[bool] = Field(
        None,
        description=(
            "Option société : les heures manquantes d'une semaine se compensent avec les "
            "heures supplémentaires des autres semaines de la fenêtre de paie, sans retenue. "
            "Choix explicite de l'entreprise ; la règle légale reste hebdomadaire."
        ),
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
    taux_at_mp: Optional[float] = None
    paie_jour_de_fin: Optional[int] = None
    paie_occurrence: Optional[int] = None
    dsn_sync_mode: Optional[str] = Field(
        None,
        description="external | native | transition — source paie pour alertes DSN",
    )
    effectif: Optional[int] = Field(
        None,
        description=(
            "Effectif retenu pour les seuils (11, 20, 50 salariés) : effectif moyen "
            "de l'année précédente. Entier, 0 ou plus ; jamais vidé."
        ),
    )
    taux_assurance_chomage: Optional[float] = Field(
        None,
        description=(
            "settings.taux_assurance_chomage : taux bonus-malus notifié par l'URSSAF, "
            "en %, entre 2,95 et 5. null retire la clé (taux normal du barème)."
        ),
    )
    date_paiement: Optional[str] = Field(
        None,
        description=(
            "settings.date_paiement : dernier_jour_du_mois | arrete_des_variables. "
            "null retire la clé (comportement historique)."
        ),
    )
    jour_solidarite: Optional[str] = Field(
        None,
        description=(
            "settings.jour_solidarite : date AAAA-MM-JJ de l'année en cours. "
            "null retire la clé (le moteur prend le lundi de Pentecôte)."
        ),
    )

    @field_validator("effectif", mode="before")
    @classmethod
    def _effectif(cls, valeur: Any) -> int:
        return _en_erreur_lisible(valider_effectif, valeur)

    @field_validator("taux_assurance_chomage", mode="before")
    @classmethod
    def _taux_assurance_chomage(cls, valeur: Any) -> Optional[float]:
        return _en_erreur_lisible(valider_taux_assurance_chomage, valeur)

    @field_validator("date_paiement", mode="before")
    @classmethod
    def _date_paiement(cls, valeur: Any) -> Optional[str]:
        return _en_erreur_lisible(valider_date_paiement, valeur)

    @field_validator("jour_solidarite", mode="before")
    @classmethod
    def _jour_solidarite(cls, valeur: Any) -> Optional[str]:
        return _en_erreur_lisible(valider_jour_solidarite, valeur)

    def to_update_dict(self) -> Dict[str, Any]:
        """Champs fournis. Pour les réglages de settings, un null explicite est
        gardé : il demande le retrait de la clé."""
        data = self.model_dump(exclude_none=True, exclude=set(CLES_SETTINGS))
        for cle in CLES_SETTINGS:
            if cle in self.model_fields_set:
                data[cle] = getattr(self, cle)
        return data


def _en_erreur_lisible(valider: Any, valeur: Any) -> Any:
    """La phrase métier telle quelle dans le 422, sans le préfixe « Value error »."""
    try:
        return valider(valeur)
    except ValueError as exc:
        raise PydanticCustomError("parametre_paie_invalide", str(exc)) from None


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
