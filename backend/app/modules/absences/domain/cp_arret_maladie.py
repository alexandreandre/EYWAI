"""Congés payés acquis pendant un arrêt maladie ordinaire — domaine pur.

Code du travail (versions lues le 05/11/2026 sur code.travail.gouv.fr) :
- L3141-5 7° : l'arrêt de travail pour accident ou maladie n'ayant pas un
  caractère professionnel compte comme travail effectif pour la durée du congé ;
- L3141-5-1 (loi n° 2024-364 du 22/04/2024) : « par dérogation » à L3141-3, il
  ouvre « deux jours ouvrables par mois, dans la limite d'une attribution, à ce
  titre, de vingt-quatre jours ouvrables par période de référence » ;
- L3141-5 2° et 5° : maternité, paternité, adoption, accident du travail et
  maladie professionnelle restent du travail effectif à taux plein ; la fiche
  service-public « L'absence du salarié est-elle prise en compte pour le calcul
  de ses congés payés ? » (mise à jour le 20/02/2026) y range l'accident de trajet.

Un mois d'arrêt maladie ordinaire acquiert donc les 4/5 d'un mois travaillé
(2 jours sur 2,5 ; 1,67 sur 2,08 en ouvrés). Les arrêts sont des périodes
calendaires : la part d'un mois passée en arrêt est le nombre de ses jours
calendaires d'arrêt rapporté à ses jours calendaires, si bien qu'un mois
entier vaut 1 qu'il ait 28 ou 31 jours. La limite de 24 jours ne peut pas être
atteinte autrement : une période de référence compte 12 mois, 12 × 2 = 24.

Une convention peut assimiler l'arrêt à du travail effectif, dans une limite de
durée (`AssimilationMaladie`) : la métallurgie (IDCC 3248, art. 84) le fait.
"""

from __future__ import annotations

import calendar
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import Any

#: Part du taux normal acquise pendant un arrêt maladie ordinaire (2 / 2,5).
PART_ACQUISE_EN_ARRET_MALADIE = 2.0 / 2.5
#: Ce qu'un mois entier d'arrêt retire au nombre de mois acquis.
PERTE_PAR_MOIS_D_ARRET = 1.0 - PART_ACQUISE_EN_ARRET_MALADIE

NATURE_ARRET_MALADIE = "arret_maladie"

#: Types d'arrêt qui, même saisis sous la nature « Arrêt maladie », ne sont pas
#: une maladie ordinaire : origine professionnelle ou parentalité (anciennes
#: combinaisons, refusées à la saisie depuis), ou mi-temps thérapeutique — le
#: salarié travaille à temps partiel, son contrat n'est pas suspendu.
TYPES_D_ARRET_A_TAUX_PLEIN: frozenset[str] = frozenset(
    {
        "mi_temps_therapeutique",
        "accident_travail",
        "accident_trajet",
        "rechute_at",
        "maladie_professionnelle",
        "maternite",
        "paternite",
        "adoption",
    }
)


def est_arret_maladie_ordinaire(absence: Mapping[str, Any]) -> bool:
    """Vrai pour une demande validée d'arrêt maladie non professionnel.

    La nature décide d'abord : seuls les arrêts « Arrêt maladie » sont
    concernés (maladie simple, ALD, arrêt exceptionnel ; un type absent vaut
    maladie simple, comme au maintien de salaire)."""
    if str(absence.get("status") or "validated") != "validated":
        return False
    if absence.get("type") != NATURE_ARRET_MALADIE:
        return False
    type_arret = str(absence.get("arret_type") or "maladie_simple").strip()
    return type_arret not in TYPES_D_ARRET_A_TAUX_PLEIN


def _jour(valeur: Any) -> date | None:
    if isinstance(valeur, date):
        return valeur
    try:
        return date.fromisoformat(str(valeur)[:10])
    except ValueError:
        return None


def jours_d_arret_maladie_ordinaire(
    absences: Iterable[Mapping[str, Any]],
) -> frozenset[date]:
    """Les jours calendaires d'arrêt maladie ordinaire, sans doublon."""
    jours: set[date] = set()
    for absence in absences:
        if not est_arret_maladie_ordinaire(absence):
            continue
        for valeur in absence.get("selected_days") or []:
            jour = _jour(valeur)
            if jour is not None:
                jours.add(jour)
    return frozenset(jours)


def mois_d_arret(jours: Iterable[date], debut: date, fin: date) -> float:
    """Mois d'arrêt des mois civils de `debut` à `fin`, chacun valant ses jours
    d'arrêt sur ses jours calendaires.

    Le mois de `fin` compte entier, comme il compte entier dans l'acquis
    (`_months_worked_in_period`) : un arrêt connu jusqu'au 30 retire déjà sa
    part le 5 du mois."""
    if fin < debut:
        return 0.0
    premier = (debut.year, debut.month)
    dernier = (fin.year, fin.month)
    par_mois: dict[tuple[int, int], int] = {}
    for jour in jours:
        cle = (jour.year, jour.month)
        if premier <= cle <= dernier:
            par_mois[cle] = par_mois.get(cle, 0) + 1
    return sum(
        min(1.0, n / calendar.monthrange(annee, mois)[1])
        for (annee, mois), n in par_mois.items()
    )


