"""Le bloc « Changements Contrat » (S21.G00.41) d'un changement de convention collective.

Cas d'origine : Zone 404, de « sans convention » (9999) à Syntec (1486) au 01/11/2026 (R-462).
Cahier technique DSN 2026.1.2 : rubrique S21.G00.41.011, « la valeur avant changement » (p. 215),
table IDCC, 9999 admis « sans convention collective » ; date de la modification et profondeur de
recalcul obligatoires (p. 26, CCH-12 à 15) ; une modalité par bloc (p. 25).

La fiche garde `convention_changement = {"ancien", "date"}` dans la classification, comme
`pcs_changement`. Date et profondeur sont au 1er du mois de l'enregistrement : le bulletin du mois
se calcule entier sur la fiche du jour. Seul le serveur pose la note ; ce que le client renvoie
est ignoré. Le bloc part dans toute DSN du mois du changement (régénérée comprise), et dans celles
des mois suivants tant qu'aucune DSN d'un mois intermédiaire n'est partie. Un contrat commencé
dans le mois du changement n'a jamais été déclaré avec l'ancien code : pas de bloc.
"""

from __future__ import annotations

from datetime import date
from typing import AbstractSet, Any, Dict, Optional

from app.modules.dsn_export.domain.contract_map import debut_du_contrat
from app.modules.dsn_export.domain.settings import normaliser_idcc
from app.modules.dsn_import.domain.model import ChangementContratBlock

CLE = "convention_changement"
RUBRIQUE = "S21.G00.41.011"


def _classification(valeur: Any) -> Dict[str, Any]:
    return valeur if isinstance(valeur, dict) else {}


def _note(classification: Any) -> Optional[Dict[str, Any]]:
    note = _classification(classification).get(CLE)
    return note if isinstance(note, dict) and note.get("ancien") and note.get("date") else None


def _en_attente(note: Optional[Dict[str, Any]], periodes_declarees: AbstractSet[str]) -> bool:
    return bool(note) and not any(p >= str(note["date"])[:7] for p in periodes_declarees)


def appliquer_changement_convention(
    avant: Optional[Dict[str, Any]],
    apres: Optional[Dict[str, Any]],
    *,
    aujourd_hui: date,
    depuis_import: bool,
    periodes_declarees: AbstractSet[str],
    debut_contrat: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """La classification à écrire, avec le changement de convention posé, gardé ou retiré."""
    if not isinstance(apres, dict):
        return apres
    avant = _classification(avant)
    resultat = {k: v for k, v in apres.items() if k != CLE}
    existante = _note(avant)

    def garder() -> Dict[str, Any]:
        if existante:
            resultat[CLE] = existante
        return resultat

    ancien, nouveau = normaliser_idcc(avant.get("idcc")), normaliser_idcc(apres.get("idcc"))
    if depuis_import or not nouveau or nouveau == ancien or not ancien:
        return garder()
    debut_du_mois = f"{aujourd_hui:%Y-%m}-01"
    if _en_attente(existante, periodes_declarees):
        premier = str(existante["ancien"])
        if premier == nouveau:
            return resultat
        resultat[CLE] = {"ancien": premier, "date": debut_du_mois}
    elif not (debut_contrat and str(debut_contrat)[:10] >= debut_du_mois):
        resultat[CLE] = {"ancien": ancien, "date": debut_du_mois}
    return resultat


def idcc_du_mois(classification: Any, idcc_actuel: str, period: str) -> str:
    """L'IDCC en vigueur pendant le mois déclaré : l'ancien si le changement vient après."""
    note = _note(classification)
    if note and str(note["date"])[:7] > period[:7]:
        return normaliser_idcc(note["ancien"])
    return idcc_actuel


def bloc_changement_convention(
    classification: Any,
    period: str,
    periodes_declarees: AbstractSet[str],
    debut_contrat: str,
) -> Optional[ChangementContratBlock]:
    note = _note(classification)
    if not note:
        return None
    jour = str(note["date"])[:10]
    mois = jour[:7]
    if mois > period[:7] or any(mois <= p < period[:7] for p in periodes_declarees):
        return None
    if not debut_contrat or str(debut_contrat)[:10] >= f"{mois}-01":
        return None
    annee, m, j = jour.split("-")
    date_dsn = f"{j}{m}{annee}"
    return ChangementContratBlock(
        date_modification=date_dsn,
        rubriques={
            "S21.G00.41.001": date_dsn,
            RUBRIQUE: normaliser_idcc(note["ancien"]),
            "S21.G00.41.028": date_dsn,
        },
    )


def avis_changements_convention(
    employees_data: Any, period: str, periodes_declarees: AbstractSet[str]
) -> Optional[str]:
    """La ligne de l'aperçu DSN qui dit combien de changements de convention partent."""
    n = 0
    for row in employees_data or []:
        employee = (row.get("employee") or row) if isinstance(row, dict) else {}
        if bloc_changement_convention(
            employee.get("classification_conventionnelle"), period, periodes_declarees, debut_du_contrat(employee)
        ):
            n += 1
    if not n:
        return None
    return (
        f"Convention collective changée pour {n} salarié{'s' if n > 1 else ''} : la DSN déclare "
        "l'ancienne convention (bloc Changements Contrat, S21.G00.41)."
    )
