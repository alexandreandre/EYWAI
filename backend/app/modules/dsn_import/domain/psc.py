"""
Extraction mutuelle / prévoyance depuis une DSN (blocs affiliation + cotisations PSC).

Références norme DSN :
- S21.G00.15 : contrats collectifs mutuelle / prévoyance (établissement)
- S21.G00.70 : affiliation salarié (code option = pack, code population = catégorie)
- S21.G00.78 / S21.G00.81 : cotisations individuelles (code 059 = PSC)

Le contrat d'une affiliation se lit par ses liens (norme, 08/11) : 70.013 renvoie au 15.005 de
l'adhésion (organisme), 78.005 d'une base 31 renvoie au 70.012 de l'affiliation, et cette base porte
ses composants (79) et sa cotisation 059 (81). Une base sur le salaire (79.001 = 10 à 17, 19, 24 :
salaire brut, tranches, base spécifique) est une prévoyance ; une base forfaitaire seule (18, 20,
21) est la complémentaire santé. Les codes population (70.005) sont propres à chaque contrat
d'organisme : Cartol déclare « 841 » sur sa prévoyance et « ENSP » sur sa mutuelle, l'inverse des
listes fixes ; ils ne servent plus qu'en dernier repli, faute de lien.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.modules.dsn_import.application.cumuls import extract_monthly_totals
from app.modules.dsn_import.domain.model import (
    AffiliationBlock,
    ContratBlock,
    IndividuBlock,
    OrganismePscBlock,
)
from app.modules.dsn_import.domain.normalize import map_statut_cadre

PSC_COTISATION_CODES = {"059", "031", "032", "033"}
MUTUELLE_ORGANISME_RE = re.compile(r"^(?:\d{9}|E\d)", re.IGNORECASE)
PREVOYANCE_ORGANISME_RE = re.compile(r"^P(?:I)?\d", re.IGNORECASE)

#: Dernier repli, faute de lien. « 841 » et « ENSP » retirés le 08/11 : ajoutés le 22/06 depuis la DSN
#: de Cartol lue à l'envers (841 y est la population de la prévoyance Groupama, ENSP celle de la mutuelle).
MUTUELLE_POPULATION_CODES = {"01", "MUT", "MUTUELLE"}
PREVOYANCE_POPULATION_CODES = {"056", "02", "PREV", "PREVOYANCE"}


@dataclass
class PscCotisationAmounts:
    montant_salarial: float = 0.0
    montant_patronal: float = 0.0
    base: float = 0.0
    code: str = "059"
    identifiant_affiliation: str = ""


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


#: 79.001 d'une base 31 : sur le salaire (prévoyance) ou forfaitaire (santé).
COMPOSANTS_SUR_SALAIRE = {"10", "11", "12", "13", "14", "15", "16", "17", "19", "24"}
COMPOSANTS_FORFAITAIRES = {"18", "20", "21"}
CODE_MUTUELLE_RE = re.compile(r"^\d{9}$")
CODE_INSTITUTION_PREVOYANCE_RE = re.compile(r"^P\d{4}$", re.IGNORECASE)


def _kind_par_composants(aff: AffiliationBlock, contrat: Optional[ContratBlock]) -> Optional[str]:
    ident = (aff.identifiant_affiliation or "").strip()
    if not ident or contrat is None:
        return None
    codes = {
        (cb.code or "").strip()
        for ver in contrat.versements
        for cb in ver.composants_base
        if (cb.identifiant_affiliation or "").strip() == ident
    }
    if codes & COMPOSANTS_SUR_SALAIRE:
        return "prevoyance"
    if codes & COMPOSANTS_FORFAITAIRES:
        return "mutuelle"
    return None


def _adhesion_de(aff: AffiliationBlock, organismes_psc: Optional[List[OrganismePscBlock]]) -> Optional[OrganismePscBlock]:
    ident = (aff.identifiant_adhesion or "").strip()
    if not ident or not organismes_psc:
        return None
    return next((o for o in organismes_psc if (o.rang or "").strip() == ident), None)


def _kind_par_organisme(code: str) -> Optional[str]:
    """Code organisme du 15.002 : mutuelle sur 9 chiffres, institution de prévoyance « Pnnnn » ;
    société d'assurances et organisme non fédéré : les deux, rien n'en est déduit."""
    code = (code or "").strip()
    if CODE_MUTUELLE_RE.match(code):
        return "mutuelle"
    if CODE_INSTITUTION_PREVOYANCE_RE.match(code):
        return "prevoyance"
    return None


def _affiliation_kind(
    aff: AffiliationBlock,
    contrat: Optional[ContratBlock] = None,
    organismes_psc: Optional[List[OrganismePscBlock]] = None,
) -> str:
    kind = _kind_par_composants(aff, contrat)
    if kind:
        return kind
    adhesion = _adhesion_de(aff, organismes_psc)
    if adhesion is not None:
        kind = _kind_par_organisme(adhesion.code_organisme)
        if kind:
            return kind
    pop = (aff.code_population or "").strip().upper()
    if pop in PREVOYANCE_POPULATION_CODES:
        return "prevoyance"
    if pop in MUTUELLE_POPULATION_CODES:
        return "mutuelle"
    org = (aff.code_organisme or aff.reference_contrat or "").strip()
    if _is_prevoyance_organisme(org):
        return "prevoyance"
    if _is_mutuelle_organisme(org):
        return "mutuelle"
    return "unknown"


def _organisme_kind(org: OrganismePscBlock) -> str:
    # 15.004 (`code_nature`) dit si du personnel est couvert (01 oui, 02 non), pas la nature du
    # contrat : il classait « mutuelle » toute adhésion couvrant quelqu'un.
    kind = _kind_par_organisme(org.code_organisme)
    if kind:
        return kind
    ref = (org.reference_contrat or "").strip()
    if _is_prevoyance_organisme(ref):
        return "prevoyance"
    if _is_mutuelle_organisme(ref):
        return "mutuelle"
    return "unknown"


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
                            identifiant_affiliation=(ci.identifiant_affiliation or "").strip(),
                        )
                    )
    return amounts


def _nonzero_amounts(amounts: List[PscCotisationAmounts]) -> List[PscCotisationAmounts]:
    return [a for a in amounts if a.montant_salarial or a.montant_patronal]


def _brut_from_contrat(contrat: ContratBlock) -> float:
    stub = IndividuBlock(contrats=[contrat])
    return float(extract_monthly_totals(stub).get("brut", 0.0) or 0.0)


def _classify_amounts_legacy(
    amounts: List[PscCotisationAmounts],
    affiliation: Optional[AffiliationBlock],
    statut: str,
) -> tuple[Optional[PscCotisationAmounts], Optional[PscCotisationAmounts]]:
    """Repli heuristique lorsque les affiliations ne suffisent pas."""
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
        is_percent_like = (
            amt.base > 100
            and amt.montant_patronal > 0
            and amt.montant_patronal / amt.base < 0.15
        )
        if is_percent_like or (statut == "Cadre" and amt.base > 100 and not mutuelle):
            prevoyance = prevoyance or amt
        else:
            mutuelle = mutuelle or amt
    if mutuelle is None and prevoyance is None and amounts:
        mutuelle = amounts[0]
    return mutuelle, prevoyance


def _somme(amounts: List[PscCotisationAmounts]) -> Optional[PscCotisationAmounts]:
    if not amounts:
        return None
    return PscCotisationAmounts(
        montant_salarial=round(sum(a.montant_salarial for a in amounts), 2),
        montant_patronal=round(sum(a.montant_patronal for a in amounts), 2),
        base=max(a.base for a in amounts),
        code=amounts[0].code,
        identifiant_affiliation=amounts[0].identifiant_affiliation,
    )


def _split_amounts_by_affiliations(
    amounts: List[PscCotisationAmounts],
    mut_affs: List[AffiliationBlock],
    prev_affs: List[AffiliationBlock],
    statut: str,
    affiliation: Optional[AffiliationBlock],
) -> tuple[Optional[PscCotisationAmounts], Optional[PscCotisationAmounts]]:
    nonzero = _nonzero_amounts(amounts)
    # Chaque cotisation liée à son affiliation (78.005) va au contrat de cette affiliation.
    ids_mut = {(a.identifiant_affiliation or "").strip() for a in mut_affs} - {""}
    ids_prev = {(a.identifiant_affiliation or "").strip() for a in prev_affs} - {""}
    lies = [a for a in nonzero if a.identifiant_affiliation and a.identifiant_affiliation in ids_mut | ids_prev]
    if lies and len(lies) == len(nonzero):
        return (_somme([a for a in lies if a.identifiant_affiliation in ids_mut]),
                _somme([a for a in lies if a.identifiant_affiliation in ids_prev]))
    if mut_affs and prev_affs:
        if len(nonzero) >= 2:
            return nonzero[0], nonzero[1]
        if len(nonzero) == 1:
            return nonzero[0], None
        return None, None
    if mut_affs and not prev_affs:
        return (nonzero[0] if nonzero else None), None
    if prev_affs and not mut_affs:
        return None, (nonzero[0] if nonzero else None)
    return _classify_amounts_legacy(amounts, affiliation, statut)


def _enrich_organisme_from_etablissement(
    result: EmployeePscData,
    organismes_psc: Optional[List[OrganismePscBlock]],
    mut_affs: List[AffiliationBlock],
    prev_affs: List[AffiliationBlock],
) -> None:
    if not organismes_psc:
        return
    mut_orgs = [o for o in organismes_psc if _organisme_kind(o) == "mutuelle"]
    prev_orgs = [o for o in organismes_psc if _organisme_kind(o) == "prevoyance"]
    if mut_affs and mut_orgs and not result.code_organisme_dsn:
        org = mut_orgs[0]
        result.reference_contrat_dsn = result.reference_contrat_dsn or org.reference_contrat or None
        result.code_organisme_dsn = org.code_organisme or org.reference_contrat or None
    if prev_affs and prev_orgs and result.prevoyance_adhesion:
        org = prev_orgs[0]
        if not result.reference_contrat_dsn:
            result.reference_contrat_dsn = org.reference_contrat or None


def _build_prevoyance_lignes(
    prev_amounts: PscCotisationAmounts,
    statut: str,
    brut: float,
) -> List[Dict[str, Any]]:
    if statut != "Cadre":
        return []

    base = prev_amounts.base if prev_amounts.base > 100 else brut
    if base <= 0:
        return []

    taux_sal = round(prev_amounts.montant_salarial / base, 6) if prev_amounts.montant_salarial else 0.0
    taux_pat = round(prev_amounts.montant_patronal / base, 6) if prev_amounts.montant_patronal else 0.0

    if taux_pat <= 0 and taux_sal <= 0:
        total = prev_amounts.montant_salarial + prev_amounts.montant_patronal
        if total > 0:
            taux_pat = round(total / base, 6)

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


def extract_psc_from_contrat(
    contrat: ContratBlock,
    organismes_psc: Optional[List[OrganismePscBlock]] = None,
) -> EmployeePscData:
    """Extrait mutuelle / prévoyance depuis affiliations et cotisations PSC du contrat."""
    result = EmployeePscData()
    kinds = [(_affiliation_kind(a, contrat, organismes_psc), a) for a in contrat.affiliations]
    mut_affs = [a for k, a in kinds if k == "mutuelle"]
    prev_affs = [a for k, a in kinds if k == "prevoyance"]
    affiliation = mut_affs[0] if mut_affs else (prev_affs[0] if prev_affs else (contrat.affiliations[0] if contrat.affiliations else None))

    if affiliation:
        adhesion = _adhesion_de(affiliation, organismes_psc)
        result.code_option_dsn = affiliation.code_option or None
        result.code_population_dsn = affiliation.code_population or None
        result.reference_contrat_dsn = affiliation.reference_contrat or (
            adhesion.reference_contrat if adhesion else None) or None
        result.code_organisme_dsn = affiliation.code_organisme or (
            adhesion.code_organisme if adhesion else None) or None
        result.code_delegataire_dsn = affiliation.code_delegataire or None
        result.pack_couverture = infer_pack_from_code_option(
            affiliation.code_option,
            affiliation.nb_enfants,
            affiliation.nb_adultes,
        )

    statut = map_statut_cadre(contrat.statut)
    amounts = _collect_psc_cotisations(contrat)
    mut_amt, prev_amt = _split_amounts_by_affiliations(
        amounts, mut_affs, prev_affs, statut, affiliation
    )
    brut = _brut_from_contrat(contrat)

    if mut_affs or mut_amt:
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
        elif mut_affs:
            result.mutuelle_adhesion = True
            result.warnings.append("Affiliation mutuelle sans montant DSN — formule à compléter")

    if prev_affs or prev_amt:
        if prev_amt and (prev_amt.montant_salarial or prev_amt.montant_patronal):
            result.prevoyance_adhesion = True
            result.prevoyance_amounts = prev_amt
            result.prevoyance_lignes = _build_prevoyance_lignes(prev_amt, statut, brut)
            if statut == "Cadre" and not result.prevoyance_lignes:
                result.warnings.append(
                    "Prévoyance cadre détectée — taux non dérivables (brut DSN absent), compléter la fiche"
                )
            elif statut != "Cadre":
                result.warnings.append("Prévoyance non-cadre détectée — taux entreprise à vérifier")
        elif prev_affs:
            result.prevoyance_adhesion = True
            result.warnings.append("Affiliation prévoyance sans montant DSN — taux à compléter")

    if affiliation and not result.mutuelle_adhesion and not result.prevoyance_adhesion:
        org = affiliation.code_organisme or affiliation.reference_contrat
        if _is_mutuelle_organisme(org):
            result.mutuelle_adhesion = True
            result.warnings.append("Affiliation mutuelle sans montant DSN — formule à compléter")
        elif _is_prevoyance_organisme(org):
            result.prevoyance_adhesion = True
            result.warnings.append("Affiliation prévoyance sans montant DSN — taux à compléter")

    _enrich_organisme_from_etablissement(result, organismes_psc, mut_affs, prev_affs)

    if result.prevoyance_lignes and brut > 0 and prev_amt:
        total = (prev_amt.montant_salarial or 0) + (prev_amt.montant_patronal or 0)
        if total > 0 and prev_amt.base <= 0:
            result.warnings.append(
                "Taux prévoyance dérivés du forfait DSN — vérifier répartition salarial / patronal"
            )

    return result


def build_specificites_paie_psc(
    contrat: ContratBlock,
    organismes_psc: Optional[List[OrganismePscBlock]] = None,
) -> Dict[str, Any]:
    """Construit specificites_paie.mutuelle / prevoyance depuis la DSN."""
    psc = extract_psc_from_contrat(contrat, organismes_psc=organismes_psc)
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
    if psc.prevoyance_adhesion and psc.reference_contrat_dsn:
        prevoyance["dsn"] = {
            "reference_contrat": psc.reference_contrat_dsn,
            "code_organisme": psc.code_organisme_dsn,
        }

    return {
        "mutuelle": mutuelle,
        "prevoyance": prevoyance,
        "_psc_meta": {
            "pack_couverture": psc.pack_couverture,
            "statut_categoriel": (
                "cadre" if map_statut_cadre(contrat.statut) == "Cadre" else "non_cadre"
            ),
            "warnings": psc.warnings,
        },
    }
