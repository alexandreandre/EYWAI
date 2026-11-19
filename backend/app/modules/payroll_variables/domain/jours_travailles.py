"""Jours travaillés d'un salarié sur la fenêtre des variables, lus dans son calendrier.

Sert la règle « Par jour travaillé » (paniers, primes de poste) : les sociétés
remplissent les calendriers des salariés, pas le module Planning, et la règle
« Par type de poste » ne comptait donc rien chez elles (retour d'Elsa, 16/11).

Un jour compte quand le salarié y a travaillé :
- des heures réelles saisies > 0 ;
- sans heures réelles saisies, un jour « travail » prévu > 0 qui n'est pas
  couvert par une absence validée (c'est le jour que la paie paie au prévu).
Un seuil d'heures facultatif écarte les jours trop courts (panier dû à partir
de N heures, par exemple).

Des plages d'heure de début facultatives ne gardent que les postes commencés
dans l'une d'elles (retour d'Elsa du 17/11 : « panier si le poste commence à
4 h ou 12 h »). L'heure de début est celle du relevé importé (`debut` du jour
réel, voir `schedules.domain.horaires_pointes`) ; un jour travaillé sans heure
de début ne compte pas et il est compté à part, pour le dire à la RH.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from typing import Any

from app.modules.schedules.domain.horaires_pointes import debut_dans_les_plages

TYPES_TRAVAIL = {"travail", "travaille", "work"}


def _heures(valeur: Any) -> float | None:
    if valeur is None or valeur == "":
        return None
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def index_calendrier(
    annee: int, mois: int, entrees: Iterable[Mapping[str, Any]] | None
) -> dict[date, Mapping[str, Any]]:
    """Les entrées d'un calendrier mensuel (`jour` = numéro du jour), par date."""
    index: dict[date, Mapping[str, Any]] = {}
    for e in entrees or []:
        if not isinstance(e, Mapping):
            continue
        try:
            jour = date(annee, mois, int(e.get("jour")))
        except (TypeError, ValueError):
            continue
        index[jour] = e
    return index


def heures_du_jour(
    p: Mapping[str, Any] | None, r: Mapping[str, Any] | None, absent: bool
) -> float:
    """Heures travaillées d'un jour : le réel saisi, sinon le prévu « travail »
    hors absence validée (le jour que la paie paie au prévu)."""
    faites = _heures((r or {}).get("heures_faites"))
    if faites is not None:
        return faites
    p = p or {}
    if str(p.get("type") or "").lower() in TYPES_TRAVAIL and not absent:
        return _heures(p.get("heures_prevues")) or 0.0
    return 0.0


def detail_jours_travailles(
    prevu: Mapping[date, Mapping[str, Any]],
    reel: Mapping[date, Mapping[str, Any]],
    jours_absence: set[date],
    debut: date,
    fin: date,
    min_heures: float | None = None,
    plages_debut: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """`{jours, sans_heure_de_debut, dates}` : les jours qui comptent, et, si
    des plages de début sont demandées, les jours travaillés sans heure lue."""
    seuil = float(min_heures) if min_heures else 0.0
    plages = [p for p in (plages_debut or []) if isinstance(p, Mapping)]
    n = 0
    sans_debut = 0
    dates: list[str] = []
    jour = debut
    while jour <= fin:
        r = reel.get(jour) or {}
        heures = heures_du_jour(prevu.get(jour), r, jour in jours_absence)
        if heures > 0 and heures >= seuil:
            if not plages:
                n += 1
                dates.append(jour.isoformat())
            elif not r.get("debut"):
                sans_debut += 1
            elif debut_dans_les_plages(r.get("debut"), plages):
                n += 1
                dates.append(jour.isoformat())
        jour += timedelta(days=1)
    return {"jours": n, "sans_heure_de_debut": sans_debut, "dates": dates}


def compter_jours_travailles(
    prevu: Mapping[date, Mapping[str, Any]],
    reel: Mapping[date, Mapping[str, Any]],
    jours_absence: set[date],
    debut: date,
    fin: date,
    min_heures: float | None = None,
    plages_debut: Iterable[Mapping[str, Any]] | None = None,
) -> int:
    return detail_jours_travailles(
        prevu, reel, jours_absence, debut, fin, min_heures, plages_debut
    )["jours"]
