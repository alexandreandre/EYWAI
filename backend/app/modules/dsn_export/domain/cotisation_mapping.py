"""Traduction des cotisations du bulletin EYWAI en blocs DSN 78 / 81.

Un bulletin de paie et une DSN ne découpent pas les cotisations de la même
façon. Le bulletin porte une ligne par rubrique, avec sa part salariale et sa
part patronale côte à côte. La DSN porte une ligne par **code de cotisation**,
rattachée à une **base assujettie**, dont le montant est la somme des deux
parts et le taux leur cumul.

Trois écarts structurels en découlent, tous vérifiés sur les DSN réellement
déposées par le cabinet (`data/_dsn_conformance/*/*/reference.dsn`) :

1. **Une rubrique de bulletin peut donner deux codes DSN.** La maladie à 13 %
   se déclare en `075` à 7 % plus `907` à 6 % ; les allocations familiales à
   5,25 % en `074` à 3,45 % plus `102` à 1,80 % ; la réduction générale se
   ventile entre `018` (sécurité sociale et chômage) et `106` (retraite
   complémentaire).
2. **Deux rubriques peuvent donner un seul code.** La CSG déductible et la
   part CSG de la ligne « CSG/CRDS non déductible » se regroupent en `072` à
   9,20 % ; seule la CRDS reste à part, en `079` à 0,50 %.
3. **Le rattachement à la base compte autant que le code.** La vieillesse
   plafonnée va sur la base `02`, la déplafonnée sur la `03`, la CSG sur la
   `04`, le forfait social sur la `05`, le chômage sur la `07`, la prévoyance
   sur la `31`.

La nomenclature des codes est publique : voir `nomenclature_cotisation.py`.
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

# --------------------------------------------------------------------------
# Bases assujetties
# --------------------------------------------------------------------------

BASE_PLAFONNEE = "02"
BASE_BRUT_DEPLAFONNE = "03"
BASE_CSG = "04"
BASE_FORFAIT_SOCIAL = "05"
BASE_CHOMAGE = "07"
BASE_PREVOYANCE = "31"
BASE_VERSEMENT_MOBILITE = "57"

# Ordre d'émission des bases, celui du cabinet.
ORDRE_BASES = [
    BASE_PLAFONNEE,
    BASE_BRUT_DEPLAFONNE,
    BASE_CSG,
    BASE_FORFAIT_SOCIAL,
    BASE_CHOMAGE,
    BASE_PREVOYANCE,
    BASE_VERSEMENT_MOBILITE,
]

# --------------------------------------------------------------------------
# Taux de référence servant à découper une rubrique en deux codes
# --------------------------------------------------------------------------

# Maladie : 7 % jusqu'à 2,5 SMIC, 13 % au-delà. La DSN déclare toujours 7 % en
# `075` et loge le surplus en `907`.
TAUX_MALADIE_BASE = 0.07
# Allocations familiales : 3,45 % jusqu'à 3,5 SMIC, 5,25 % au-delà.
TAUX_AF_BASE = 0.0345
# Part de la réduction générale imputée sur la retraite complémentaire, en
# points de coefficient (décret n°2025-887). La fraction vaut 6,01 / T, T étant
# le coefficient maximal applicable à la société.
POINTS_RETRAITE_COMPLEMENTAIRE = 0.0601
# Coefficients maximaux 2026 (T = Tmin + Tdelta). Le FNAL distingue les deux.
TMAX_FNAL_MOINS_50 = 0.3980
TMAX_FNAL_50_ET_PLUS = 0.4020
# Le FNAL à 0,10 % est plafonné (base 02) et signale un effectif < 50.
TAUX_FNAL_MOINS_50 = 0.001

# CSG et CRDS : le bulletin sépare déductible / non déductible, la DSN sépare
# CSG (9,20 %) et CRDS (0,50 %).
TAUX_CSG_TOTAL = 0.092
TAUX_CRDS = 0.005
# L'épargne salariale supporte CSG et CRDS d'un bloc, sans abattement.
TAUX_CSG_EPARGNE = 0.097

CODE_CSG = "072"
CODE_CRDS = "079"
CODE_CSG_EPARGNE_SALARIALE = "073"
CODE_MALADIE = "075"
CODE_MALADIE_COMPLEMENT = "907"
CODE_AF = "074"
CODE_AF_COMPLEMENT = "102"
CODE_REDUCTION_GENERALE = "018"
CODE_REDUCTION_RETRAITE_COMP = "106"
CODE_AGIRC_ARRCO = "131"
CODE_AGIRC_ARRCO_PAT_T1 = "142"
CODE_AGIRC_ARRCO_PAT_T2 = "146"
CODE_APEC = "132"
CODE_FORFAIT_SOCIAL = "071"


@dataclass(frozen=True)
class Regle:
    """Où va une rubrique de bulletin dans la DSN."""

    code: str
    base: str
    # Une rubrique dont les deux parts se déclarent séparément (part salariale
    # sur un code, part patronale sur un autre).
    code_patronal: Optional[str] = None


# coti_id du moteur → règle DSN. Le rattachement à la base fait partie de la
# règle : un même code sur deux bases n'est pas la même déclaration.
REGLES: Dict[str, Regle] = {
    # Base 02 — plafonnée
    "retraite_secu_plafond": Regle("076", BASE_PLAFONNEE),
    "vieillesse_plafonnee": Regle("076", BASE_PLAFONNEE),
    "retraite_comp_t1": Regle(CODE_AGIRC_ARRCO, BASE_PLAFONNEE, CODE_AGIRC_ARRCO_PAT_T1),
    "ceg_t1": Regle(CODE_AGIRC_ARRCO, BASE_PLAFONNEE, CODE_AGIRC_ARRCO_PAT_T1),
    # La tranche 2 dépasse le plafond : elle se rattache au brut déplafonné,
    # pas à la base plafonnée. L'Apec suit la tranche 2.
    "retraite_comp_t2": Regle(CODE_AGIRC_ARRCO, BASE_BRUT_DEPLAFONNE, CODE_AGIRC_ARRCO_PAT_T2),
    "ceg_t2": Regle(CODE_AGIRC_ARRCO, BASE_BRUT_DEPLAFONNE, CODE_AGIRC_ARRCO_PAT_T2),
    "cet": Regle(CODE_AGIRC_ARRCO, BASE_BRUT_DEPLAFONNE, CODE_AGIRC_ARRCO_PAT_T2),
    "apec": Regle(CODE_APEC, BASE_BRUT_DEPLAFONNE),
    # Base 03 — brut déplafonné
    "retraite_secu_deplafond": Regle("076", BASE_BRUT_DEPLAFONNE),
    "vieillesse_deplafonnee": Regle("076", BASE_BRUT_DEPLAFONNE),
    "assurance_vieillesse_salarial": Regle("076", BASE_BRUT_DEPLAFONNE),
    "assurance_vieillesse_patronal": Regle("076", BASE_BRUT_DEPLAFONNE),
    "at_mp": Regle("045", BASE_BRUT_DEPLAFONNE),
    "csa": Regle("068", BASE_BRUT_DEPLAFONNE),
    "dialogue_social": Regle("100", BASE_BRUT_DEPLAFONNE),
    "CFP": Regle("128", BASE_BRUT_DEPLAFONNE),
    "cfp": Regle("128", BASE_BRUT_DEPLAFONNE),
    "taxe_apprentissage": Regle("130", BASE_BRUT_DEPLAFONNE),
    # Le versement mobilité a sa propre base assujettie, la 57.
    "versement_mobilite": Regle("081", BASE_VERSEMENT_MOBILITE),
    "reduction_hs_salariale": Regle("114", BASE_BRUT_DEPLAFONNE),
    # Base 07 — chômage
    "assurance_chomage": Regle("040", BASE_CHOMAGE),
    "chomage": Regle("040", BASE_CHOMAGE),
    "ags": Regle("048", BASE_CHOMAGE),
    # Base 05 — forfait social
    "forfait_social": Regle(CODE_FORFAIT_SOCIAL, BASE_FORFAIT_SOCIAL),
    # Base 31 — prévoyance, santé, retraite supplémentaire
    "mutuelle": Regle(PSC_COTISATION_CODE, BASE_PREVOYANCE),
    "complementaire_sante": Regle(PSC_COTISATION_CODE, BASE_PREVOYANCE),
    "prevoyance_cadre": Regle(PSC_COTISATION_CODE, BASE_PREVOYANCE),
    "prevoyance_non_cadre": Regle(PSC_COTISATION_CODE, BASE_PREVOYANCE),
    "retraite_sup": Regle(PSC_COTISATION_CODE, BASE_PREVOYANCE),
}

# Rubriques traitées à part, parce qu'une règle « une ligne → un code » ne les
# décrit pas : elles se découpent, se regroupent, ou dépendent d'un taux.
COTI_ID_A_TRAITEMENT_PROPRE = {
    "securite_sociale_maladie",
    "maladie_alsace_moselle",
    "allocations_familiales",
    "fnal",
    "reduction_generale",
    "csg_deductible",
    "csg_non_deductible",
    "crds",
}

# Rubriques qui ne se déclarent pas au niveau du salarié. Le solde de la taxe
# d'apprentissage se verse annuellement et n'apparaît que dans les cotisations
# agrégées de l'établissement : le cabinet ne déclare que la part principale
# (0,59 %) en `130`. Les lister explicitement évite que le repli par mots-clés
# les rattrape et les fasse gonfler un code voisin.
COTI_ID_NON_INDIVIDUELS = {
    "taxe_apprentissage_solde",
}


class CotisationMappingError(ValueError):
    """Rubrique de cotisation obligatoire non traduisible en code DSN."""


@dataclass
class LigneDsn:
    """Une ligne de cotisation individuelle, telle qu'elle sera écrite."""

    code: str
    base: str
    assiette: float = 0.0
    montant: float = 0.0
    taux: float = 0.0  # en fraction (0.07 = 7 %)
    ops_identifiant: str = ""
    affiliation_id: str = ""
    # Une ligne par affiliation ne se cumule pas avec une autre.
    distincte: bool = False


