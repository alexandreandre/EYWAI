"""
Extraction mutuelle / prévoyance depuis une DSN (blocs affiliation + cotisations PSC).

Références norme DSN :
- S21.G00.70 : affiliation salarié (code option = pack, code population = catégorie)
- S21.G00.78 / S21.G00.81 : cotisations individuelles (code 059 = PSC)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.modules.dsn_import.domain.model import AffiliationBlock, ContratBlock
from app.modules.dsn_import.domain.normalize import map_statut_cadre

PSC_COTISATION_CODES = {"059", "031", "032", "033"}
MUTUELLE_ORGANISME_RE = re.compile(r"^\d{9}$")
PREVOYANCE_ORGANISME_RE = re.compile(r"^P\d", re.IGNORECASE)


@dataclass
class PscCotisationAmounts:
    montant_salarial: float = 0.0
    montant_patronal: float = 0.0
    base: float = 0.0
    code: str = "059"


@dataclass
class EmployeePscData:
    """Données PSC extraites pour un contrat salarié."""

    mutuelle_adhesion: bool = False
    prevoyance_adhesion: bool = False
    pack_couverture: Optional[str] = None
    code_option_dsn: Optional[str] = None
    code_population_dsn: Optional[str] = None
    reference_contrat_dsn: Optional[str] = None
    code_organisme_dsn: Optional[str] = None
    code_delegataire_dsn: Optional[str] = None
    mutuelle_amounts: Optional[PscCotisationAmounts] = None
    prevoyance_amounts: Optional[PscCotisationAmounts] = None
    prevoyance_lignes: List[Dict[str, Any]] = field(default_factory=list)
    mutuelle_lignes: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def infer_pack_from_code_option(code_option: str, nb_enfants: int = 0, nb_adultes: int = 0) -> Optional[str]:
    """Infère isole / famille / duo depuis le code option DSN ou les ayants-droit."""
    code = (code_option or "").strip().upper()
    if not code and (nb_enfants > 0 or nb_adultes > 1):
        return "famille"
    if not code:
        return None

    if any(k in code for k in ("FAM", "FAMILLE", "UNIV", "UNIVERSEL")):
        return "famille"
    if any(k in code for k in ("ISO", "ISOL", "IND", "INDIV", "SALAR")):
        return "isole"
    if "DUO" in code or "COUPLE" in code:
        return "duo"
    if code in {"01", "1", "I"}:
        return "isole"
    if code in {"02", "2", "F"}:
        return "famille"
    if nb_enfants > 0 or nb_adultes > 1:
        return "famille"
    return "autre"


def _statut_from_population(code_population: str, contrat_statut: str) -> str:
    pop = (code_population or "").strip().upper()
    if pop in {"01", "CAD", "CADRE", "03", "04"}:
        return "Cadre"
    if pop in {"02", "NC", "NON", "ETAM", "05"}:
        return "Non-Cadre"
    return map_statut_cadre(contrat_statut)


def _is_prevoyance_organisme(code: str) -> bool:
    return bool(PREVOYANCE_ORGANISME_RE.match((code or "").strip()))


def _is_mutuelle_organisme(code: str) -> bool:
    clean = (code or "").strip()
    return bool(MUTUELLE_ORGANISME_RE.match(clean)) and not _is_prevoyance_organisme(clean)


def _collect_psc_cotisations(contrat: ContratBlock) -> List[PscCotisationAmounts]:
    amounts: List[PscCotisationAmounts] = []
    for ver in contrat.versements:
        for cot in ver.cotisations:
            code = (cot.code or "").strip()
            if code in PSC_COTISATION_CODES or code.endswith("059"):
                if cot.montant_salarial or cot.montant_patronal:
                    amounts.append(
                        PscCotisationAmounts(
                            montant_salarial=cot.montant_salarial,
                            montant_patronal=cot.montant_patronal,
                            base=cot.base,
                            code=code,
                        )
                    )
        for ci in ver.cotisations_individuelles:
            code = (ci.code or "").strip()
            if code in PSC_COTISATION_CODES or code.endswith("059"):
                if ci.montant_salarial or ci.montant_patronal:
                    amounts.append(
                        PscCotisationAmounts(
                            montant_salarial=ci.montant_salarial,
                            montant_patronal=ci.montant_patronal,
                            base=ci.montant_assiette,
                            code=code,
                        )
                    )
    return amounts


def _classify_amounts(
    amounts: List[PscCotisationAmounts],
    affiliation: Optional[AffiliationBlock],
    statut: str,
) -> tuple[Optional[PscCotisationAmounts], Optional[PscCotisationAmounts]]:
    """Sépare montants mutuelle (forfait €) et prévoyance (% ou forfait selon contexte)."""
    if not amounts:
        return None, None

    org = affiliation.code_organisme if affiliation else ""
    if _is_mutuelle_organisme(org):
        return amounts[0], amounts[1] if len(amounts) > 1 else None
    if _is_prevoyance_organisme(org):
        return None, amounts[0]

    mutuelle: Optional[PscCotisationAmounts] = None
    prevoyance: Optional[PscCotisationAmounts] = None
    for amt in amounts:
        has_taux = amt.base > 0 and (
            abs(amt.montant_patronal / amt.base - round(amt.montant_patronal / amt.base, 4)) < 0.001
        )
        is_percent_like = (
            amt.base > 100
            and amt.montant_patronal > 0
            and amt.montant_patronal / amt.base < 0.15
        )
        if is_percent_like or (statut == "Cadre" and has_taux and not mutuelle):
            prevoyance = prevoyance or amt
        else:
            mutuelle = mutuelle or amt
    if mutuelle is None and prevoyance is None and amounts:
        mutuelle = amounts[0]
    return mutuelle, prevoyance


def _build_prevoyance_lignes(
    prev_amounts: PscCotisationAmounts,
    statut: str,
) -> List[Dict[str, Any]]:
    if statut != "Cadre" or prev_amounts.base <= 0:
        return []
    taux_sal = round(prev_amounts.montant_salarial / prev_amounts.base, 6) if prev_amounts.base else 0.0
    taux_pat = round(prev_amounts.montant_patronal / prev_amounts.base, 6) if prev_amounts.base else 0.0
    if taux_pat <= 0 and taux_sal <= 0:
        return []
    return [
        {
            "id": "prevoyance_dsn",
            "libelle": "Prévoyance (import DSN)",
            "salarial": taux_sal,
            "patronal": max(taux_pat, 0.015) if taux_pat <= 0 else taux_pat,
            "forfait_social": 0.08,
            "base": "brut_plafonne",
        }
    ]


def extract_psc_from_contrat(contrat: ContratBlock) -> EmployeePscData:
    """Extrait mutuelle / prévoyance depuis affiliations et cotisations PSC du contrat."""
    result = EmployeePscData()
    affiliation = contrat.affiliations[0] if contrat.affiliations else None

    if affiliation:
        result.code_option_dsn = affiliation.code_option or None
        result.code_population_dsn = affiliation.code_population or None
        result.reference_contrat_dsn = affiliation.reference_contrat or None
        result.code_organisme_dsn = affiliation.code_organisme or None
        result.code_delegataire_dsn = affiliation.code_delegataire or None
        result.pack_couverture = infer_pack_from_code_option(
            affiliation.code_option,
            affiliation.nb_enfants,
            affiliation.nb_adultes,
        )

    statut = _statut_from_population(
        affiliation.code_population if affiliation else "",
        contrat.statut,
    )
    amounts = _collect_psc_cotisations(contrat)
    mut_amt, prev_amt = _classify_amounts(amounts, affiliation, statut)

    if mut_amt and (mut_amt.montant_salarial or mut_amt.montant_patronal):
        result.mutuelle_adhesion = True
        result.mutuelle_amounts = mut_amt
        result.mutuelle_lignes = [
            {
                "id": "mutuelle_dsn",
                "libelle": "Mutuelle (import DSN)",
                "montant_salarial": round(mut_amt.montant_salarial, 2),
                "montant_patronal": round(mut_amt.montant_patronal, 2),
                "part_patronale_soumise_a_csg": True,
            }
        ]

    if prev_amt and (prev_amt.montant_salarial or prev_amt.montant_patronal):
        result.prevoyance_adhesion = True
        result.prevoyance_amounts = prev_amt
        result.prevoyance_lignes = _build_prevoyance_lignes(prev_amt, statut)
        if statut != "Cadre" and not result.prevoyance_lignes:
            result.warnings.append("Prévoyance non-cadre détectée — taux entreprise à vérifier")

    if affiliation and not result.mutuelle_adhesion and not result.prevoyance_adhesion:
        org = affiliation.code_organisme
        if _is_mutuelle_organisme(org):
            result.mutuelle_adhesion = True
            result.warnings.append("Affiliation mutuelle sans montant DSN — formule à compléter")
        elif _is_prevoyance_organisme(org):
            result.prevoyance_adhesion = True
            result.warnings.append("Affiliation prévoyance sans montant DSN — taux à compléter")

    return result


def build_specificites_paie_psc(contrat: ContratBlock) -> Dict[str, Any]:
    """Construit specificites_paie.mutuelle / prevoyance depuis la DSN."""
    psc = extract_psc_from_contrat(contrat)
    mutuelle: Dict[str, Any] = {"adhesion": psc.mutuelle_adhesion}
    prevoyance: Dict[str, Any] = {"adhesion": psc.prevoyance_adhesion}

    if psc.pack_couverture:
        mutuelle["pack_couverture"] = psc.pack_couverture
    if psc.mutuelle_lignes:
        mutuelle["lignes_specifiques"] = psc.mutuelle_lignes
    if psc.code_option_dsn or psc.code_organisme_dsn:
        mutuelle["dsn"] = {
            k: v
            for k, v in {
                "code_option": psc.code_option_dsn,
                "code_population": psc.code_population_dsn,
                "reference_contrat": psc.reference_contrat_dsn,
                "code_organisme": psc.code_organisme_dsn,
                "code_delegataire": psc.code_delegataire_dsn,
            }.items()
            if v
        }
    if psc.prevoyance_lignes:
        prevoyance["lignes_specifiques"] = psc.prevoyance_lignes

    return {
        "mutuelle": mutuelle,
        "prevoyance": prevoyance,
        "_psc_meta": {
            "pack_couverture": psc.pack_couverture,
            "statut_categoriel": (
                "cadre"
                if map_statut_cadre(contrat.statut) == "Cadre"
                else "non_cadre"
            ),
            "warnings": psc.warnings,
        },
    }
