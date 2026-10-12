"""Prolongation d'arrêt : rattacher une demande à l'arrêt qu'elle prolonge.

Chaque demande validée porte son propre début (`date_debut_arret_reel`). Une
prolongation saisie comme seconde demande n'est pourtant pas un nouvel arrêt :
pas de nouvelle carence, ni de la Sécurité sociale ni de l'employeur, et le
maintien continue à son rang (enquête F, [F11], 10/10/2026).

Règle (service-public F3053, vérifiée le 01/06/2026) : « Il n'y a pas de délai
de carence en cas de reprise d'activité entre 2 arrêts de travail n'ayant pas
dépassé 48 heures. » Une demande prolonge donc un arrêt de même nature qui finit
au plus tard trois jours avant son début (deux jours de reprise au plus), ou
qu'elle recouvre.

La carence payée de la plasturgie (`carence_payee.py`) garde sa propre règle,
apprise avec Gaëlle : prolongation si l'arrêt commence au plus tard le
lendemain du précédent.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Iterable, Mapping

#: Écart maximal entre la fin d'un arrêt et le début de sa prolongation : deux
#: jours de reprise au plus (48 heures).
ECART_MAX_PROLONGATION_JOURS = 3


def _date(valeur: Any) -> date | None:
    if isinstance(valeur, date):
        return valeur
    try:
        return date.fromisoformat(str(valeur)[:10])
    except (TypeError, ValueError):
        return None


def famille_d_arret(arret_type: Any) -> str:
    """Nature de l'arrêt : une prolongation reste dans sa famille."""
    t = str(arret_type or "").strip().lower()
    if t in {"accident_travail", "maladie_professionnelle", "accident_trajet", "rechute_at"}:
        return "at_mp"
    if "matern" in t or "patern" in t or "adoption" in t or "naissance" in t:
        return "parentalite"
    return "maladie"


def chainer_arret(
    debut: date,
    fin: date,
    arret_type: Any,
    arrets_connus: Iterable[Mapping[str, Any]],
) -> tuple[date | None, int]:
    """(début de l'arrêt prolongé, jours d'arrêt déjà passés avant `debut`).

    `arrets_connus` : les autres arrêts du salarié ({debut, fin, type}). Rend
    (None, 0) si la demande ne prolonge aucun arrêt connu.
    """
    famille = famille_d_arret(arret_type)
    candidats: list[tuple[date, date]] = []
    for autre in arrets_connus or []:
        d = _date((autre or {}).get("debut"))
        f = _date((autre or {}).get("fin")) or d
        if d is None or f is None or (d, f) == (debut, fin):
            continue
        if d < debut and famille_d_arret(autre.get("type")) == famille:
            candidats.append((d, f))

    debut_chaine = debut
    chaine: list[tuple[date, date]] = []
    trouve = True
    while trouve:
        trouve = False
        for d, f in candidats:
            if (d, f) in chaine or d >= debut_chaine:
                continue
            if (debut_chaine - f).days <= ECART_MAX_PROLONGATION_JOURS:
                chaine.append((d, f))
                debut_chaine = d
                trouve = True
    if not chaine:
        return None, 0

    jours: set[date] = set()
    for d, f in chaine:
        jour = d
        while jour <= f and jour < debut:
            jours.add(jour)
            jour += timedelta(days=1)
    return debut_chaine, len(jours)


def debut_de_l_arret_prolonge(arret: Mapping[str, Any]) -> date | None:
    """Le début de l'arrêt que prolonge `arret` (le sien s'il n'en prolonge aucun)."""
    debut = _date(arret.get("date_debut"))
    if debut is None:
        return None
    fin = _date(arret.get("date_fin")) or debut
    debut_chaine, _ = chainer_arret(
        debut, fin, arret.get("arret_type"), arret.get("arrets_connus") or []
    )
    return debut_chaine or debut


__all__ = [
    "ECART_MAX_PROLONGATION_JOURS",
    "chainer_arret",
    "debut_de_l_arret_prolonge",
    "famille_d_arret",
]