# --------------------------------------------------------------------------
# Lecture d'une ligne de bulletin
# --------------------------------------------------------------------------


def _flottant(valeur: Any) -> float:
    try:
        return float(valeur or 0)
    except (TypeError, ValueError):
        return 0.0


def _parts(ligne: Dict[str, Any]) -> Tuple[float, float, float, float, float]:
    """(assiette, montant salarial, montant patronal, taux sal, taux pat)."""
    return (
        _flottant(ligne.get("base") if ligne.get("base") is not None else ligne.get("assiette")),
        _flottant(ligne.get("montant_salarial")),
        _flottant(ligne.get("montant_patronal")),
        _flottant(ligne.get("taux_salarial")),
        _flottant(ligne.get("taux_patronal")),
    )


def _est_epargne_salariale(libelle: str) -> bool:
    minuscule = (libelle or "").lower()
    return any(
        mot in minuscule
        for mot in ("participation", "intéressement", "interessement", "épargne", "epargne")
    )


# --------------------------------------------------------------------------
# Traductions particulières
# --------------------------------------------------------------------------


def _scinder_au_taux(
    assiette: float,
    montant: float,
    taux: float,
    *,
    taux_socle: float,
    code_socle: str,
    code_complement: str,
) -> List[LigneDsn]:
    """Sépare une cotisation à taux majoré en un socle et son complément.

    Les deux montants se recalculent depuis l'assiette, chacun arrondi pour son
    compte : c'est la méthode du cabinet. Déduire le complément par soustraction
    donnerait le même total mais décalerait chaque ligne d'un centime dès que le
    montant du bulletin n'est pas exactement l'assiette multipliée par le taux.
    """
    if taux <= taux_socle + 1e-9:
        return [LigneDsn(code_socle, BASE_BRUT_DEPLAFONNE, assiette, montant, taux)]
    taux_complement = round(taux - taux_socle, 6)
    return [
        LigneDsn(
            code_socle,
            BASE_BRUT_DEPLAFONNE,
            assiette,
            round(assiette * taux_socle, 2),
            taux_socle,
        ),
        LigneDsn(
            code_complement,
            BASE_BRUT_DEPLAFONNE,
            assiette,
            round(assiette * taux_complement, 2),
            taux_complement,
        ),
    ]


