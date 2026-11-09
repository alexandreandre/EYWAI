"""Le bloc « Changements Contrat » (S21.G00.41) d'un changement de temps de travail.

Cas d'origine : un forfait jours qui passe aux heures (R-462, forfaits de Zone 404 sous le
plancher Syntec). Cahier technique DSN 2026.1.2 : rubriques .006 (unité), .007 (quotité), .008
(modalité), .022 (quotité de référence), portant « la valeur avant changement » (p. 215) ; date
de la modification et profondeur de recalcul obligatoires (p. 26) ; « si deux modalités
différentes faisaient l'objet d'un changement […], ces changements doivent être déclarés dans
différents blocs » (p. 25).

La fiche garde `temps_travail_changement = {"date", "anciens": {rubrique: valeur}}` dans la
classification, comme `pcs_changement`. Date et profondeur sont au 1er du mois de
l'enregistrement : le bulletin du mois se calcule entier sur la fiche du jour. Seul le serveur
pose la note ; ce que le client renvoie est ignoré.
"""

from __future__ import annotations

from datetime import date
from typing import AbstractSet, Any, Dict, List, Optional, Tuple

from app.modules.dsn_export.domain.contract_map import debut_du_contrat, map_modalite_temps
from app.modules.dsn_import.domain.model import ChangementContratBlock
from app.modules.payroll.engine.forfait_individuel import jours_du_forfait_de_la_fiche

CLE = "temps_travail_changement"
UNITE, QUOTITE, MODALITE, REFERENCE = (
    "S21.G00.41.006",
    "S21.G00.41.007",
    "S21.G00.41.008",
    "S21.G00.41.022",
)
#: Les rubriques du bloc 41, dans l'ordre de `map_modalite_temps` (unité, référence, quotité, modalité).
_ORDRE = (UNITE, REFERENCE, QUOTITE, MODALITE)
Temps = Tuple[str, str, str, str]


def _classification(fiche: Any) -> Dict[str, Any]:
    valeur = fiche.get("classification_conventionnelle") if isinstance(fiche, dict) else None
    return valeur if isinstance(valeur, dict) else {}


def valeurs_dsn(fiche: Any, quotite_forfait_jours: str = "") -> Optional[Dict[str, str]]:
    """{rubrique du bloc 41: valeur déclarée pour cette fiche} ; None si la fiche se refuse."""
    try:
        jours = jours_du_forfait_de_la_fiche(fiche.get("specificites_paie"))
        duree = fiche.get("duree_hebdomadaire")
        temps = map_modalite_temps(
            is_temps_partiel=bool(fiche.get("is_temps_partiel")),
            duree_hebdo=float(duree) if duree is not None else None,
            is_forfait_jour=bool(fiche.get("is_forfait_jour")),
            quotite_forfait_jours=quotite_forfait_jours,
            jours_forfait_salarie=jours,
        )
    except (TypeError, ValueError):
        return None
    return dict(zip(_ORDRE, temps))


def _note(classification: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    note = classification.get(CLE)
    return note if isinstance(note, dict) and note.get("date") and note.get("anciens") else None


def _en_attente(note: Optional[Dict[str, Any]], periodes_declarees: AbstractSet[str]) -> bool:
    return bool(note) and not any(p >= str(note["date"])[:7] for p in periodes_declarees)


def appliquer_changement_temps_travail(
    fiche_avant: Any,
    fiche_apres: Any,
    *,
    aujourd_hui: date,
    depuis_import: bool,
    periodes_declarees: AbstractSet[str],
    debut_contrat: Optional[str],
    quotite_forfait_jours: str = "",
) -> Dict[str, Any]:
    """La classification à écrire, avec le changement de temps de travail noté, gardé ou retiré."""
    classification_apres = _classification(fiche_apres) or _classification(fiche_avant)
    resultat = {k: v for k, v in classification_apres.items() if k != CLE}
    existante = _note(_classification(fiche_avant))

    def garder() -> Dict[str, Any]:
        if existante:
            resultat[CLE] = existante
        return resultat

    if depuis_import:
        return garder()
    avant = valeurs_dsn(fiche_avant, quotite_forfait_jours)
    apres = valeurs_dsn(fiche_apres, quotite_forfait_jours)
    if avant is None or apres is None or avant == apres:
        return garder()
    attente = _en_attente(existante, periodes_declarees)
    originaux = {**avant, **(existante["anciens"] if attente else {})}
    differences = {r: originaux[r] for r in _ORDRE if originaux[r] != apres[r]}
    debut_du_mois = f"{aujourd_hui:%Y-%m}-01"
    if not differences or (debut_contrat and str(debut_contrat)[:10] >= debut_du_mois and not attente):
        return resultat
    resultat[CLE] = {"date": debut_du_mois, "anciens": differences}
    return resultat


def _en_vigueur(note: Dict[str, Any], period: str) -> bool:
    return str(note["date"])[:7] <= period[:7]


def temps_du_mois(classification: Any, period: str, actuel: Temps) -> Temps:
    """(unité, référence, quotité, modalité) du mois déclaré : les anciennes valeurs avant le changement."""
    note = _note(classification if isinstance(classification, dict) else {})
    if not note or _en_vigueur(note, period):
        return actuel
    anciens = note["anciens"]
    valeurs = dict(zip(_ORDRE, actuel))
    return tuple(anciens.get(r, valeurs[r]) for r in _ORDRE)  # type: ignore[return-value]


def blocs_changement_temps_travail(
    classification: Any,
    period: str,
    periodes_declarees: AbstractSet[str],
    debut_contrat: str,
) -> List[ChangementContratBlock]:
    """Un bloc 41 par modalité changée, dans toute DSN du mois (régénérée comprise), et dans
    celles d'après tant qu'aucune DSN d'un mois intermédiaire n'est partie."""
    note = _note(classification if isinstance(classification, dict) else {})
    if not note or not _en_vigueur(note, period):
        return []
    jour = str(note["date"])[:10]
    mois = jour[:7]
    if any(mois <= p < period[:7] for p in periodes_declarees):
        return []
    if not debut_contrat or str(debut_contrat)[:10] >= f"{mois}-01":
        return []
    annee, m, j = jour.split("-")
    date_dsn = f"{j}{m}{annee}"
    return [
        ChangementContratBlock(
            date_modification=date_dsn,
            rubriques={
                "S21.G00.41.001": date_dsn,
                rubrique: str(note["anciens"][rubrique]),
                "S21.G00.41.028": date_dsn,
            },
        )
        for rubrique in sorted(note["anciens"])
    ]


def avis_changements_temps_travail(
    employees_data: Any, period: str, periodes_declarees: AbstractSet[str]
) -> Optional[str]:
    """La ligne de l'aperçu DSN qui dit combien de changements de temps de travail partent."""
    n = 0
    for row in employees_data or []:
        employee = (row.get("employee") or row) if isinstance(row, dict) else {}
        if blocs_changement_temps_travail(
            employee.get("classification_conventionnelle"), period, periodes_declarees, debut_du_contrat(employee)
        ):
            n += 1
    if not n:
        return None
    return (
        f"Temps de travail changé pour {n} salarié{'s' if n > 1 else ''} : la DSN déclare les "
        "anciennes valeurs (bloc Changements Contrat, S21.G00.41)."
    )
