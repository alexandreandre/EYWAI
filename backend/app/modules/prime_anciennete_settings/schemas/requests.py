"""Schémas de requête — paramètres prime d'ancienneté entreprise."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

ProrataMode = Literal["heures_contrat", "jours_forfait", "none"]


class PrimeAncienneteSettingsUpdate(BaseModel):
    valeur_point_override: Optional[float] = None
    min_annees_override: Optional[float] = None
    prorata_mode_override: Optional[ProrataMode] = None