def _maladie(assiette: float, montant: float, taux: float) -> List[LigneDsn]:
    """7 % en `075`, le surplus éventuel en `907`."""
    return _scinder_au_taux(
        assiette,
        montant,
        taux,
        taux_socle=TAUX_MALADIE_BASE,
        code_socle=CODE_MALADIE,
        code_complement=CODE_MALADIE_COMPLEMENT,
    )


def _allocations_familiales(assiette: float, montant: float, taux: float) -> List[LigneDsn]:
    """3,45 % en `074`, le surplus éventuel en `102`."""
    return _scinder_au_taux(
        assiette,
        montant,
        taux,
        taux_socle=TAUX_AF_BASE,
        code_socle=CODE_AF,
        code_complement=CODE_AF_COMPLEMENT,
    )


def _deduction_heures_supplementaires(
    ligne: Dict[str, Any], assiette_heures_sup: float
) -> List[LigneDsn]:
    """Déduction forfaitaire patronale sur heures supplémentaires (`021`).

    Le bulletin raisonne en heures : l'assiette y est un nombre d'heures et le
    montant vaut ce nombre multiplié par la déduction unitaire (1,50 € en
    dessous de 20 salariés, 0,50 € de 20 à 249). La DSN, elle, attend la
    **rémunération** des heures supplémentaires en assiette, et loge la
    déduction unitaire dans le taux.
    """
    heures, sal, pat, _, _ = _parts(ligne)
    montant = round(sal + pat, 2)
    unitaire = round(abs(montant) / heures, 2) if heures else 0.0
    return [
        LigneDsn(
            "021",
            BASE_BRUT_DEPLAFONNE,
            round(assiette_heures_sup, 2),
            montant,
            # Le taux DSN s'écrit en pourcentage : la déduction unitaire en
            # euros s'y inscrit telle quelle (0,50 € → « 0.500 »).
            unitaire / 100.0,
        )
    ]


