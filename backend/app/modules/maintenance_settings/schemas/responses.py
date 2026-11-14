"""Schémas de réponse API maintien de salaire."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


SubrogationMode = Literal["when_maintien", "automatic", "at_mp_only", "per_case", "never"]
BaremeConvention = Literal["plasturgie_0292", "metallurgie_3248"]


class MaintenanceSettings(BaseModel):
    """Configuration maintien de salaire (ligne BDD ou valeurs par défaut)."""

    model_config = ConfigDict(from_attributes=True)

    id: Optional[str] = None
    company_id: str
    apply_legal_maintenance: bool = True
    min_seniority_months: int = Field(default=12, ge=0, le=120)
    min_seniority_months_at_mp: int = Field(default=3, ge=0, le=120)
    employer_waiting_days: int = Field(default=7, ge=0, le=30)
    seniority_extension_enabled: bool = False
    remove_employer_waiting: bool = False
    annual_unique_waiting: bool = False
    maintain_100_percent: bool = False
    differentiated_at_illness: bool = False
    maintain_by_category: bool = False
    no_seniority_condition: bool = False
    custom_duration_days: Optional[int] = None
    subrogation_mode: SubrogationMode = "when_maintien"
    provident_relay_days: Optional[int] = None
    provident_maintenance_rate: Optional[float] = Field(default=None, ge=0, le=1)
    provident_cadre_only: bool = True
    #: Jours de carence payés par l'employeur par année civile (plasturgie : 3).
    paid_waiting_days_per_year: Optional[int] = Field(default=None, ge=0, le=30)
    paid_waiting_min_seniority_months: int = Field(default=12, ge=0, le=120)
    #: Maintien en jours ouvrés : 7 h + quote-part d'heures sup structurelles,
    #: week-ends non maintenus, IJSS hors bulletin.
    maintain_working_days: bool = False
    #: Maintien au-delà de la convention pendant les congés de maternité, de
    #: paternité et d'adoption : 100 % dès le premier jour. La convention
    #: s'applique d'office (payroll/engine/parentalite_convention.py) ; éteint
    #: par défaut, le réglage ne l'étend pas.
    maintain_parental_leave: bool = False
    #: Arrêt sans subrogation : la CPAM verse les IJSS au salarié. True : Martine
    #: ne verse que le complément, IJSS des jours maintenus déduites (règle
    #: légale, D1226-5). False : le salaire garanti en entier.
    deduire_ijss_sans_subrogation: bool = True
    #: Sans subrogation : maintien versé seulement quand les IJ du mois sont
    #: saisies, c'est-à-dire déclarées par le salarié (plasturgie, 13/11).
    maintien_apres_ij_recues: bool = False
    #: Barème de la convention (24/10/2026) : None, les réglages manuels ;
    #: "plasturgie_0292", les paliers de la plasturgie (non-cadres et cadres).
    bareme_convention: Optional[BaremeConvention] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
