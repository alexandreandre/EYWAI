"""Mapping cotisations bulletin EYWAI → codes DSN P26 (G00.78 / G00.81).

Les codes suivent la table NEODeS (alignée Cegid) :
048 AGS, 049 FNAL, 045 AT/MP, 068 CSA, 074 AF, 040 chômage, etc.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from app.modules.dsn_import.domain.model import (
    BaseAssujettieBlock,
    CotisationIndividuelleBlock,
)
from app.modules.dsn_import.domain.rubriques import (
    BASE_ASSUJETTIE_BRUT_CODES,
    PSC_COTISATION_CODE,
    REDUCTION_GENERALE_COT_CODES,
)

# coti_id moteur → code cotisation individuelle DSN (G00.81.001)
COTI_ID_TO_DSN_CODE: Dict[str, str] = {
    "securite_sociale_maladie": "075",
    "maladie_alsace_moselle": "075",
    "at_mp": "045",
    "vieillesse_plafonnee": "076",
    "vieillesse_deplafonnee": "076",
    "retraite_secu_plafond": "076",
    "retraite_secu_deplafond": "076",
    "assurance_vieillesse_salarial": "076",
    "assurance_vieillesse_patronal": "076",
    "allocations_familiales": "074",
    "assurance_chomage": "040",
    "chomage": "040",
    "ags": "048",
    "fnal": "049",
    "CFP": "128",
    "cfp": "128",
    "taxe_apprentissage": "130",
    "taxe_apprentissage_solde": "130",
    "csa": "068",
    "dialogue_social": "100",
    "versement_mobilite": "081",
    "forfait_social": "093",
    # Retraite complémentaire → code régime unifié (agrégé côté builder)
    "retraite_comp_t1": "131",
    "retraite_comp_t2": "131",
    "ceg_t1": "131",
    "ceg_t2": "131",
    "cet": "131",
    "apec": "131",
    "retraite_sup": "131",
    "prevoyance_cadre": PSC_COTISATION_CODE,
    "prevoyance_non_cadre": PSC_COTISATION_CODE,
    "mutuelle": PSC_COTISATION_CODE,
    "complementaire_sante": PSC_COTISATION_CODE,
    "csg_deductible": "142",
    "csg_non_deductible": "079",
    "crds": "079",
    "reduction_generale": "018",
    "reduction_hs_salariale": "114",
    "deduction_hs_patronale": "021",
}

# Base assujettie DSN préférée par code cotisation (schéma Cegid / URSSAF)
CODE_TO_BASE: Dict[str, str] = {
    "018": "03",
    "021": "03",
    "040": "07",
    "045": "03",
    "048": "07",
    "049": "02",
    "059": "31",
    "068": "03",
    "071": "05",
    "072": "04",
    "074": "03",
    "075": "03",
    "076": "03",
    "079": "04",
    "100": "03",
    "102": "03",
    "106": "03",
    "114": "03",
    "128": "03",
    "130": "03",
    "131": "02",
    "142": "02",
    "907": "03",
}

# Mots-clés libellé → code DSN (repli)
_LIBELLE_TO_CODE: List[Tuple[str, str]] = [
    ("réduction générale", "018"),
    ("reduction generale", "018"),
    ("déduction forfaitaire heures", "021"),
    ("deduction forfaitaire heures", "021"),
    ("réduction de cotisations sur heures", "114"),
    ("reduction de cotisations sur heures", "114"),
    ("accident", "045"),
    ("at/mp", "045"),
    ("ags", "048"),
    ("fnal", "049"),
    ("aide au logement", "049"),
    ("csa", "068"),
    ("solidarité autonomie", "068"),
    ("solidarite autonomie", "068"),
    ("allocations familiales", "074"),
    ("maladie", "075"),
    ("vieillesse", "076"),
    ("chômage", "040"),
    ("chomage", "040"),
    ("dialogue", "100"),
    ("formation", "128"),
    ("apprentissage", "130"),
    ("agirc", "131"),
    ("arrco", "131"),
    ("retraite complémentaire", "131"),
    ("retraite complementaire", "131"),
    ("ceg", "131"),
    ("prévoyance", "059"),
    ("prevoyance", "059"),
    ("mutuelle", "059"),
    ("complémentaire santé", "059"),
    ("csg déductible", "142"),
    ("csg deductible", "142"),
    ("csg/crds", "079"),
    ("crds", "079"),
]


@dataclass(frozen=True)
class MappedCotisation:
    code: str
    assiette: float
    montant: float
    taux: float  # fraction (0.0025 = 0.25 %)
    is_patronal: bool
    ops_identifiant: str = ""
    affiliation_id: str = ""
    source_coti_id: str = ""
    base_code: str = "02"


class CotisationMappingError(ValueError):
    """Rubrique cotisation obligatoire non mappable."""


def resolve_dsn_cotisation_code(
    coti_id: Optional[str],
    libelle: str = "",
) -> Optional[str]:
    if coti_id and coti_id in COTI_ID_TO_DSN_CODE:
        return COTI_ID_TO_DSN_CODE[coti_id]
    lib = (libelle or "").lower()
    for keyword, code in _LIBELLE_TO_CODE:
        if keyword in lib:
            return code
    return None


def _base_for_code(code: str) -> str:
    return CODE_TO_BASE.get((code or "").zfill(3), "03")


def map_cotisation_line(
    line: Dict[str, Any],
    *,
    require_code: bool = False,
    default_ops: str = "",
) -> List[MappedCotisation]:
    """Retourne 0..n lignes DSN (salariale et/ou patronale)."""
    coti_id = str(line.get("coti_id") or "")
    libelle = str(line.get("libelle") or "")
    code = resolve_dsn_cotisation_code(coti_id, libelle)
    if not code:
        if require_code:
            raise CotisationMappingError(
                f"Impossible de mapper la cotisation '{libelle or coti_id}' vers un code DSN"
            )
        return []
    sal = float(line.get("montant_salarial") or 0)
    pat = float(line.get("montant_patronal") or 0)
    assiette = float(line.get("base") or line.get("assiette") or 0)
    taux_sal = float(line.get("taux_salarial") or 0)
    taux_pat = float(line.get("taux_patronal") or 0)
    ops = str(line.get("ops_identifiant") or default_ops or "")
    aff = str(line.get("identifiant_affiliation") or "")
    base_code = _base_for_code(code)

    out: List[MappedCotisation] = []
    # Codes « montant unique » (réductions / agrégats) : une seule ligne
    if code in {"018", "021", "114", "131"}:
        montant = sal + pat
        if montant == 0 and assiette == 0:
            return []
        is_pat = abs(pat) >= abs(sal)
        taux = taux_pat if is_pat else taux_sal
        out.append(
            MappedCotisation(
                code=code,
                assiette=assiette,
                montant=montant,
                taux=taux,
                is_patronal=is_pat,
                ops_identifiant=ops,
                affiliation_id=aff,
                source_coti_id=coti_id,
                base_code=base_code,
            )
        )
        return out

    if sal:
        out.append(
            MappedCotisation(
                code=code,
                assiette=assiette,
                montant=sal,
                taux=taux_sal,
                is_patronal=False,
                ops_identifiant=ops,
                affiliation_id=aff,
                source_coti_id=coti_id,
                base_code=base_code,
            )
        )
    if pat:
        out.append(
            MappedCotisation(
                code=code,
                assiette=assiette,
                montant=pat,
                taux=taux_pat,
                is_patronal=True,
                ops_identifiant=ops,
                affiliation_id=aff,
                source_coti_id=coti_id,
                base_code=base_code,
            )
        )
    if not out and assiette:
        # Ligne à zéro mais assiette déclarée (rare)
        out.append(
            MappedCotisation(
                code=code,
                assiette=assiette,
                montant=0.0,
                taux=0.0,
                is_patronal=True,
                ops_identifiant=ops,
                affiliation_id=aff,
                source_coti_id=coti_id,
                base_code=base_code,
            )
        )
    return out


def _taux_dsn(taux_fraction: float) -> str:
    """DSN attend un taux en % (0.250 pour 0,25 %)."""
    if abs(taux_fraction) < 1e-12:
        return "0.000"
    # Déjà en % si > 1 (ex. 7.0) ou fraction si < 1 (ex. 0.07)
    pct = taux_fraction * 100.0 if abs(taux_fraction) <= 1.0 else taux_fraction
    return f"{pct:.3f}"


def _aggregate_mapped(items: List[MappedCotisation]) -> List[MappedCotisation]:
    """Agrège les lignes 131 (retraite unifiée) en une seule cotisation."""
    others: List[MappedCotisation] = []
    agg_131: Optional[MappedCotisation] = None
    for item in items:
        if item.code != "131":
            others.append(item)
            continue
        if agg_131 is None:
            agg_131 = item
        else:
            agg_131 = MappedCotisation(
                code="131",
                assiette=max(agg_131.assiette, item.assiette),
                montant=round(agg_131.montant + item.montant, 2),
                taux=0.0,
                is_patronal=True,
                ops_identifiant=agg_131.ops_identifiant or item.ops_identifiant,
                affiliation_id=agg_131.affiliation_id or item.affiliation_id,
                source_coti_id="retraite_unifiee",
                base_code="02",
            )
    if agg_131 is not None:
        others.append(agg_131)
    return others


def build_bases_and_cotisations(
    cotisation_lines: List[Dict[str, Any]],
    *,
    brut: float,
    period_start: str,
    period_end: str,
    require_codes: bool = False,
    default_ops: str = "",
) -> Tuple[List[BaseAssujettieBlock], List[CotisationIndividuelleBlock], List[str]]:
    """Construit bases assujetties + cotisations individuelles G00.81."""
    warnings: List[str] = []
    mapped: List[MappedCotisation] = []
    for line in cotisation_lines:
        if not isinstance(line, dict):
            continue
        try:
            items = map_cotisation_line(
                line, require_code=require_codes, default_ops=default_ops
            )
        except CotisationMappingError as exc:
            if require_codes:
                raise
            warnings.append(str(exc))
            continue
        if items:
            mapped.extend(items)
        else:
            lib = line.get("libelle") or line.get("coti_id") or "?"
            warnings.append(f"Cotisation non mappée ignorée : {lib}")

    mapped = _aggregate_mapped(mapped)

    # Bases présentes selon les cotisations + brut
    base_amounts: Dict[str, float] = {}
    if brut > 0:
        base_amounts["02"] = round(brut, 2)
        base_amounts["03"] = round(brut, 2)
        base_amounts["07"] = round(brut, 2)
    for item in mapped:
        bc = item.base_code or "03"
        if bc == "31":
            base_amounts.setdefault("31", 0.0)
        elif bc in {"04", "05"}:
            # Assiette CSG / spécifique
            base_amounts[bc] = max(base_amounts.get(bc, 0.0), round(item.assiette or 0, 2))
        elif item.assiette:
            base_amounts[bc] = max(base_amounts.get(bc, 0.0), round(item.assiette, 2))

    bases: List[BaseAssujettieBlock] = []
    for code in sorted(base_amounts.keys(), key=lambda c: (c != "02", c)):
        montant = base_amounts[code]
        rub = {
            "S21.G00.78.001": code,
            "S21.G00.78.002": period_start,
            "S21.G00.78.003": period_end,
            "S21.G00.78.004": f"{montant:.2f}",
        }
        if code == "31":
            rub["S21.G00.78.005"] = "1"
        bases.append(
            BaseAssujettieBlock(
                code=code,
                date_debut=period_start,
                date_fin=period_end,
                montant=montant,
                rubriques=rub,
            )
        )

    # Émettre les cotisations groupées par base (ordre Cegid)
    by_base: Dict[str, List[MappedCotisation]] = {}
    for item in mapped:
        by_base.setdefault(item.base_code or "03", []).append(item)

    cotisations: List[CotisationIndividuelleBlock] = []
    for base in bases:
        for item in by_base.get(base.code, []):
            rub = {"S21.G00.81.001": item.code}
            if item.ops_identifiant:
                rub["S21.G00.81.002"] = item.ops_identifiant
            if item.assiette:
                rub["S21.G00.81.003"] = f"{item.assiette:.2f}"
            rub["S21.G00.81.004"] = f"{item.montant:.2f}"
            if item.taux:
                rub["S21.G00.81.007"] = _taux_dsn(item.taux)
            elif item.code in {"018", "131", "059"}:
                rub["S21.G00.81.007"] = "0.000"
            if item.affiliation_id:
                rub["S21.G00.81.005"] = item.affiliation_id
            cotisations.append(
                CotisationIndividuelleBlock(
                    code=item.code,
                    montant_assiette=item.assiette,
                    montant_salarial=0.0 if item.is_patronal else item.montant,
                    montant_patronal=item.montant if item.is_patronal else 0.0,
                    identifiant_affiliation=item.ops_identifiant or item.affiliation_id,
                    rubriques={**rub, "_base": base.code},
                )
            )

    return bases, cotisations, warnings


def is_reduction_generale_code(code: str) -> bool:
    return (code or "").zfill(3) in REDUCTION_GENERALE_COT_CODES


def is_brut_base_code(code: str) -> bool:
    return (code or "").zfill(2) in BASE_ASSUJETTIE_BRUT_CODES