def _assiette_heures_supplementaires(lignes: List[Dict[str, Any]]) -> float:
    """Rémunération des heures supplémentaires, lue sur la réduction salariale."""
    for ligne in lignes:
        if str(ligne.get("coti_id") or "") == "reduction_hs_salariale":
            assiette, _, _, _, _ = _parts(ligne)
            return assiette
    return 0.0


def _fnal(assiette: float, montant: float, taux: float) -> List[LigneDsn]:
    """FNAL plafonné (0,10 %, < 50 salariés) sur la base 02, déplafonné sur la 03."""
    base = BASE_PLAFONNEE if taux <= TAUX_FNAL_MOINS_50 + 1e-9 else BASE_BRUT_DEPLAFONNE
    return [LigneDsn("049", base, assiette, montant, taux)]


def _reduction_generale(assiette: float, montant: float, tmax: float) -> List[LigneDsn]:
    """Ventile la réduction entre sécurité sociale (`018`) et retraite (`106`).

    La fraction imputée sur la retraite complémentaire vaut 6,01 / T. Vérifiée
    sur 216 salariés des DSN du cabinet : 0,1494 pour T = 40,20 % et 0,1510
    pour T = 39,80 %.
    """
    if tmax <= 0:
        return [LigneDsn(CODE_REDUCTION_GENERALE, BASE_BRUT_DEPLAFONNE, assiette, montant, 0.0)]
    part_retraite = round(montant * POINTS_RETRAITE_COMPLEMENTAIRE / tmax, 2)
    return [
        LigneDsn(
            CODE_REDUCTION_GENERALE,
            BASE_BRUT_DEPLAFONNE,
            assiette,
            round(montant - part_retraite, 2),
            0.0,
        ),
        LigneDsn(
            CODE_REDUCTION_RETRAITE_COMP,
            BASE_BRUT_DEPLAFONNE,
            assiette,
            part_retraite,
            0.0,
        ),
    ]


def _tmax_applicable(lignes: List[Dict[str, Any]]) -> float:
    """Coefficient maximal T, déduit du taux de FNAL du même bulletin."""
    for ligne in lignes:
        if str(ligne.get("coti_id") or "") == "fnal":
            _, _, _, _, taux_pat = _parts(ligne)
            if taux_pat <= TAUX_FNAL_MOINS_50 + 1e-9:
                return TMAX_FNAL_MOINS_50
            return TMAX_FNAL_50_ET_PLUS
    return TMAX_FNAL_MOINS_50


