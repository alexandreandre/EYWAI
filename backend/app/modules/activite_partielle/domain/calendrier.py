"""Activité partielle posée au calendrier : les heures chômées du mois.

Un jour typé « Activité partielle » est un jour chômé. Ses heures chômées sont
ses heures prévues moins les heures faites ce jour-là (une demi-journée
travaillée réduit d'autant). Un jour posé sans heures prévues vaut une journée
du contrat. Au forfait jours, le jour chômé vaut 7 h (fiche « forfaits jours »
du ministère du Travail) ; une demi-journée faite en retire la moitié.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable

TYPE_JOUR = "activite_partielle"
HEURES_JOUR_FORFAIT = 7.0


@dataclass(frozen=True)
class JourChome:
    jour: int
    heures: float
    annee: int | None = None
    mois: int | None = None


def _nombre(valeur: Any) -> float:
    try:
        return float(valeur or 0)
    except (TypeError, ValueError):
        return 0.0


def jours_chomes(
    prevu: Iterable[dict[str, Any]],
    reel: Iterable[dict[str, Any]],
    *,
    forfait_jours: bool,
    heures_par_jour: float,
) -> list[JourChome]:
    """Jours d'activité partielle (listes du calendrier ; un jour porte son
    `annee` et son `mois` quand les listes couvrent plusieurs mois)."""

    def cle(j: dict[str, Any]) -> tuple[Any, Any, int]:
        return (j.get("annee"), j.get("mois"), int(j["jour"]))

    faites = {cle(j): _nombre(j.get("heures_faites")) for j in reel if j.get("jour")}
    resultat: list[JourChome] = []
    for j in prevu:
        if str(j.get("type") or "") != TYPE_JOUR or not j.get("jour"):
            continue
        jour = int(j["jour"])
        fait = faites.get(cle(j), 0.0)
        prevues = _nombre(j.get("heures_prevues"))
        if forfait_jours:
            part = prevues if 0 < prevues <= 1 else 1.0
            chome = max(0.0, part - min(1.0, fait)) * HEURES_JOUR_FORFAIT
        else:
            if prevues <= 0:
                prevues = float(heures_par_jour)
            chome = max(0.0, prevues - fait)
        if chome > 0:
            resultat.append(JourChome(jour, round(chome, 2), j.get("annee"), j.get("mois")))
    return resultat


def dans_la_periode(
    jours: Iterable[dict[str, Any]], debut: date, fin: date, *, annee: int, mois: int
) -> list[dict[str, Any]]:
    """Les jours du calendrier entre `debut` et `fin` (un jour sans `annee` ni
    `mois` est du mois `annee/mois`)."""
    gardes = []
    for j in jours:
        if not j.get("jour"):
            continue
        try:
            quand = date(int(j.get("annee") or annee), int(j.get("mois") or mois), int(j["jour"]))
        except (TypeError, ValueError):
            continue
        if debut <= quand <= fin:
            gardes.append(j)
    return gardes


def heures_chomees(jours: Iterable[JourChome]) -> float:
    return round(sum(j.heures for j in jours), 2)
