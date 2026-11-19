"""Heure de début et de fin d'un jour pointé, gardées au calendrier réel.

Retour d'Elsa du 17/11/2026 : les paniers et primes d'équipe des usines
dépendent de l'heure de prise de poste (« panier si le poste commence à 4 h ou
12 h », « heures de nuit de 22 h à 6 h »). Les relevés importés portent bien
les badgeages de chaque jour (Mont Blanc, LEWIS, Cartol), mais seul le total
d'heures était gardé.

Un jour réel peut donc porter `debut` et `fin` (« HH:MM ») : la première entrée
et la dernière sortie lues sur le relevé. Ce sont des informations : elles ne
changent ni les heures faites ni le bulletin. Seules les règles de variables
qui les demandent les lisent.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from app.modules.schedules.domain.punch_accounting_rules import parse_hhmm_value

TYPES_TRAVAILLES = {"travail", "travaille", "work", ""}


def en_hhmm(valeur: object) -> str | None:
    """800, « 8:00 », « 08h00 » → « 08:00 » ; illisible → None."""
    minutes = parse_hhmm_value(valeur)
    if minutes is None:
        return None
    h, m = divmod(minutes, 60)
    return f"{h:02d}:{m:02d}"


def en_minutes(valeur: object) -> int | None:
    """« 04:15 » → 255 minutes depuis minuit."""
    return parse_hhmm_value(valeur)


def _type_travaille(entree: Mapping[str, Any]) -> bool:
    return str(entree.get("type") or "").strip().lower() in TYPES_TRAVAILLES


def horaires_de_l_entree(entree: Mapping[str, Any]) -> dict[str, str]:
    """`{debut, fin}` d'un jour proposé à l'import (seulement ce qui est lisible).

    Un relevé de badges (tableur) porte `punch_entry_raw` / `punch_exit_raw` ;
    les relevés PDF (Cegid, banque d'heures) portent `heure_debut` /
    `heure_fin`. Un jour qui n'est pas travaillé n'a pas d'horaire.
    """
    if not _type_travaille(entree):
        return {}
    debut = en_hhmm(entree.get("heure_debut")) or en_hhmm(entree.get("punch_entry_raw"))
    fin = en_hhmm(entree.get("heure_fin")) or en_hhmm(entree.get("punch_exit_raw"))
    out: dict[str, str] = {}
    if debut:
        out["debut"] = debut
    if fin:
        out["fin"] = fin
    return out


def _heures(valeur: Any) -> float | None:
    if valeur is None or valeur == "":
        return None
    try:
        return round(float(valeur), 2)
    except (TypeError, ValueError):
        return None


def garder_les_horaires(
    entrant: Iterable[Mapping[str, Any]], stocke: Iterable[Mapping[str, Any]] | None
) -> list[dict[str, Any]]:
    """Le calendrier réel enregistré à l'écran, avec les horaires pointés gardés.

    L'écran ne connaît pas `debut`/`fin` et renvoie les jours sans eux : un
    simple enregistrement les effaçait. Ils restent quand le jour n'a pas
    changé (même type travaillé, mêmes heures faites) ; un jour modifié à la
    main les perd, car ils ne décriraient plus la journée.
    """
    par_jour: dict[Any, Mapping[str, Any]] = {}
    for e in stocke or []:
        if isinstance(e, Mapping) and e.get("jour") is not None and e.get("debut"):
            par_jour[e.get("jour")] = e
    out: list[dict[str, Any]] = []
    for e in entrant:
        jour = dict(e)
        ancien = par_jour.get(jour.get("jour"))
        if (
            ancien is not None
            and not jour.get("debut")
            and _type_travaille(jour)
            and str(jour.get("type") or "").lower() == str(ancien.get("type") or "").lower()
            and _heures(jour.get("heures_faites")) == _heures(ancien.get("heures_faites"))
        ):
            jour["debut"] = ancien["debut"]
            if ancien.get("fin"):
                jour["fin"] = ancien["fin"]
        out.append(jour)
    return out


def debut_dans_les_plages(debut: object, plages: Iterable[Mapping[str, Any]] | None) -> bool:
    """Le poste commence-t-il dans une des plages `{de, a}` (bornes comprises) ?

    Une plage qui passe minuit (de 21:30 à 00:30) est acceptée.
    """
    minute = en_minutes(debut)
    if minute is None:
        return False
    for plage in plages or []:
        if not isinstance(plage, Mapping):
            continue
        de, a = en_minutes(plage.get("de")), en_minutes(plage.get("a"))
        if de is None or a is None:
            continue
        if de <= a:
            if de <= minute <= a:
                return True
        elif minute >= de or minute <= a:
            return True
    return False


def minutes_dans_la_nuit(debut: object, fin: object, nuit_de: object = "22:00", nuit_a: object = "06:00") -> int:
    """Minutes du poste [debut, fin] tombées dans la plage de nuit.

    Un poste dont la fin précède le début finit le lendemain (22:00 → 05:00).
    Les pauses ne sont pas connues ici : c'est l'amplitude du poste.
    """
    d, f = en_minutes(debut), en_minutes(fin)
    n_de, n_a = en_minutes(nuit_de), en_minutes(nuit_a)
    if d is None or f is None or n_de is None or n_a is None:
        return 0
    if f <= d:
        f += 24 * 60
    # Plages de nuit sur deux jours : [n_de - 24 h, n_a], [n_de, n_a + 24 h], …
    plages: list[tuple[int, int]] = []
    for decalage in (-24 * 60, 0, 24 * 60):
        if n_de > n_a:
            plages.append((n_de + decalage, n_a + 24 * 60 + decalage))
        else:
            plages.append((n_de + decalage, n_a + decalage))
    total = 0
    for p_de, p_a in plages:
        total += max(0, min(f, p_a) - max(d, p_de))
    return total
