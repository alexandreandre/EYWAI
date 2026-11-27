"""Vider le calendrier d'un mois — règles pures (retour d'Elsa, 27/11).

« Un gros bouton rouge pour annuler un modèle appliqué par erreur. » Vider
remet chaque jour du mois à vide, au prévu comme au réel : il redevient « à
saisir ». Deux sortes de jours restent tels quels, et sont comptés pour être
dits à l'écran :

- les arrêts, congés et absences posés (type d'absence au planning, jour issu
  d'une absence validée, ou jour couvert par une demande validée — un week-end
  d'arrêt garde son type) : ils se retirent là où ils se posent, sinon la
  demande validée et le planning se contrediraient ;
- les jours lus par un bulletin validé (ou repris de l'ancien logiciel) : le
  bulletin est un fait, le calendrier qui l'a produit ne change pas sous lui.

Module pur : l'appelant fournit le calendrier stocké et les jours protégés.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Iterable, Mapping

from app.shared.domain.absence_calendar import ABSENCE_CALENDAR_TYPES, ORIGINE_ABSENCE

#: Types que le vidage ne touche jamais (même liste que l'écran,
#: `frontend/src/lib/viderCalendrier.ts`).
TYPES_GARDES: frozenset[str] = ABSENCE_CALENDAR_TYPES | {"activite_partielle"}


@dataclass(frozen=True)
class PlanDeVidage:
    jours_vides: tuple[int, ...]
    jours_gardes_absence: tuple[int, ...]
    jours_gardes_bulletin: tuple[int, ...]
    #: Entrées du prévu à écrire (seulement les jours vidés : la fusion du
    #: serveur garde les autres tels quels).
    calendrier_prevu: list[dict[str, Any]]
    #: Le réel complet à écrire (il remplace le mois) : jours vidés remis à
    #: vide, les autres tels qu'ils sont stockés.
    calendrier_reel: list[dict[str, Any]]


def _par_jour(entrees: Iterable[Mapping[str, Any]] | None) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for e in entrees or []:
        if not isinstance(e, Mapping):
            continue
        try:
            jour = int(e.get("jour"))
        except (TypeError, ValueError):
            continue
        out[jour] = dict(e)
    return out


def _type_du_jour_vide(annee: int, mois: int, jour: int, prevu: Mapping[str, Any] | None) -> str:
    if prevu and prevu.get("type") == "ferie":
        return "ferie"
    return "weekend" if date(annee, mois, jour).weekday() >= 5 else "travail"


def _est_absence(prevu: Mapping[str, Any] | None) -> bool:
    if not prevu:
        return False
    return prevu.get("type") in TYPES_GARDES or prevu.get("origine") == ORIGINE_ABSENCE


def _nombre(valeur: Any) -> float | None:
    if valeur is None or valeur == "":
        return None
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def _a_du_contenu(prevu: Mapping[str, Any] | None, reel: Mapping[str, Any] | None) -> bool:
    """Le jour porte-t-il une saisie ? Un week-end ou un férié à 0 h est l'état
    par défaut : il n'est ni vidé ni compté."""
    if reel and (reel.get("debut") or reel.get("fin") or (_nombre(reel.get("heures_faites")) or 0) > 0):
        return True
    type_prevu = str((prevu or {}).get("type") or "")
    prevues = _nombre((prevu or {}).get("heures_prevues"))
    if type_prevu in ("weekend", "ferie"):
        return (prevues or 0) > 0
    if prevu and (prevues is not None or type_prevu not in ("", "travail")):
        return True
    return bool(reel and _nombre(reel.get("heures_faites")) is not None)


def plan_de_vidage(
    annee: int,
    mois: int,
    prevu: Iterable[Mapping[str, Any]] | None,
    reel: Iterable[Mapping[str, Any]] | None,
    *,
    jours_absence_validee: set[int],
    jours_bulletin: set[int],
) -> PlanDeVidage:
    prevu_par_jour = _par_jour(prevu)
    reel_par_jour = _par_jour(reel)
    vides: list[int] = []
    gardes_absence: list[int] = []
    gardes_bulletin: list[int] = []
    prevu_a_ecrire: list[dict[str, Any]] = []
    for jour in range(1, calendar.monthrange(annee, mois)[1] + 1):
        p, r = prevu_par_jour.get(jour), reel_par_jour.get(jour)
        if _est_absence(p) or jour in jours_absence_validee:
            gardes_absence.append(jour)
            continue
        if not _a_du_contenu(p, r):
            continue
        if jour in jours_bulletin:
            gardes_bulletin.append(jour)
            continue
        vides.append(jour)
        prevu_a_ecrire.append(
            {"jour": jour, "type": _type_du_jour_vide(annee, mois, jour, p), "heures_prevues": None}
        )
    vides_set = set(vides)
    reel_a_ecrire: list[dict[str, Any]] = []
    if vides:
        types = {e["jour"]: e["type"] for e in prevu_a_ecrire}
        for jour in sorted(reel_par_jour):
            if jour in vides_set:
                reel_a_ecrire.append({"jour": jour, "type": types[jour], "heures_faites": None})
            else:
                reel_a_ecrire.append(reel_par_jour[jour])
        for jour in vides:
            if jour not in reel_par_jour:
                reel_a_ecrire.append({"jour": jour, "type": types[jour], "heures_faites": None})
        reel_a_ecrire.sort(key=lambda e: int(e["jour"]))
    return PlanDeVidage(
        jours_vides=tuple(vides),
        jours_gardes_absence=tuple(gardes_absence),
        jours_gardes_bulletin=tuple(gardes_bulletin),
        calendrier_prevu=prevu_a_ecrire,
        calendrier_reel=reel_a_ecrire,
    )


def jours_lus_par_les_bulletins(
    annee: int, mois: int, fenetres: Mapping[tuple[int, int], tuple[date, date]]
) -> set[int]:
    """Jours du mois lus par les bulletins donnés : chaque bulletin lit son mois
    civil et sa fenêtre des variables (union, comme le moteur)."""
    premier = date(annee, mois, 1)
    dernier = date(annee, mois, calendar.monthrange(annee, mois)[1])
    jours: set[int] = set()
    for (a, m), (debut, fin) in fenetres.items():
        civil_debut = date(a, m, 1)
        civil_fin = date(a, m, calendar.monthrange(a, m)[1])
        for de, a_ in ((civil_debut, civil_fin), (debut, fin)):
            d = max(de, premier)
            while d <= min(a_, dernier):
                jours.add(d.day)
                d += timedelta(days=1)
    return jours


__all__ = ["PlanDeVidage", "TYPES_GARDES", "jours_lus_par_les_bulletins", "plan_de_vidage"]
