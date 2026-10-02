"""Heures dues sur un mois d'entrée ou de sortie : l'horaire du salarié, jour par jour.

Un mois incomplet se paie sur l'horaire du salarié : la somme des heures que
son planning prévoit les jours couverts par le contrat. C'est ce que fait
Quadra (septembre 2026 : CDD sorti le mardi 15/09 sur l'horaire 8,5 h du lundi
au jeudi et 5 h le vendredi, 86,50 h payées = la somme du planning du 1er au
15 ; entrée le lundi 28/09 sur l'horaire d'hiver 8,5/8,5/8/8,5/5,5, 25,00 h =
lundi + mardi + mercredi). Le prorata en jours ouvrés (7,80 h par jour sur un
39 h) donnait 85,80 h et 23,40 h.

Deux garde-fous, parce que le planning n'est pas toujours celui du contrat :

- le planning ne sert que si son horaire de la semaine fait la durée du
  contrat (un 35 h planifié à 7,8 h par jour, un 14 h planifié à temps plein
  gardent le prorata en jours ouvrés) ;
- un jour sous contrat qui n'est pas « travail » au planning (congé payé ou
  férié posé à 0 h, arrêt, semaine laissée en « repos ») compte pour l'horaire
  de son jour de semaine : dans un mois plein il serait payé puis, s'il le
  faut, retiré par sa propre ligne d'absence. Sans cela, un congé serait
  retiré deux fois.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from typing import Any

DUREE_LEGALE_HEBDO = 35.0
#: Écart toléré entre l'horaire de la semaine et la durée du contrat.
TOLERANCE_HEURES = 0.01


def _date_du_jour(jour: Mapping[str, Any]) -> date | None:
    try:
        return date(int(jour["annee"]), int(jour["mois"]), int(jour["jour"]))
    except (KeyError, TypeError, ValueError):
        return None


def _heures(jour: Mapping[str, Any]) -> float:
    try:
        return float(jour.get("heures_prevues") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _distance(jour: date, debut: date, fin: date) -> int:
    if jour < debut:
        return (debut - jour).days
    if jour > fin:
        return (jour - fin).days
    return 0


def heures_prevues_sous_contrat(
    jours_prevus: Iterable[Mapping[str, Any]],
    debut: date,
    fin: date,
    duree_hebdo: float,
) -> float | None:
    """Heures prévues du `debut` au `fin` inclus (jours sous contrat du mois).

    `jours_prevus` : jours du planning (`annee`, `mois`, `jour`, `type`,
    `heures_prevues`), idéalement le mois et ses deux voisins — l'horaire
    d'une entrée le 28 se lit sur le mois suivant.

    `None` quand le planning ne permet pas de conclure (pas d'horaire, ou un
    horaire de semaine qui ne fait pas la durée du contrat) : l'appelant garde
    alors le prorata en jours ouvrés.
    """
    if fin < debut:
        return None
    travailles: dict[date, float] = {}
    for jour in jours_prevus:
        quand = _date_du_jour(jour)
        if quand is None:
            continue
        heures = _heures(jour)
        if jour.get("type") == "travail" and heures > 0:
            travailles[quand] = heures
    if not travailles:
        return None

    # L'horaire de la semaine : pour chaque jour de semaine, le jour travaillé
    # le plus proche de la période (dans la période d'abord, le plus tôt à
    # distance égale).
    horaire: dict[int, float] = {}
    for jour_semaine in range(7):
        candidats = [
            (_distance(quand, debut, fin), quand)
            for quand in travailles
            if quand.weekday() == jour_semaine
        ]
        if candidats:
            horaire[jour_semaine] = travailles[min(candidats)[1]]
    if abs(sum(horaire.values()) - float(duree_hebdo)) > TOLERANCE_HEURES:
        return None

    total = 0.0
    quand = debut
    while quand <= fin:
        total += travailles.get(quand, horaire.get(quand.weekday(), 0.0))
        quand += timedelta(days=1)
    return round(total, 2)


def repartir_heures_du_contrat(total: float, duree_hebdo: float) -> tuple[float, float]:
    """(heures de base, heures sup structurelles) d'un total d'heures du contrat.

    Au-delà de 35 h, la part structurelle vaut total × (durée − 35) / durée,
    tronquée au centième comme Quadra (25,50 h sur un 39 h : 2,61 et non
    2,62) ; la base est le reste.
    """
    total_d = Decimal(str(round(float(total), 2)))
    duree_d = Decimal(str(float(duree_hebdo)))
    legale_d = Decimal(str(DUREE_LEGALE_HEBDO))
    if duree_d <= legale_d or duree_d <= 0:
        return float(total_d), 0.0
    heures_sup = (total_d * (duree_d - legale_d) / duree_d).quantize(
        Decimal("0.01"), rounding=ROUND_DOWN
    )
    base = (total_d - heures_sup).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return float(base), float(heures_sup)