def _csg_et_crds(lignes: List[Dict[str, Any]]) -> List[LigneDsn]:
    """Regroupe toutes les lignes de CSG/CRDS du bulletin en `072` + `079`.

    Le bulletin sépare déductible et non déductible, et multiplie les lignes
    (salaire, heures supplémentaires, épargne salariale). La DSN n'en garde
    qu'une assiette, celle de la base 04, et deux codes : la CSG à 9,20 % et la
    CRDS à 0,50 %.

    L'épargne salariale y est incluse. Le code dédié `073` existe et le cabinet
    s'en sert, mais rarement : sur les 157 salariés mesurés, 10 le portent et
    147 voient leur participation fondue dans l'assiette de la base 04. Séparer
    systématiquement dégrade la conformité (136 lignes en trop contre 10 en
    moins) ; on suit donc l'usage majoritaire, et ces 10 salariés restent un
    écart connu.
    """
    assiette_salaires = 0.0
    vues: set = set()

    for ligne in lignes:
        coti_id = str(ligne.get("coti_id") or "")
        libelle = str(ligne.get("libelle") or "")
        est_csg = coti_id in {"csg_deductible", "csg_non_deductible", "crds"} or (
            "csg" in libelle.lower() or "crds" in libelle.lower()
        )
        if not est_csg:
            continue
        assiette, _, _, _, _ = _parts(ligne)
        if assiette <= 0:
            continue
        # Une même assiette porte la CSG déductible et la non déductible : ne la
        # compter qu'une fois.
        # Une même assiette porte la CSG déductible et la non déductible : ne la
        # compter qu'une fois.
        cle = round(assiette, 2)
        if cle in vues:
            continue
        vues.add(cle)
        assiette_salaires += assiette

    resultat: List[LigneDsn] = []
    if assiette_salaires > 0:
        resultat.append(
            LigneDsn(
                CODE_CSG,
                BASE_CSG,
                round(assiette_salaires, 2),
                round(assiette_salaires * TAUX_CSG_TOTAL, 2),
                TAUX_CSG_TOTAL,
            )
        )
        resultat.append(
            LigneDsn(
                CODE_CRDS,
                BASE_CSG,
                round(assiette_salaires, 2),
                round(assiette_salaires * TAUX_CRDS, 2),
                TAUX_CRDS,
            )
        )
    return resultat


# --------------------------------------------------------------------------
# Traduction d'une ligne quelconque
# --------------------------------------------------------------------------


def resolve_dsn_cotisation_code(coti_id: Optional[str], libelle: str = "") -> Optional[str]:
    """Code DSN d'une rubrique, sans tenir compte de la base ni des découpages.

    Conservé pour les appelants qui n'ont besoin que du code. Les rubriques à
    traitement propre renvoient leur code principal.
    """
    identifiant = str(coti_id or "")
    regle = REGLES.get(identifiant)
    if regle is not None:
        return regle.code
    principaux = {
        "securite_sociale_maladie": CODE_MALADIE,
        "maladie_alsace_moselle": CODE_MALADIE,
        "allocations_familiales": CODE_AF,
        "fnal": "049",
        "reduction_generale": CODE_REDUCTION_GENERALE,
        "csg_deductible": CODE_CSG,
        "csg_non_deductible": CODE_CSG,
        "crds": CODE_CRDS,
        "deduction_hs_patronale": "021",
    }
    if identifiant in principaux:
        return principaux[identifiant]
    return _code_depuis_libelle(libelle)


_MOTS_CLES: List[Tuple[str, str]] = [
    ("réduction générale", CODE_REDUCTION_GENERALE),
    ("reduction generale", CODE_REDUCTION_GENERALE),
    ("déduction forfaitaire heures", "021"),
    ("deduction forfaitaire heures", "021"),
    ("réduction de cotisations sur heures", "114"),
    ("reduction de cotisations sur heures", "114"),
    ("accident", "045"),
    ("at/mp", "045"),
    ("ags", "048"),
    ("fnal", "049"),
    ("aide au logement", "049"),
    ("solidarité autonomie", "068"),
    ("solidarite autonomie", "068"),
    ("allocations familiales", CODE_AF),
    ("maladie", CODE_MALADIE),
    ("vieillesse", "076"),
    ("chômage", "040"),
    ("chomage", "040"),
    ("dialogue", "100"),
    ("formation", "128"),
    ("apprentissage", "130"),
    ("apec", CODE_APEC),
    ("agirc", CODE_AGIRC_ARRCO),
    ("arrco", CODE_AGIRC_ARRCO),
    ("retraite complémentaire", CODE_AGIRC_ARRCO),
    ("retraite complementaire", CODE_AGIRC_ARRCO),
    ("ceg", CODE_AGIRC_ARRCO),
    ("forfait social", CODE_FORFAIT_SOCIAL),
    ("crds", CODE_CRDS),
    ("csg", CODE_CSG),
    ("prévoyance", PSC_COTISATION_CODE),
    ("prevoyance", PSC_COTISATION_CODE),
    ("mutuelle", PSC_COTISATION_CODE),
    ("complémentaire santé", PSC_COTISATION_CODE),
]


