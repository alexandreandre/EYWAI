"""Carence payée une fois par an : quels jours de carence l'employeur paie.

Règle des sociétés de la plasturgie (Colorplast, Comitech Composite, Mont Blanc
Composite ; Gaëlle, 28/09/2026) : l'employeur paie les jours de carence d'un
arrêt maladie dans la limite d'un crédit annuel (3 jours), si le salarié a un
an d'ancienneté. Le crédit se consomme jour par jour — un arrêt de 2 jours en
prend 2, il en reste 1 pour l'arrêt suivant — et repart à zéro en janvier.

Les jours de carence sont les 3 premiers jours calendaires de l'arrêt (carence
de la Sécurité sociale) ; seuls ceux qui tombent un jour ouvré sont payés, et
seuls ceux-là consomment le crédit. Une prolongation (arrêt qui commence au
plus tard le lendemain de la fin du précédent) n'a pas de nouvelle carence.
Les accidents du travail, maladies professionnelles et congés de parentalité
n'ont pas de carence et ne touchent pas au crédit.

Le crédit se lit sur tous les arrêts de l'année, dans l'ordre : ceux de janvier
à juillet de Colorplast viennent des calendriers repris, pas de l'écran des
absences.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

#: Jours de carence de la Sécurité sociale pour une maladie.
JOURS_DE_CARENCE = 3


@dataclass(frozen=True)
class ArretDeLAnnee:
    debut: date
    fin: date
    type_arret: str


def _est_une_maladie(type_arret: str) -> bool:
    t = (type_arret or "").lower()
    if "pro" in t or "accident" in t or "trajet" in t or t in ("at", "at_mp", "mp"):
        return False
    if "matern" in t or "patern" in t or "adoption" in t:
        return False
    return "maladie" in t or t in ("ald", "")


def _mois_d_anciennete(date_entree: date, jour: date) -> int:
    mois = (jour.year - date_entree.year) * 12 + (jour.month - date_entree.month)
    if jour.day < date_entree.day:
        mois -= 1
    return mois


def jours_de_carence_payes(
    arrets: list[ArretDeLAnnee],
    *,
    jours_par_an: int,
    date_entree: date | None,
    anciennete_min_mois: int,
) -> dict[ArretDeLAnnee, list[date]]:
    """Pour chaque arrêt, les jours de carence payés par l'employeur."""
    credits: dict[int, int] = {}
    payes: dict[ArretDeLAnnee, list[date]] = {}
    fin_precedente: date | None = None
    for arret in sorted(set(arrets), key=lambda a: (a.debut, a.fin)):
        prolongation = fin_precedente is not None and arret.debut <= fin_precedente + timedelta(days=1)
        fin_precedente = max(fin_precedente or arret.fin, arret.fin)
        payes[arret] = []
        if prolongation or jours_par_an <= 0 or not _est_une_maladie(arret.type_arret):
            continue
        if date_entree is not None and _mois_d_anciennete(date_entree, arret.debut) < anciennete_min_mois:
            continue
        credit = credits.setdefault(arret.debut.year, jours_par_an)
        for k in range(JOURS_DE_CARENCE):
            jour = arret.debut + timedelta(days=k)
            if jour > arret.fin or credit <= 0:
                break
            if jour.weekday() < 5:
                payes[arret].append(jour)
                credit -= 1
        credits[arret.debut.year] = credit
    return payes
