"""Les jours du planning postérieurs à la sortie : écartés du bulletin, et dits.

Retour de la réunion du 10/11/2026 : le planning se pré-remplit au-delà du
dernier jour du contrat (modèle hebdomadaire, copie du mois précédent). Aucun
de ces jours ne doit être payé ni compté : le contrat a pris fin, il n'y a ni
travail, ni absence, ni arrêt à rémunérer. Le moteur écartait déjà les
événements datés après la sortie (`calcul_brut`), mais l'analyse des horaires,
la compensation entre semaines et les contrôles lisaient encore ces jours. On
les retire ici, une fois, à l'entrée du calcul, et le bulletin le dit quand il
en trouve dans sa période.
"""

from __future__ import annotations

import calendar
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from typing import Any

CODE_ALERTE_PLANNING_APRES_SORTIE = "planning_apres_sortie_ecarte"

#: Jours qui ne portent rien : leur présence au planning n'est pas à signaler.
_TYPES_SANS_CONTENU = frozenset({"repos", "ferie", ""})


def date_de_sortie(valeur: Any) -> date | None:
    """Une date ou un texte ISO ; vide ou illisible : None."""
    if isinstance(valeur, datetime):
        return valeur.date()
    if isinstance(valeur, date):
        return valeur
    try:
        return date.fromisoformat(str(valeur or "")[:10])
    except ValueError:
        return None


def _date_du_jour(jour: Mapping[str, Any]) -> date | None:
    try:
        return date(int(jour["annee"]), int(jour["mois"]), int(jour["jour"]))
    except (KeyError, TypeError, ValueError):
        return None


def _porte_quelque_chose(jour: Mapping[str, Any]) -> bool:
    """Un jour qui serait payé, retenu ou compté s'il était dans le contrat."""
    for cle in ("heures_prevues", "heures_faites"):
        try:
            if float(jour.get(cle) or 0) > 0:
                return True
        except (TypeError, ValueError):
            continue
    return str(jour.get("type") or "") not in _TYPES_SANS_CONTENU | {"travail"}


def ecarter_apres_la_sortie(
    prevu: Iterable[Mapping[str, Any]],
    reel: Iterable[Mapping[str, Any]],
    sortie: date | None,
) -> tuple[list[dict], list[dict], list[date]]:
    """Le planning prévu et réel sans les jours postérieurs à `sortie`.

    Renvoie aussi les dates écartées qui portaient quelque chose (heures,
    absence, arrêt…), triées et sans doublon."""
    prevu = [dict(j) for j in prevu]
    reel = [dict(j) for j in reel]
    if sortie is None:
        return prevu, reel, []
    ecartes: set[date] = set()
    gardes: list[list[dict]] = []
    for liste in (prevu, reel):
        garde = []
        for jour in liste:
            quand = _date_du_jour(jour)
            if quand is not None and quand > sortie:
                if _porte_quelque_chose(jour):
                    ecartes.add(quand)
                continue
            garde.append(jour)
        gardes.append(garde)
    return gardes[0], gardes[1], sorted(ecartes)


def _jj_mm(jour: date) -> str:
    return f"{jour.day:02d}/{jour.month:02d}"


def alerte_planning_apres_sortie(
    jours: Iterable[date],
    sortie: date | None,
    annee: int,
    mois: int,
    fin_fenetre: date | None = None,
) -> dict[str, Any] | None:
    """L'alerte du bulletin quand des jours de sa période suivent la sortie.

    La période : le mois civil, prolongée jusqu'à la fin de la fenêtre des
    variables quand elle déborde. Les mois suivants ne sont pas cités : aucun
    bulletin ne viendra les lire."""
    if sortie is None:
        return None
    fin = date(annee, mois, calendar.monthrange(annee, mois)[1])
    if fin_fenetre is not None and fin_fenetre > fin:
        fin = fin_fenetre
    retenus = sorted(j for j in set(jours) if sortie < j <= fin)
    if not retenus:
        return None
    nombre = len(retenus)
    jours_texte = "1 jour" if nombre == 1 else f"{nombre} jours"
    etendue = (
        f"le {_jj_mm(retenus[0])}"
        if nombre == 1
        else f"du {_jj_mm(retenus[0])} au {_jj_mm(retenus[-1])}"
    )
    return {
        "code": CODE_ALERTE_PLANNING_APRES_SORTIE,
        "severity": "warning",
        "critique": False,
        "message": (
            f"Départ le {sortie:%d/%m/%Y} : le planning porte encore {jours_texte} "
            f"après cette date ({etendue}). "
            + (
                "Il est écarté de ce bulletin : rien n'est payé, retenu ni compté."
                if nombre == 1
                else "Ils sont écartés de ce bulletin : aucun n'est payé, retenu ni compté."
            )
        ),
        "jours": [j.isoformat() for j in retenus],
    }


__all__ = [
    "CODE_ALERTE_PLANNING_APRES_SORTIE",
    "alerte_planning_apres_sortie",
    "date_de_sortie",
    "ecarter_apres_la_sortie",
]
