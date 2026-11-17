"""La convention et la classification d'un salarié à une date.

Cas d'origine : Zone 404 passe de « sans convention » (9999) à Syntec (1486) à
une date d'effet (relevé du 16/11/2026). Ses bulletins de juillet à octobre sont
repris et validés : rattacher Syntec ou changer les classifications sans date
appliquerait Syntec aux mois passés et les ferait passer « à recalculer ».

Deux dates d'effet, sans I/O ici :

- la convention de la société : `company_collective_agreements.date_debut` /
  `date_fin` (bornes incluses). Sans aucune ligne datée, la première ligne vaut
  toujours, comme avant ;
- la classification de la fiche : la note `classification_avant` posée par le
  serveur dans `classification_conventionnelle`, `{"a_partir_du", "classification"}`.
  Le haut de la classification est la nouvelle ; avant la date, c'est la
  précédente, telle qu'elle était enregistrée (ses propres notes comprises).

Un mois de paie se lit à son dernier jour : une date d'effet au 01/11 laisse
octobre sur l'ancienne convention et met novembre sur la nouvelle.
"""

from __future__ import annotations

import calendar
import json
from datetime import date, datetime
from typing import Any, Iterable, Mapping, Optional

#: La note posée dans la classification de la fiche.
CLE_CLASSIFICATION_AVANT = "classification_avant"


def jour(valeur: Any) -> Optional[date]:
    if isinstance(valeur, datetime):
        return valeur.date()
    if isinstance(valeur, date):
        return valeur
    if isinstance(valeur, str) and valeur.strip():
        try:
            return date.fromisoformat(valeur.strip()[:10])
        except ValueError:
            return None
    return None


def fin_du_mois(annee: int, mois: int) -> date:
    """Le jour auquel un mois de paie lit sa convention et sa classification."""
    return date(annee, mois, calendar.monthrange(annee, mois)[1])


def a_des_dates(lignes: Iterable[Mapping[str, Any]]) -> bool:
    return any(jour(ligne.get("date_debut")) or jour(ligne.get("date_fin")) for ligne in lignes)


def ligne_en_vigueur(
    lignes: Iterable[Mapping[str, Any]], a_la_date: Optional[date] = None
) -> Optional[Mapping[str, Any]]:
    """La ligne `company_collective_agreements` qui vaut à la date, ou None.

    Sans aucune ligne datée : la première, comme avant les dates d'effet. Sinon,
    parmi les lignes en vigueur (début ≤ date ≤ fin, borne absente = ouverte),
    la plus récemment commencée ; une ligne sans début vaut depuis toujours et
    cède la place à une ligne datée dès que celle-ci commence.
    """
    lignes = [ligne for ligne in lignes if ligne.get("collective_agreement_id")]
    if not lignes:
        return None
    if not a_des_dates(lignes):
        return lignes[0]
    d = jour(a_la_date) or date.today()
    en_vigueur = []
    for ligne in lignes:
        debut, fin = jour(ligne.get("date_debut")), jour(ligne.get("date_fin"))
        if (debut is None or debut <= d) and (fin is None or d <= fin):
            en_vigueur.append(ligne)
    if not en_vigueur:
        return None
    datees = sorted(
        (ligne for ligne in en_vigueur if jour(ligne.get("date_debut"))),
        key=lambda ligne: jour(ligne.get("date_debut")),
        reverse=True,
    )
    return (datees or en_vigueur)[0]


def agreement_id_en_vigueur(
    lignes: Iterable[Mapping[str, Any]], a_la_date: Optional[date] = None
) -> Optional[str]:
    ligne = ligne_en_vigueur(lignes, a_la_date)
    return str(ligne["collective_agreement_id"]) if ligne else None


def _en_dict(classification: Any) -> Any:
    if isinstance(classification, str):
        try:
            lue = json.loads(classification)
        except ValueError:
            return classification
        return lue if isinstance(lue, dict) else classification
    return classification


def _note(classification: Any) -> Optional[Mapping[str, Any]]:
    if not isinstance(classification, Mapping):
        return None
    note = classification.get(CLE_CLASSIFICATION_AVANT)
    if isinstance(note, Mapping) and jour(note.get("a_partir_du")) and "classification" in note:
        return note
    return None


def classification_a_la_date(classification: Any, a_la_date: date) -> Any:
    """La classification qui vaut à la date.

    Sans note datée, la classification est rendue telle quelle (même objet) :
    l'empreinte d'une fiche sans changement daté ne bouge pas.
    """
    lue = _en_dict(classification)
    if not isinstance(lue, Mapping) or CLE_CLASSIFICATION_AVANT not in lue:
        return classification
    note = _note(lue)
    d = jour(a_la_date) or date.today()
    if note is not None and d < jour(note["a_partir_du"]):
        return classification_a_la_date(note["classification"], a_la_date)
    return {cle: valeur for cle, valeur in lue.items() if cle != CLE_CLASSIFICATION_AVANT}


def classification_du_mois(classification: Any, annee: int, mois: int) -> Any:
    return classification_a_la_date(classification, fin_du_mois(annee, mois))


def fiche_a_la_date(employee: Mapping[str, Any], a_la_date: date) -> dict[str, Any]:
    """La fiche avec la classification qui vaut à la date ; inchangée sans note."""
    fiche = dict(employee)
    brute = fiche.get("classification_conventionnelle")
    datee = classification_a_la_date(brute, a_la_date)
    if datee is not brute:
        fiche["classification_conventionnelle"] = datee
    return fiche


def dater_changement_classification(
    avant: Any, apres: Any, a_partir_du: Optional[date]
) -> Any:
    """La classification à écrire sur la fiche.

    Avec une date : la nouvelle vaut à partir de cette date, la classification
    enregistrée jusque-là reste pour les mois antérieurs. Une note déjà posée à
    cette date ou après est remplacée (la nouvelle classification la recouvre).
    Sans date : la note enregistrée est gardée telle quelle. Seul le serveur pose
    la note : celle que le client renvoie est ignorée.
    """
    if not isinstance(apres, Mapping):
        return apres
    resultat = {cle: valeur for cle, valeur in apres.items() if cle != CLE_CLASSIFICATION_AVANT}
    avant = _en_dict(avant)
    if a_partir_du is None:
        note = _note(avant)
        if note is not None:
            resultat[CLE_CLASSIFICATION_AVANT] = dict(note)
        return resultat
    precedente = avant
    note = _note(precedente)
    while note is not None and jour(note["a_partir_du"]) >= a_partir_du:
        precedente = note["classification"]
        note = _note(precedente)
    resultat[CLE_CLASSIFICATION_AVANT] = {
        "a_partir_du": a_partir_du.isoformat(),
        "classification": precedente,
    }
    return resultat