@dataclass(frozen=True)
class AssimilationMaladie:
    """Mois d'arrêt maladie ordinaire qu'une convention compte comme travail
    effectif (taux plein) sur une période de référence, au-delà de la loi.

    `paliers` : (années d'ancienneté révolues à l'ouverture de la période, mois
    assimilés), le plus haut atteint s'applique ; `groupes_sans_condition` :
    groupes d'emplois qui ont `mois_groupes_sans_condition` quelle que soit leur
    ancienneté."""

    paliers: tuple[tuple[int, float], ...]
    groupes_sans_condition: frozenset[str] = field(default_factory=frozenset)
    mois_groupes_sans_condition: float = 0.0
    source: str = ""

    def mois_assimiles(self, *, anciennete_annees: int, groupe: str | None) -> float:
        if groupe and groupe.strip().upper() in self.groupes_sans_condition:
            return self.mois_groupes_sans_condition
        atteints = [mois for seuil, mois in self.paliers if anciennete_annees >= seuil]
        return max(atteints, default=0.0)


#: CCN de la métallurgie du 7 février 2022 (étendue par arrêté du 14/12/2022),
#: art. 84 « Incidence de la maladie ordinaire sur le droit à congés payés »,
#: en vigueur étendu, lu sur Légifrance le 05/11/2026 (KALIARTI000046314573) :
#: « Sans préjudice des dispositions de l'article L. 3141-5 du code du travail,
#: sont considérées comme périodes de travail effectif pour la détermination de
#: la durée du congé les périodes pendant lesquelles le contrat de travail est
#: suspendu pour cause de maladie ou d'accident, dans la limite des durées
#: suivantes » : 2 mois calendaires d'absence (1 an d'ancienneté), 4 (5 ans),
#: 6 (10 ans), 8 (20 ans) ; groupes d'emplois F, G, H ou I : « un an calendaire
#: d'absence, quelle que soit l'ancienneté » ; ancienneté « appréciée à
#: l'ouverture de la période de référence » ; plusieurs absences dans la même
#: période : « la durée d'assimilation cumulée » ne dépasse pas ces durées.
METALLURGIE_3248_ART_84 = AssimilationMaladie(
    paliers=((1, 2.0), (5, 4.0), (10, 6.0), (20, 8.0)),
    groupes_sans_condition=frozenset("FGHI"),
    mois_groupes_sans_condition=12.0,
    source="Convention de la métallurgie (IDCC 3248), art. 84",
)

#: Règle conventionnelle par IDCC — une convention, jamais une filiale. La
#: plasturgie (IDCC 0292, art. 17 des clauses générales) n'assimile que les
#: absences de son article 5 (commissions, mandats) : la loi s'applique.
ASSIMILATION_MALADIE_PAR_IDCC: dict[str, AssimilationMaladie] = {
    "3248": METALLURGIE_3248_ART_84,
}


def assimilation_maladie_de_la_convention(idcc: Any) -> AssimilationMaladie | None:
    """La règle de la convention de cet IDCC, ou None (la loi seule)."""
    cle = str(idcc or "").strip()
    if not cle:
        return None
    return ASSIMILATION_MALADIE_PAR_IDCC.get(cle.zfill(4) if cle.isdigit() else cle)


def mois_d_arret_a_taux_reduit(
    jours: Iterable[date],
    *,
    debut: date,
    fin: date,
    reprise_au: date | None,
    mois_assimiles: float = 0.0,
) -> float:
    """Mois d'arrêt maladie ordinaire acquis à 2 jours sur 2,5, de `debut` à `fin`.

    Les jours jusqu'à la reprise de soldes (`reprise_au`) sont dans le solde
    repris du cabinet : ils ne retirent rien. Ils consomment en revanche, les
    premiers, les mois que la convention assimile à du travail effectif : le
    plafond conventionnel est cumulé sur la période."""
    jours = frozenset(jours)
    if not jours:
        return 0.0
    avant = frozenset(j for j in jours if reprise_au is not None and j <= reprise_au)
    apres = jours - avant
    if not apres:
        return 0.0
    mois_avant = mois_d_arret(avant, debut, fin) if avant else 0.0
    mois_apres = mois_d_arret(apres, debut, fin)
    assimiles_restants = max(0.0, mois_assimiles - mois_avant)
    return max(0.0, mois_apres - assimiles_restants)


def annees_revolues(debut: date, a: date) -> int:
    """Années entières de `debut` à `a` (le 01/06/2023 au 01/06/2024 : 1)."""
    if a < debut:
        return 0
    annees = a.year - debut.year
    if (a.month, a.day) < (debut.month, debut.day):
        annees -= 1
    return max(0, annees)


__all__ = [
    "ASSIMILATION_MALADIE_PAR_IDCC",
    "METALLURGIE_3248_ART_84",
    "PART_ACQUISE_EN_ARRET_MALADIE",
    "PERTE_PAR_MOIS_D_ARRET",
    "AssimilationMaladie",
    "annees_revolues",
    "assimilation_maladie_de_la_convention",
    "est_arret_maladie_ordinaire",
    "jours_d_arret_maladie_ordinaire",
    "mois_d_arret",
    "mois_d_arret_a_taux_reduit",
]
