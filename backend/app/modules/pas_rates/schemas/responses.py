"""Schémas de réponse — taux de prélèvement à la source."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel


class TauxLigne(BaseModel):
    employee_id: str
    nom: str
    prenom: str
    matricule: str = ""
    company_name: str = ""
    taux: Optional[float] = None
    type_taux: Optional[str] = None
    type_libelle: str = ""
    identifiant_taux: Optional[str] = None
    periode: Optional[str] = None
    source: Optional[str] = None
    statut: str
    statut_libelle: str = ""


class TauxVue(BaseModel):
    reference: str
    compteurs: Dict[str, int]
    lignes: List[TauxLigne]


class HistoriqueLigne(BaseModel):
    periode: Optional[str] = None
    taux: Optional[float] = None
    type_taux: Optional[str] = None
    type_libelle: str = ""
    source: Optional[str] = None
    source_fichier: Optional[str] = None
    applied_at: Optional[str] = None


class ApercuLigne(BaseModel):
    employee_id: Optional[str] = None
    nom: str
    prenom: str
    taux_actuel: Optional[float] = None
    taux_fichier: Optional[float] = None
    type_actuel: Optional[str] = None
    type_fichier: Optional[str] = None
    type_fichier_libelle: str = ""
    identifiant_fichier: Optional[str] = None
    nature: str


class ApercuReponse(BaseModel):
    periode: str
    siren: str
    fichier: str
    source: str
    compteurs: Dict[str, int]
    lignes: List[ApercuLigne]
    avertissements: List[str] = []


class ApplicationEchec(BaseModel):
    employee_id: str
    salarie: str
    erreur: str


class ApplicationReponse(BaseModel):
    periode: str
    appliques: int
    historique: int
    echecs: List[ApplicationEchec] = []
