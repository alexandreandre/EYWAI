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


def _un_an_avant(jour: date) -> date:
    try:
        return jour.replace(year=jour.year - 1)
    except ValueError:  # 29 février
        return jour.replace(year=jour.year - 1, day=28)


def _mois_entre(debut: date, fin: date) -> int:
    return (fin.year - debut.year) * 12 + fin.month - debut.month - (fin.day < debut.day)


def jours_legaux_des_12_mois(
    debut_arret: date,
    arrets_connus: Iterable[Mapping[str, Any]] | None,
    *,
    carence_maladie: int,
    plafond: int,
    date_anciennete: date | None = None,
    min_mois: int = 0,
) -> int:
    """Jours de maintien légal déjà indemnisés dans les douze mois avant cet arrêt (D1226-4).

    Maladie et accidents, pas la parentalité. La carence court au début de chaque arrêt
    (prolongations groupées), sauf accident du travail et maladie professionnelle. Sans
    l'ancienneté requise à l'époque, l'arrêt n'avait ouvert aucun maintien.
    """
    limite = _un_an_avant(debut_arret)
    connus: list[tuple[date, date, str]] = []
    for autre in arrets_connus or []:
        d = _date((autre or {}).get("debut"))
        f = _date((autre or {}).get("fin")) or d
        type_arret = str((autre or {}).get("type") or "")
        if d is None or f is None or d >= debut_arret or famille_d_arret(type_arret) == "parentalite":
            continue
        connus.append((d, min(f, debut_arret - timedelta(days=1)), type_arret))
    connus.sort()

    chaines: list[list[tuple[date, date, str]]] = []
    for arret in connus:
        derniere = chaines[-1] if chaines else None
        if (
            derniere
            and famille_d_arret(derniere[0][2]) == famille_d_arret(arret[2])
            and (arret[0] - max(a[1] for a in derniere)).days <= ECART_MAX_PROLONGATION_JOURS
        ):
            derniere.append(arret)
        else:
            chaines.append([arret])

    total = 0
    for chaine in chaines:
        debut_chaine, type_arret = chaine[0][0], chaine[0][2]
        if date_anciennete is not None and _mois_entre(date_anciennete, debut_chaine) < min_mois:
            continue
        sans_carence = famille_d_arret(type_arret) == "at_mp" and type_arret != "accident_trajet"
        premier_indemnise = debut_chaine + timedelta(days=0 if sans_carence else carence_maladie)
        jours: set[date] = set()
        for d, f, _ in chaine:
            jour = d
            while jour <= f:
                if jour >= premier_indemnise and jour >= limite:
                    jours.add(jour)
                jour += timedelta(days=1)
        total += len(jours)
    return min(total, plafond)


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
    "jours_legaux_des_12_mois",
]