def _code_depuis_libelle(libelle: str) -> Optional[str]:
    minuscule = (libelle or "").lower()
    for mot, code in _MOTS_CLES:
        if mot in minuscule:
            return code
    return None


def _traduire(
    ligne: Dict[str, Any], tmax: float, assiette_heures_sup: float
) -> List[LigneDsn]:
    """Lignes DSN produites par une ligne de bulletin, hors CSG/CRDS."""
    coti_id = str(ligne.get("coti_id") or "")
    libelle = str(ligne.get("libelle") or "")
    if coti_id in COTI_ID_NON_INDIVIDUELS:
        return []
    assiette, sal, pat, taux_sal, taux_pat = _parts(ligne)
    montant = round(sal + pat, 2)

    if coti_id in {"securite_sociale_maladie", "maladie_alsace_moselle"}:
        return _maladie(assiette, montant, taux_pat or taux_sal)
    if coti_id == "allocations_familiales":
        return _allocations_familiales(assiette, montant, taux_pat or taux_sal)
    if coti_id == "fnal":
        return _fnal(assiette, montant, taux_pat or taux_sal)
    if coti_id == "reduction_generale":
        return _reduction_generale(assiette, montant, tmax)
    if coti_id == "deduction_hs_patronale":
        return _deduction_heures_supplementaires(ligne, assiette_heures_sup)

    regle = REGLES.get(coti_id)
    if regle is None:
        code = _code_depuis_libelle(libelle)
        if code is None:
            return []
        regle = Regle(code, BASE_BRUT_DEPLAFONNE)

    # Agirc-Arrco : le code générique porte le **total** de la cotisation, et la
    # part patronale est redéclarée à part, par tranche. Vérifié salarié par
    # salarié : 131 = 142 + part salariale, au centime.
    if regle.code_patronal:
        lignes: List[LigneDsn] = []
        if montant:
            lignes.append(LigneDsn(regle.code, regle.base, 0.0, montant, 0.0))
        if pat:
            lignes.append(
                LigneDsn(regle.code_patronal, regle.base, 0.0, round(pat, 2), taux_pat)
            )
        return lignes

    if regle.base == BASE_PREVOYANCE:
        return [
            LigneDsn(
                regle.code,
                BASE_PREVOYANCE,
                0.0,
                montant,
                0.0,
                affiliation_id=str(ligne.get("identifiant_affiliation") or ""),
                distincte=True,
            )
        ]

    if not montant and not assiette:
        return []
    # Le taux DSN se déclare toujours positif, même sur une réduction : c'est le
    # montant qui porte le signe.
    return [
        LigneDsn(
            regle.code,
            regle.base,
            assiette,
            montant,
            abs(round(taux_sal + taux_pat, 6)),
        )
    ]


# --------------------------------------------------------------------------
# Construction des blocs
# --------------------------------------------------------------------------


def _taux_dsn(taux_fraction: float) -> str:
    """La DSN attend un taux en pourcentage, à trois décimales."""
    if abs(taux_fraction) < 1e-12:
        return "0.000"
    pourcentage = taux_fraction * 100.0 if abs(taux_fraction) <= 1.0 else taux_fraction
    return f"{pourcentage:.3f}"


def _cumuler(lignes: List[LigneDsn]) -> List[LigneDsn]:
    """Fusionne les lignes de même code et même base, sauf celles marquées distinctes."""
    cumulees: Dict[Tuple[str, str], LigneDsn] = {}
    ordre: List[LigneDsn] = []
    for ligne in lignes:
        if ligne.distincte:
            ordre.append(ligne)
            continue
        cle = (ligne.base, ligne.code)
        existante = cumulees.get(cle)
        if existante is None:
            cumulees[cle] = ligne
            ordre.append(ligne)
            continue
        existante.montant = round(existante.montant + ligne.montant, 2)
        existante.assiette = max(existante.assiette, ligne.assiette)
        existante.taux = round(existante.taux + ligne.taux, 6)
    return ordre


