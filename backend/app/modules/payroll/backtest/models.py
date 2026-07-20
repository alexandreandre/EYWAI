"""Modèles de domaine pour le backtest paie."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Verdict(str, Enum):
    PARFAIT = "PARFAIT"
    OK = "OK"
    TOLERE = "TOLERE"
    ANOMALIE = "ANOMALIE"
    KNOWN_GAP = "KNOWN_GAP"
    QUARANTAINE = "QUARANTAINE"


class RemediationColor(str, Enum):
    VERT = "VERT"
    ORANGE = "ORANGE"
    ROUGE = "ROUGE"


class EmployeeConvergenceStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PARFAIT = "PARFAIT"
    OK = "OK"
    TOLERE = "TOLERE"
    QUARANTAINE = "QUARANTAINE"
    VALIDATED = "validated"


@dataclass
class ReferenceRubricLine:
    libelle: str
    base: Optional[float] = None
    taux_salarial: Optional[float] = None
    montant_salarial: Optional[float] = None
    montant_patronal: Optional[float] = None


@dataclass
class ReferenceBulletin:
    matricule: str
    nom_complet: str = ""
    nir: str = ""
    salaire_brut: Optional[float] = None
    net_imposable: Optional[float] = None
    montant_net_social: Optional[float] = None
    net_avant_impot: Optional[float] = None
    pas_montant: Optional[float] = None
    pas_taux: Optional[float] = None
    net_a_payer: Optional[float] = None
    cout_total_employeur: Optional[float] = None
    date_paiement: Optional[str] = None
    cp_solde_n: Optional[float] = None
    coefficient: Optional[int] = None
    rubriques: List[ReferenceRubricLine] = field(default_factory=list)
    raw_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "matricule": self.matricule,
            "nom_complet": self.nom_complet,
            "salaire_brut": self.salaire_brut,
            "net_imposable": self.net_imposable,
            "montant_net_social": self.montant_net_social,
            "net_avant_impot": self.net_avant_impot,
            "pas_montant": self.pas_montant,
            "pas_taux": self.pas_taux,
            "net_a_payer": self.net_a_payer,
            "cout_total_employeur": self.cout_total_employeur,
            "date_paiement": self.date_paiement,
            "cp_solde_n": self.cp_solde_n,
            "coefficient": self.coefficient,
            "rubriques": [
                {
                    "libelle": r.libelle,
                    "base": r.base,
                    "taux_salarial": r.taux_salarial,
                    "montant_salarial": r.montant_salarial,
                    "montant_patronal": r.montant_patronal,
                }
                for r in self.rubriques
            ],
        }


@dataclass
class DiscrepancyLine:
    field_key: str
    label: str
    tier: str
    reference_value: Optional[float]
    actual_value: Optional[float]
    delta: float
    tolerance: float
    verdict: Verdict
    is_systemic: bool = False
    notes: str = ""


@dataclass
class DiscrepancyReport:
    matricule: str
    employee_id: Optional[str] = None
    employee_name: str = ""
    lines: List[DiscrepancyLine] = field(default_factory=list)
    overall_verdict: Verdict = Verdict.ANOMALIE
    tier_s_max_delta: float = 0.0
    correction_attempts: int = 0

    @property
    def has_tier_s_anomaly(self) -> bool:
        return any(
            ln.tier == "S" and ln.verdict in (Verdict.ANOMALIE, Verdict.QUARANTAINE)
            for ln in self.lines
        )


@dataclass
class RemediationProposal:
    pattern_id: str
    color: RemediationColor
    description: str
    confidence: float
    affected_matricules: List[str] = field(default_factory=list)
    action_type: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
