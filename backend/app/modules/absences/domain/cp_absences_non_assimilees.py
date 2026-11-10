"""Congés payés : les absences non assimilées à du travail effectif — domaine pur.

Code du travail (lus sur code.travail.gouv.fr le 10/11/2026) :
- L3141-3 : « Le salarié a droit à un congé de deux jours et demi ouvrables par
  mois de travail effectif chez le même employeur. » ;
- L3141-4 : « Sont assimilées à un mois de travail effectif pour la
  détermination de la durée du congé les périodes équivalentes à quatre
  semaines ou vingt-quatre jours de travail. » ;
- L3141-5 : liste des périodes « considérées comme périodes de travail
  effectif » (congé payé, maternité/paternité/adoption, repos compensateurs,
  jours de repos d'un accord, AT/MP, service national, arrêt maladie non
  professionnel, mandat électif local). L'absence injustifiée et le congé sans
  solde n'y figurent pas : ils n'ouvrent aucun droit.

Règle retenue, mois civil par mois civil : un mois où le salarié a travaillé
au moins quatre semaines compte entier ; en deçà, il ne compte qu'au prorata
des jours travaillés. Quatre semaines d'un horaire sur cinq jours font 20 jours
ouvrés : la part travaillée d'un mois est (jours ouvrés du mois dans le
contrat − jours d'absence non assimilée) / 20, plafonnée à la part du mois déjà
créditée (mois entier, ou part du mois d'entrée ou de sortie). Le samedi n'est
pas compté : un salarié absent tout le mois ne « travaille » pas ses samedis
non planifiés.

Sources des jours : le planning (« Absence non rémunérée », que le congé sans
solde validé écrit aussi) et les demandes de congé sans solde validées. Les
jours jusqu'à une reprise de soldes sont dans le solde repris du cabinet : ils
ne retirent rien.
"""

from __future__ import annotations

import calendar
from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from typing import Any

#: Quatre semaines de cinq jours (C. trav. L3141-4).
JOURS_OUVRES_D_UN_MOIS_DE_TRAVAIL = 20

#: Types de demande d'absence non assimilés à du travail effectif.
TYPES_DE_DEMANDE_NON_ASSIMILES: frozenset[str] = frozenset({"sans_solde"})

#: Types de jour du planning non assimilés à du travail effectif.
TYPES_DE_PLANNING_NON_ASSIMILES: frozenset[str] = frozenset({"absence_non_remuneree"})


def _jour(valeur: Any) -> date | None:
    if isinstance(valeur, date):
        return valeur
    try:
        return date.fromisoformat(str(valeur)[:10])
    except ValueError:
        return None


def jours_non_assimiles_des_demandes(
    demandes: Iterable[Mapping[str, Any]],
) -> frozenset[date]:
    """Les jours des congés sans solde validés."""
    jours: set[date] = set()
    for demande in demandes or ():
        if str(demande.get("status") or "validated") != "validated":
            continue
        if demande.get("type") not in TYPES_DE_DEMANDE_NON_ASSIMILES:
            continue
        for valeur in demande.get("selected_days") or []:
            jour = _jour(valeur)
            if jour is not None:
                jours.add(jour)
    return frozenset(jours)


def jours_non_assimiles_du_planning(
    lignes: Iterable[Mapping[str, Any]],
) -> frozenset[date]:
    """Les jours « Absence non rémunérée » du planning prévu.

    `lignes` : des lignes `employee_schedules` (`year`, `month`,
    `planned_calendar`)."""
    jours: set[date] = set()
    for ligne in lignes or ():
        try:
            annee, mois = int(ligne["year"]), int(ligne["month"])
        except (KeyError, TypeError, ValueError):
            continue
        calendrier = (ligne.get("planned_calendar") or {}).get("calendrier_prevu") or []
        for jour_prevu in calendrier:
            if not isinstance(jour_prevu, Mapping):
                continue
            if jour_prevu.get("type") not in TYPES_DE_PLANNING_NON_ASSIMILES:
                continue
            try:
                jours.add(date(annee, mois, int(jour_prevu.get("jour"))))
            except (TypeError, ValueError):
                continue
    return frozenset(jours)


def _jours_ouvres(debut: date, fin: date) -> list[date]:
    jours = []
    jour = debut
    while jour <= fin:
        if jour.weekday() < 5:
            jours.append(jour)
        jour += timedelta(days=1)
    return jours


def mois_perdus_par_absences(
    jours: Iterable[date],
    *,
    debut: date,
    fin: date,
    reprise_au: date | None = None,
    fraction_du_mois: Mapping[tuple[int, int], float] | None = None,
) -> float:
    """Mois d'acquisition perdus par les absences non assimilées de `debut` à `fin`.

    `debut` : l'entrée ou l'ouverture de la période ; `fin` : la date de
    l'acquis (fin du mois du bulletin, ou sortie). `fraction_du_mois` : la part
    déjà créditée d'un mois (mois d'entrée ou de sortie), 1 par défaut."""
    retenus = sorted(
        j
        for j in frozenset(jours)
        if debut <= j <= fin
        and j.weekday() < 5
        and (reprise_au is None or j > reprise_au)
    )
    if not retenus:
        return 0.0
    par_mois: dict[tuple[int, int], int] = {}
    for jour in retenus:
        cle = (jour.year, jour.month)
        par_mois[cle] = par_mois.get(cle, 0) + 1
    perte = 0.0
    for (annee, mois), absents in par_mois.items():
        premier = max(debut, date(annee, mois, 1))
        dernier = min(fin, date(annee, mois, calendar.monthrange(annee, mois)[1]))
        ouvres = len(_jours_ouvres(premier, dernier))
        credite = min(1.0, float((fraction_du_mois or {}).get((annee, mois), 1.0)))
        travaille = max(0, ouvres - absents) / JOURS_OUVRES_D_UN_MOIS_DE_TRAVAIL
        perte += max(0.0, credite - min(credite, travaille))
    return perte


__all__ = [
    "JOURS_OUVRES_D_UN_MOIS_DE_TRAVAIL",
    "TYPES_DE_DEMANDE_NON_ASSIMILES",
    "TYPES_DE_PLANNING_NON_ASSIMILES",
    "jours_non_assimiles_des_demandes",
    "jours_non_assimiles_du_planning",
    "mois_perdus_par_absences",
]
