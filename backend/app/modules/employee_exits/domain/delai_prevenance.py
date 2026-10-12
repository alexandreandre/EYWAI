"""Délai de prévenance d'une rupture de période d'essai.

Code du travail (Légifrance, ouverts le 11/10/2026) :
- art. L1221-25 (version en vigueur depuis le 28/06/2014) : rupture par
  l'employeur, le salarié « est prévenu dans un délai qui ne peut être
  inférieur à : 1° Vingt-quatre heures en deçà de huit jours de présence ;
  2° Quarante-huit heures entre huit jours et un mois de présence ; 3° Deux
  semaines après un mois de présence ; 4° Un mois après trois mois de
  présence. » ; « La période d'essai, renouvellement inclus, ne peut être
  prolongée du fait de la durée du délai de prévenance. » ; s'il n'est pas
  respecté, une indemnité compensatrice égale aux salaires et avantages que le
  salarié aurait perçus jusqu'à l'expiration du délai, « indemnité
  compensatrice de congés payés comprise », sauf faute grave.
- art. L1221-26 (version en vigueur depuis le 27/06/2008) : rupture par le
  salarié, « un délai de prévenance de quarante-huit heures. Ce délai est
  ramené à vingt-quatre heures si la durée de présence du salarié dans
  l'entreprise est inférieure à huit jours. »

Conventions de calcul (les textes ne les fixent pas) : la présence se compte
en jours civils, du jour d'entrée au jour de la notification compris ; un mois
de présence est atteint la veille du quantième du mois suivant ; 24 heures font
un jour, 48 heures deux, deux semaines quatorze, un mois va de quantième à
quantième. Le délai court du jour de la notification : le contrat peut prendre
fin le jour où il expire.

Module pur : aucune lecture, aucune écriture.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from dateutil.relativedelta import relativedelta

Initiative = Literal["employer", "employee"]


@dataclass(frozen=True)
class DelaiDePrevenance:
    initiative: str
    notification: date
    jours_de_presence: int
    #: Durée du délai en jours civils.
    jours: int
    libelle: str
    article: str
    #: Jour où le délai expire.
    fin: date

    def jours_accordes(self, dernier_jour: date) -> int:
        return max(0, (dernier_jour - self.notification).days)

    def jours_non_respectes(self, dernier_jour: date) -> int:
        return max(0, (self.fin - dernier_jour).days)

    def respecte(self, dernier_jour: date) -> bool:
        return self.jours_non_respectes(dernier_jour) == 0


def _mois_de_presence(entree: date, notification: date) -> int:
    ecart = relativedelta(notification + timedelta(days=1), entree)
    return max(0, ecart.years * 12 + ecart.months)


def delai_de_prevenance(initiative: str, entree: date, notification: date) -> DelaiDePrevenance:
    """Le délai légal minimum selon qui rompt et le temps de présence à la notification."""
    presence = max(0, (notification - entree).days + 1)
    mois = _mois_de_presence(entree, notification)
    if initiative == "employer":
        if presence < 8:
            jours, libelle, article = 1, "24 heures", "L1221-25, 1°"
        elif mois < 1:
            jours, libelle, article = 2, "48 heures", "L1221-25, 2°"
        elif mois < 3:
            jours, libelle, article = 14, "2 semaines", "L1221-25, 3°"
        else:
            jours = ((notification + relativedelta(months=1)) - notification).days
            libelle, article = "1 mois", "L1221-25, 4°"
    else:
        if presence < 8:
            jours, libelle = 1, "24 heures"
        else:
            jours, libelle = 2, "48 heures"
        article = "L1221-26"
    return DelaiDePrevenance(
        initiative=initiative,
        notification=notification,
        jours_de_presence=presence,
        jours=jours,
        libelle=libelle,
        article=article,
        fin=notification + timedelta(days=jours),
    )
