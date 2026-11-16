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
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from typing import Any

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


def compter_jours_travailles(
    prevu: Mapping[date, Mapping[str, Any]],
    reel: Mapping[date, Mapping[str, Any]],
    jours_absence: set[date],
    debut: date,
    fin: date,
    min_heures: float | None = None,
) -> int:
    seuil = float(min_heures) if min_heures else 0.0
    n = 0
    jour = debut
    while jour <= fin:
        r = reel.get(jour) or {}
        faites = _heures(r.get("heures_faites"))
        if faites is not None:
            heures = faites
        else:
            p = prevu.get(jour) or {}
            type_prevu = str(p.get("type") or "").lower()
            heures = 0.0
            if type_prevu in TYPES_TRAVAIL and jour not in jours_absence:
                heures = _heures(p.get("heures_prevues")) or 0.0
        if heures > 0 and heures >= seuil:
            n += 1
        jour += timedelta(days=1)
    return n
