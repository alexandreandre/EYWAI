"""Schémas des formules de prévoyance de la société."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Categorie = Literal["cadre", "non_cadre", "tous"]
Base = Literal["brut_plafonne", "tranche_2", "brut"]


class LignePrevoyance(BaseModel):
    """Une ligne, comme sur la fiche : taux en fraction ; les autres clés passent."""

    model_config = ConfigDict(extra="allow")

    libelle: str
    salarial: float = 0.0
    patronal: float = 0.0
    forfait_social: float = 0.0
    base: Base | None = None

    @field_validator("libelle")
    @classmethod
    def _libelle(cls, v: str) -> str:
        v = (v or "").strip()
        if len(v) < 2:
            raise ValueError("Libellé requis.")
        return v

    @field_validator("salarial", "patronal", "forfait_social")
    @classmethod
    def _taux(cls, v: float) -> float:
        if v < 0 or v > 1:
            raise ValueError("Un taux se saisit en fraction, entre 0 et 1.")
        return v

    def en_ligne(self) -> dict:
        ligne = self.model_dump(exclude_none=True)
        return ligne


class FormuleCreate(BaseModel):
    libelle: str = Field(min_length=2)
    statut_categoriel: Categorie = "tous"
    lignes: list[LignePrevoyance] = Field(default_factory=list)


class FormuleUpdate(BaseModel):
    libelle: str | None = Field(default=None, min_length=2)
    statut_categoriel: Categorie | None = None
    lignes: list[LignePrevoyance] | None = None
