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
de début (badge oublié) prend le poste des autres jours badgés de sa semaine
(deux au moins, dans la fenêtre) quand ils sont tous au même poste (retour d'Alexandre, 21/11 : 236 jours sur
390 en octobre, aucun ne contredit sa semaine) ; sinon il ne compte pas et il
est compté à part, pour le dire à la RH.

Seul un jour prévu travaillé reprend le poste de sa semaine : un week-end, un
férié, un jour non planifié avec des heures et sans heure d'arrivée ne le
reprend jamais (un dimanche saisi par erreur comptait un panier en trop,
LEWIS, octobre 2026) ; il est compté à part, comme un jour que la semaine ne
tranche pas.
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


def jour_prevu_travaille(p: Mapping[str, Any] | None) -> bool:
    """Un jour « travail » du prévu, avec des heures prévues."""
    p = p or {}
    return str(p.get("type") or "").lower() in TYPES_TRAVAIL and (_heures(p.get("heures_prevues")) or 0.0) > 0


def _poste(debut: Any, plages: list[Mapping[str, Any]]) -> int | None:
    """Rang de la plage où le poste commence, None hors de toute plage."""
    for i, plage in enumerate(plages):
        if debut_dans_les_plages(debut, [plage]):
            return i
    return None


BADGES_MIN_PAR_SEMAINE = 2


def postes_par_semaine(
    reel: Mapping[date, Mapping[str, Any]],
    plages: list[Mapping[str, Any]],
    debut: date,
    fin: date,
    seuil: float = 0.0,
) -> dict[tuple[int, int], set[int | None]]:
    """Le poste de chaque semaine (ISO) quand elle en a un seul, lu sur au moins
    deux jours badgés de la fenêtre qui comptent eux-mêmes (seuil d'heures).

    Un seul badge ne suffit pas à trancher une semaine (une formation à 8 h
    ferait perdre les paniers des postes de 4 h) ; les badges hors fenêtre
    (autre contrat, mois suivant) ne tranchent rien."""
    vus: dict[tuple[int, int], list[int | None]] = {}
    for jour, r in reel.items():
        if not isinstance(jour, date) or not (debut <= jour <= fin) or not (r or {}).get("debut"):
            continue
        faites = _heures(r.get("heures_faites"))
        if faites is not None and (faites <= 0 or faites < seuil):
            continue
        vus.setdefault(jour.isocalendar()[:2], []).append(_poste(r.get("debut"), plages))
    return {sem: set(p) for sem, p in vus.items() if len(p) >= BADGES_MIN_PAR_SEMAINE}


def detail_jours_travailles(
    prevu: Mapping[date, Mapping[str, Any]],
    reel: Mapping[date, Mapping[str, Any]],
    jours_absence: set[date],
    debut: date,
    fin: date,
    min_heures: float | None = None,
    plages_debut: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """`{jours, sans_heure_de_debut, dates_sans_heure_de_debut, dates,
    repris_de_la_semaine, aucun_badge}` : les jours qui comptent ; si des plages
    de début sont demandées, les jours travaillés sans heure lue que leur semaine
    ne tranche pas (ou hors du prévu), et ceux qu'elle a tranchés."""
    seuil = float(min_heures) if min_heures else 0.0
    plages = [p for p in (plages_debut or []) if isinstance(p, Mapping)]
    n = 0
    sans_debut = 0
    dates_sans_debut: list[str] = []
    dates: list[str] = []
    repris: list[str] = []
    semaines = postes_par_semaine(reel, plages, debut, fin, seuil) if plages else {}
    jour = debut
    while jour <= fin:
        r = reel.get(jour) or {}
        heures = heures_du_jour(prevu.get(jour), r, jour in jours_absence)
        if heures > 0 and heures >= seuil:
            if not plages:
                n += 1
                dates.append(jour.isoformat())
            elif not r.get("debut"):
                # Hors du prévu (week-end, férié, jour non planifié) : la
                # semaine ne tranche jamais.
                postes = (
                    semaines.get(jour.isocalendar()[:2]) or set()
                    if jour_prevu_travaille(prevu.get(jour))
                    else set()
                )
                if len(postes) != 1:
                    sans_debut += 1
                    dates_sans_debut.append(jour.isoformat())
                else:
                    repris.append(jour.isoformat())
                    if next(iter(postes)) is not None:
                        n += 1
                        dates.append(jour.isoformat())
            elif debut_dans_les_plages(r.get("debut"), plages):
                n += 1
                dates.append(jour.isoformat())
        jour += timedelta(days=1)
    return {
        "jours": n,
        "sans_heure_de_debut": sans_debut,
        "dates_sans_heure_de_debut": dates_sans_debut,
        "dates": dates,
        "repris_de_la_semaine": repris,
        # Aucun badge de toute la fenêtre : relevé absent ou salarié hors
        # badgeuse ; une seule alerte plutôt qu'un jour par jour.
        "aucun_badge": bool(plages) and sans_debut > 0 and not any(
            debut <= j <= fin and (r or {}).get("debut") for j, r in reel.items() if isinstance(j, date)
        ),
    }


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