#: Codes que le cabinet déclare sans identifiant OPS (S21.G00.81.002) : la
#: cotisation individuelle Prévoyance (059) le refuse même — CCH-11 — et les
#: réductions 106 / 131 sortent nues dans toutes les DSN acceptées.
CODES_SANS_OPS = {"059", "106", "131"}


def build_bases_and_cotisations(
    cotisation_lines: List[Dict[str, Any]],
    *,
    brut: float,
    period_start: str,
    period_end: str,
    require_codes: bool = False,
    default_ops: str = "",
    smic_retenu: Optional[float] = None,
    affiliation_ids: Optional[List[str]] = None,
) -> Tuple[List[BaseAssujettieBlock], List[CotisationIndividuelleBlock], List[str]]:
    """Bases assujetties et cotisations individuelles d'un bulletin.

    ``smic_retenu`` alimente le composant S21.G00.79 type 01 sous la base 03 —
    le montant du SMIC pris pour la réduction générale, sans lequel déclarer le
    code 018 est refusé (CCH-17). ``affiliation_ids`` sont les identifiants
    techniques d'affiliation (S21.G00.70.012) du salarié, dans l'ordre : chaque
    cotisation 059 obtient sa propre base 31 qui référence le sien.
    """
    avertissements: List[str] = []
    lignes_valides = [l for l in cotisation_lines if isinstance(l, dict)]
    tmax = _tmax_applicable(lignes_valides)
    assiette_hs = _assiette_heures_supplementaires(lignes_valides)

    produites: List[LigneDsn] = []
    for ligne in lignes_valides:
        coti_id = str(ligne.get("coti_id") or "")
        libelle = str(ligne.get("libelle") or "")
        if coti_id in {"csg_deductible", "csg_non_deductible", "crds"} or (
            not coti_id and ("csg" in libelle.lower() or "crds" in libelle.lower())
        ):
            continue  # traitées en bloc plus bas
        if coti_id in COTI_ID_NON_INDIVIDUELS:
            continue  # déclarées au niveau de l'établissement, pas du salarié
        traduites = _traduire(ligne, tmax, assiette_hs)
        if traduites:
            produites.extend(traduites)
            continue
        intitule = libelle or coti_id or "?"
        if require_codes:
            raise CotisationMappingError(
                f"Impossible de traduire la cotisation '{intitule}' en code DSN"
            )
        avertissements.append(f"Cotisation non traduite, ignorée : {intitule}")

    produites.extend(_csg_et_crds(lignes_valides))
    produites = _cumuler(produites)

    # Montant de chaque base assujettie. La prévoyance (base 31) est traitée à
    # part : une base par cotisation 059, pas une base fourre-tout.
    lignes_prevoyance = [l for l in produites if l.base == BASE_PREVOYANCE]
    montants_base: Dict[str, float] = {}
    if brut > 0:
        montants_base[BASE_BRUT_DEPLAFONNE] = round(brut, 2)
    for ligne in produites:
        if ligne.base == BASE_PREVOYANCE:
            continue
        if ligne.assiette:
            montants_base[ligne.base] = max(
                montants_base.get(ligne.base, 0.0), round(ligne.assiette, 2)
            )
        else:
            montants_base.setdefault(ligne.base, 0.0)

    bases: List[BaseAssujettieBlock] = []
    for code in ORDRE_BASES:
        if code not in montants_base:
            continue
        montant = montants_base[code]
        rubriques: Dict[str, Any] = {
            "S21.G00.78.001": code,
            "S21.G00.78.002": period_start,
            "S21.G00.78.003": period_end,
            "S21.G00.78.004": f"{montant:.2f}",
        }
        if code == BASE_BRUT_DEPLAFONNE and smic_retenu:
            # Composant « 01 - montant du SMIC retenu pour la réduction
            # générale » : sa présence conditionne le droit de déclarer 018/106.
            rubriques["_composants_79"] = [
                {"type": "01", "montant": f"{float(smic_retenu):.2f}"}
            ]
        bases.append(
            BaseAssujettieBlock(
                code=code,
                date_debut=period_start,
                date_fin=period_end,
                montant=montant,
                rubriques=rubriques,
            )
        )

    cotisations: List[CotisationIndividuelleBlock] = []
    for base in bases:
        for ligne in produites:
            if ligne.base != base.code:
                continue
            rubriques = {"S21.G00.81.001": ligne.code}
            identifiant = ligne.ops_identifiant or default_ops
            if identifiant and ligne.code not in CODES_SANS_OPS:
                rubriques["S21.G00.81.002"] = identifiant
            if ligne.assiette:
                rubriques["S21.G00.81.003"] = f"{ligne.assiette:.2f}"
            rubriques["S21.G00.81.004"] = f"{ligne.montant:.2f}"
            rubriques["S21.G00.81.007"] = _taux_dsn(ligne.taux)
            if ligne.affiliation_id:
                rubriques["S21.G00.81.005"] = ligne.affiliation_id
            cotisations.append(
                CotisationIndividuelleBlock(
                    code=ligne.code,
                    montant_assiette=ligne.assiette,
                    montant_salarial=0.0,
                    montant_patronal=ligne.montant,
                    identifiant_affiliation=identifiant or ligne.affiliation_id,
                    rubriques={**rubriques, "_base": base.code},
                )
            )

    # Une base 31 par cotisation 059, comme le cabinet : montant 0.00,
    # identifiant d'affiliation en 78.005, l'assiette réelle portée par un
    # composant 79 type 18, et la cotisation seule, sans identifiant OPS.
    #
    # Chaque identifiant d'affiliation déclaré au bloc 70 exige sa base 31
    # (CCH-13) : si le salarié a plus d'affiliations que le bulletin ne porte
    # de cotisations — typiquement une retraite supplémentaire que le moteur ne
    # calcule pas encore — les affiliations restantes reçoivent une base et une
    # cotisation 059 à zéro. C'est le manque du moteur rendu visible, pas
    # masqué : le montant juste remplacera le zéro, la structure ne bougera pas.
    lignes_31: List[Optional[LigneDsn]] = list(lignes_prevoyance)
    while affiliation_ids and len(lignes_31) < len(affiliation_ids):
        lignes_31.append(None)
    for index, ligne_ou_vide in enumerate(lignes_31):
        ligne = ligne_ou_vide or LigneDsn(
            code="059",
            base=BASE_PREVOYANCE,
            montant=0.0,
            assiette=0.0,
            taux=0.0,
        )
        if affiliation_ids and index < len(affiliation_ids):
            identifiant_affiliation = str(affiliation_ids[index])
        else:
            identifiant_affiliation = str(index + 1)
        code_interne = f"{BASE_PREVOYANCE}#{index}"
        bases.append(
            BaseAssujettieBlock(
                code=code_interne,
                date_debut=period_start,
                date_fin=period_end,
                montant=0.0,
                rubriques={
                    "S21.G00.78.001": BASE_PREVOYANCE,
                    "S21.G00.78.002": period_start,
                    "S21.G00.78.003": period_end,
                    "S21.G00.78.004": "0.00",
                    "S21.G00.78.005": identifiant_affiliation,
                    "_composants_79": [
                        {
                            "type": "18",
                            "montant": f"{(ligne.assiette or brut):.2f}",
                        }
                    ],
                },
            )
        )
        cotisations.append(
            CotisationIndividuelleBlock(
                code=ligne.code,
                montant_assiette=ligne.assiette,
                montant_salarial=0.0,
                montant_patronal=ligne.montant,
                identifiant_affiliation=identifiant_affiliation,
                rubriques={
                    "S21.G00.81.001": ligne.code,
                    "S21.G00.81.004": f"{ligne.montant:.2f}",
                    "S21.G00.81.007": _taux_dsn(ligne.taux),
                    "_base": code_interne,
                },
            )
        )

    return bases, cotisations, avertissements


def is_reduction_generale_code(code: str) -> bool:
    return (code or "").zfill(3) in REDUCTION_GENERALE_COT_CODES


def is_brut_base_code(code: str) -> bool:
    return (code or "").zfill(2) in BASE_ASSUJETTIE_BRUT_CODES
