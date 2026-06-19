"""Schémas de réponse — paramètres prime d'ancienneté entreprise."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

ProrataMode = Literal["heures_contrat", "jours_forfait", "none"]


class PrimeAncienneteOverrides(BaseModel):
    valeur_point_override: Optional[float] = None
    min_annees_override: Optional[float] = None
    prorata_mode_override: Optional[ProrataMode] = None


class PrimeAncienneteCcResolved(BaseModel):
    idcc: Optional[str] = None
    formule: Optional[str] = None
    valeur_point_zone: Optional[float] = None
    zone_libelle: Optional[str] = None
    min_annees: float = 0.0
    statuts_exclus: list[str] = Field(default_factory=list)
    prorata_enabled: bool = False
    prorata_mode: ProrataMode = "none"


class PrimeAncienneteSettings(BaseModel):
    overrides: PrimeAncienneteOverrides
    cc_resolved: PrimeAncienneteCcResolved
    code_postal: Optional[str] = None
