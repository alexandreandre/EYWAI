"""Regroupement officiel des cotisations par risque (modèle clarifié arrêté 25/02/2016)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# Ordre réglementaire des rubriques (hors exonérations).
RUBRIQUES_ORDRE: List[Tuple[str, str]] = [
    ("sante", "Santé"),
    ("at_mp", "Accidents du travail et maladies professionnelles"),
    ("retraite", "Retraite"),
    ("famille", "Famille"),
    ("chomage", "Assurance chômage"),
    (
        "autres_contributions_employeur",
        "Autres contributions dues par l'employeur",
    ),
    (
        "cotisations_statutaires",
        "Cotisations statutaires et conventionnelles",
    ),
    ("csg_deductible", "CSG déductible"),
    ("csg_non_deductible", "CSG/CRDS non déductible"),
]

RUBRIQUE_EXONERATIONS = (
    "exonerations",
    "Exonérations, allègements et réductions",
)

COTI_ID_TO_RUBRIQUE: Dict[str, str] = {
    "securite_sociale_maladie": "sante",
    "maladie_alsace_moselle": "sante",
    "mutuelle": "sante",
    "complementaire_sante": "sante",
    "at_mp": "at_mp",
    "vieillesse_plafonnee": "retraite",
    "vieillesse_deplafonnee": "retraite",
    "assurance_vieillesse_salarial": "retraite",
    "assurance_vieillesse_patronal": "retraite",
    "retraite_comp_t1": "retraite",
    "retraite_comp_t2": "retraite",
    "ceg_t1": "retraite",
    "ceg_t2": "retraite",
    "cet": "retraite",
    "apec": "retraite",
    "allocations_familiales": "famille",
    "assurance_chomage": "chomage",
    "chomage": "chomage",
    "ags": "chomage",
    "fnal": "autres_contributions_employeur",
    "CFP": "autres_contributions_employeur",
    "cfp": "autres_contributions_employeur",
    "taxe_apprentissage": "autres_contributions_employeur",
    "taxe_apprentissage_solde": "autres_contributions_employeur",
    "csa": "autres_contributions_employeur",
    "dialogue_social": "autres_contributions_employeur",
    "versement_mobilite": "autres_contributions_employeur",
    "forfait_social": "autres_contributions_employeur",
    "prevoyance_cadre": "cotisations_statutaires",
    "prevoyance_non_cadre": "cotisations_statutaires",
    "csg_deductible": "csg_deductible",
    "csg_non_deductible": "csg_non_deductible",
    "crds": "csg_non_deductible",
    "reduction_generale": RUBRIQUE_EXONERATIONS[0],
    "reduction_hs_salariale": RUBRIQUE_EXONERATIONS[0],
    "deduction_hs_patronale": RUBRIQUE_EXONERATIONS[0],
    "exoneration_apprenti_salariale": RUBRIQUE_EXONERATIONS[0],
    "exoneration_stage": RUBRIQUE_EXONERATIONS[0],
    "exoneration_jei": RUBRIQUE_EXONERATIONS[0],
}

EXONERATION_KEYWORDS = (
    "réduction générale",
    "reduction generale",
    "réduction de cotisations sur heures sup",
    "déduction forfaitaire",
    "exonération",
    "exoneration",
    "allègement",
    "allegement",
    "exonération jei",
    "exoneration jei",
    "gratification de stage exonérée",
)

LIBELLE_KEYWORD_TO_RUBRIQUE: List[Tuple[str, str]] = [
    ("mutuelle", "sante"),
    ("frais de santé", "sante"),
    ("complémentaire santé", "sante"),
    ("maladie", "sante"),
    ("accident", "at_mp"),
    ("at/mp", "at_mp"),
    ("vieillesse", "retraite"),
    ("retraite", "retraite"),
    ("agirc", "retraite"),
    ("arrco", "retraite"),
    ("ceg", "retraite"),
    ("cet", "retraite"),
    ("apec", "retraite"),
    ("allocations familiales", "famille"),
    ("famille", "famille"),
    ("chômage", "chomage"),
    ("chomage", "chomage"),
    ("ags", "chomage"),
    ("fnal", "autres_contributions_employeur"),
    ("formation", "autres_contributions_employeur"),
    ("apprentissage", "autres_contributions_employeur"),
    ("solidarité", "autres_contributions_employeur"),
    ("dialogue", "autres_contributions_employeur"),
    ("mobilité", "autres_contributions_employeur"),
    ("mobilite", "autres_contributions_employeur"),
    ("forfait social", "autres_contributions_employeur"),
    ("prévoyance", "cotisations_statutaires"),
    ("prevoyance", "cotisations_statutaires"),
    ("csg déductible", "csg_deductible"),
    ("csg/crds non déductible", "csg_non_deductible"),
    ("csg/crds sur hs", "csg_non_deductible"),
]


def _normaliser_libelle(libelle: str) -> str:
    return (libelle or "").lower().replace("é", "e").replace("è", "e")


def est_ligne_exoneration(coti_id: Optional[str], libelle: str) -> bool:
    if coti_id and COTI_ID_TO_RUBRIQUE.get(coti_id) == RUBRIQUE_EXONERATIONS[0]:
        return True
    lib = _normaliser_libelle(libelle)
    return any(kw in lib for kw in EXONERATION_KEYWORDS)


def resoudre_rubrique(
    coti_id: Optional[str] = None, libelle: str = ""
) -> str:
    """Retourne le code rubrique officiel ; fallback « autres » si non mappé."""
    if coti_id and coti_id in COTI_ID_TO_RUBRIQUE:
        return COTI_ID_TO_RUBRIQUE[coti_id]

    lib = _normaliser_libelle(libelle)
    if est_ligne_exoneration(coti_id, libelle):
        return RUBRIQUE_EXONERATIONS[0]

    if "csg deductible" in lib and "non" not in lib:
        return "csg_deductible"
    if "csg/crds" in lib or "csg crds" in lib:
        if "non" in lib or "hs" in lib:
            return "csg_non_deductible"
        if "deductible" in lib:
            return "csg_deductible"

    for keyword, rubrique in LIBELLE_KEYWORD_TO_RUBRIQUE:
        if keyword in lib:
            return rubrique

    return "autres"


def libelle_rubrique(code: str) -> str:
    if code == RUBRIQUE_EXONERATIONS[0]:
        return RUBRIQUE_EXONERATIONS[1]
    for rub_code, rub_lib in RUBRIQUES_ORDRE:
        if rub_code == code:
            return rub_lib
    if code == "autres":
        return "Autres cotisations et contributions"
    return code


def enrichir_ligne_cotisation(
    ligne: Dict[str, Any], coti_id: Optional[str] = None
) -> Dict[str, Any]:
    """Attache coti_id et rubrique à une ligne sans modifier les clés existantes."""
    cid = coti_id or ligne.get("coti_id")
    rubrique = resoudre_rubrique(cid, ligne.get("libelle", ""))
    ligne["coti_id"] = cid
    ligne["rubrique"] = rubrique
    return ligne


def construire_cotisations_officielles(
    lignes_cotisations: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], float]:
    """
    Construit la liste ordonnée des rubriques officielles et le total des exonérations.

    Les lignes d'exonération/allègement sont regroupées dans la rubrique dédiée.
    """
    buckets: Dict[str, List[Dict[str, Any]]] = {
        code: [] for code, _ in RUBRIQUES_ORDRE
    }
    buckets[RUBRIQUE_EXONERATIONS[0]] = []
    buckets["autres"] = []

    for ligne in lignes_cotisations:
        ligne_enrichie = enrichir_ligne_cotisation(dict(ligne))
        rubrique = ligne_enrichie["rubrique"]
        if rubrique not in buckets:
            buckets.setdefault("autres", []).append(ligne_enrichie)
        else:
            buckets[rubrique].append(ligne_enrichie)

    cotisations_officielles: List[Dict[str, Any]] = []
    ordre_affichage = [code for code, _ in RUBRIQUES_ORDRE] + ["autres"]

    for code in ordre_affichage:
        lignes = buckets.get(code, [])
        if not lignes:
            continue
        total_salarial = round(
            sum((ligne.get("montant_salarial") or 0.0) for ligne in lignes), 2
        )
        total_patronal = round(
            sum((ligne.get("montant_patronal") or 0.0) for ligne in lignes), 2
        )
        cotisations_officielles.append(
            {
                "code": code,
                "libelle": libelle_rubrique(code),
                "lignes": lignes,
                "total_salarial": total_salarial,
                "total_patronal": total_patronal,
            }
        )

    exo_lignes = buckets.get(RUBRIQUE_EXONERATIONS[0], [])
    total_exonerations = 0.0
    if exo_lignes:
        total_salarial = round(
            sum((ligne.get("montant_salarial") or 0.0) for ligne in exo_lignes), 2
        )
        total_patronal = round(
            sum((ligne.get("montant_patronal") or 0.0) for ligne in exo_lignes), 2
        )
        # Total exonérations = valeur absolue des montants négatifs (allègements).
        total_exonerations = round(
            abs(min(0.0, total_salarial)) + abs(min(0.0, total_patronal)), 2
        )
        cotisations_officielles.append(
            {
                "code": RUBRIQUE_EXONERATIONS[0],
                "libelle": RUBRIQUE_EXONERATIONS[1],
                "lignes": exo_lignes,
                "total_salarial": total_salarial,
                "total_patronal": total_patronal,
            }
        )

    return cotisations_officielles, total_exonerations
