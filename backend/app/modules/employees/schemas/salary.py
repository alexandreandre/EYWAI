"""Schémas API — mise à jour du salaire et historique."""

from datetime import date, datetime
from typing import Any, Dict, List, Literal

from pydantic import BaseModel, field_validator


PerimetreAugmentation = Literal["brut_seul", "brut_et_hs"]
TypeAugmentation = Literal["pourcentage", "montant_fixe"]


class UpdateSalaryRequest(BaseModel):
    nouveau_salaire: float  # montant brut mensuel
    motif: str | None = None
    effective_date: date
    type_augmentation: TypeAugmentation | None = None
    valeur_augmentation: float | None = None
    perimetre_augmentation: PerimetreAugmentation | None = None

    @field_validator("nouveau_salaire")
    @classmethod
    def salaire_positif(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Le salaire doit être positif")
        return v


class SalaryHistoryEntry(BaseModel):
    id: str
    ancien_salaire: Dict[str, Any]
    nouveau_salaire: Dict[str, Any]
    motif: str | None
    effective_date: date
    created_at: datetime


class SalaryUpdateResponse(BaseModel):
    success: bool
    ancien_salaire: float
    nouveau_salaire: float
    history_entry_id: str


class SimulationAugmentationRequest(BaseModel):
    type_augmentation: TypeAugmentation
    valeur: float  # % ou montant selon type
    effective_date: date
    perimetre_augmentation: PerimetreAugmentation = "brut_et_hs"

    @field_validator("valeur")
    @classmethod
    def valeur_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("La valeur doit être positive")
        return v


class SimulationResultat(BaseModel):
    ancien_salaire_brut: float
    nouveau_salaire_brut: float
    difference_brut: float
    ancien_net_estime: float
    nouveau_net_estime: float
    difference_net: float
    anciennes_charges_patronales: float
    nouvelles_charges_patronales: float
    difference_charges_patronales: float
    cout_total_employeur_avant: float
    cout_total_employeur_apres: float
    difference_cout_employeur: float
    taux_augmentation_reel: float  # % calculé même si montant fixe
    perimetre_augmentation: PerimetreAugmentation
    a_hs_structurelles: bool
    ancien_base_35h: float
    ancien_part_hs: float
    nouveau_base_35h: float
    nouveau_part_hs: float


class FiltresCollectifs(BaseModel):
    service_id: str | None = None
    statut: str | None = None  # Cadre / Non-Cadre
    contract_type: str | None = None  # CDI / CDD...
    anciennete_min_mois: int | None = None
    salaire_min: float | None = None
    salaire_max: float | None = None


class SimulationCollectiveRequest(BaseModel):
    filtres: FiltresCollectifs
    type_augmentation: TypeAugmentation
    valeur: float
    effective_date: date
    perimetre_augmentation: PerimetreAugmentation = "brut_et_hs"

    @field_validator("valeur")
    @classmethod
    def valeur_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("La valeur doit être positive")
        return v


class EmployeSimule(BaseModel):
    employee_id: str
    nom_complet: str
    poste: str | None
    service_id: str | None
    ancien_salaire_brut: float
    nouveau_salaire_brut: float
    difference_brut: float
    taux_augmentation_reel: float
    a_hs_structurelles: bool = False
    ancien_base_35h: float | None = None
    ancien_part_hs: float | None = None
    nouveau_base_35h: float | None = None
    nouveau_part_hs: float | None = None


class SimulationCollectiveResultat(BaseModel):
    nb_employes: int
    employes: List[EmployeSimule]
    masse_salariale_avant: float
    masse_salariale_apres: float
    difference_masse_salariale: float
    cout_charges_patronales_supplementaires: float
    cout_total_supplementaire: float  # diff brut + diff charges


class ApplicationCollectiveRequest(BaseModel):
    employee_ids: List[str]
    type_augmentation: TypeAugmentation
    valeur: float
    effective_date: date
    motif: str | None = None
    perimetre_augmentation: PerimetreAugmentation = "brut_et_hs"

    @field_validator("valeur")
    @classmethod
    def valeur_positive_collectif(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("La valeur doit être positive")
        return v


class ApplicationCollectiveResultat(BaseModel):
    nb_appliques: int
    nb_erreurs: int
    erreurs: List[str]


class GenerationAvenantsLotRequest(BaseModel):
    employee_ids: List[str]
    effective_date: date
    motif: str | None = None
    # template_id optionnel — si absent, template EYWAI par défaut
    template_id: str | None = None
    nouveau_salaire_par_employe: Dict[str, float] | None = None


class GenerationAvenantsLotResultat(BaseModel):
    nb_generes: int
    nb_erreurs: int
    document_ids: List[str]  # IDs des documents créés
    erreurs: List[str]


__all__ = [
    "PerimetreAugmentation",
    "TypeAugmentation",
    "UpdateSalaryRequest",
    "SalaryHistoryEntry",
    "SalaryUpdateResponse",
    "SimulationAugmentationRequest",
    "SimulationResultat",
    "FiltresCollectifs",
    "SimulationCollectiveRequest",
    "EmployeSimule",
    "SimulationCollectiveResultat",
    "ApplicationCollectiveRequest",
    "ApplicationCollectiveResultat",
    "GenerationAvenantsLotRequest",
    "GenerationAvenantsLotResultat",
]
