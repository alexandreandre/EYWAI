"""Schéma réponse — récapitulatif des congés et absences de la société (lot L21)."""

from typing import Dict, List, Optional

from pydantic import BaseModel


class RecapCongesColonne(BaseModel):
    cle: str
    libelle: str
    source: str


class RecapCongesSalarie(BaseModel):
    employee_id: str
    matricule: Optional[str] = None
    prenom: str
    nom: str
    jours: Dict[str, float]
    total_jours: float
    solde_cp_n1: Optional[float] = None
    solde_cp_n: Optional[float] = None
    #: Reprise de solde dans la période (AAAA-MM-JJ) : chiffres d'avant non fiables.
    reprise_au: Optional[str] = None


class RecapCongesResponse(BaseModel):
    debut: str
    fin: str
    colonnes: List[RecapCongesColonne]
    source_soldes: str
    note_arrets: str
    note_reprise: str
    date_des_soldes: str
    salaries: List[RecapCongesSalarie]
    totaux: Dict[str, float]
    aucun_jour: bool
