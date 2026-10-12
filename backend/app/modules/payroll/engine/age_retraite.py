"""Âges de la retraite : âge légal de départ par génération, mise à la retraite.

Sources ouvertes le 11/10/2026 :
- Code de la sécurité sociale, art. L161-17-2 (Légifrance, rédaction issue de
  la loi n° 2025-1403 du 30 décembre 2025, art. 105) : « fixé à soixante-quatre
  ans pour les assurés nés à compter du 1er janvier 1969 » ; 62 ans et 3 mois
  (nés du 1er septembre au 31 décembre 1961), 62 ans et 6 mois (1962), 62 ans
  et 9 mois (du 1er janvier 1963 au 31 mars 1965), 63 ans (du 1er avril au 31
  décembre 1965), 63 ans et 3 mois (1966), 63 ans et 6 mois (1967), 63 ans et 9
  mois (1968). « Pour les assurés nés avant le 1er septembre 1961, il est celui
  applicable [...] dans sa rédaction antérieure » : rédaction non ouverte ici ;
  ces assurés ont tous plus de 65 ans en 2026, Martine dit « 62 ans au plus »
  sans prétendre à l'exactitude. Ces âges valent pour les pensions prenant
  effet à compter du 1er septembre 2026.
- service-public.gouv.fr F14043 (vérifié le 14/08/2026) : même tableau à
  partir des assurés nés en 1963.
- Code du travail, art. L1237-5 (en vigueur depuis le 26/10/2025) : la mise à
  la retraite vise un salarié ayant atteint l'âge du 1° de l'article L. 351-8
  du code de la sécurité sociale ; avant, chaque année « jusqu'au
  soixante-neuvième anniversaire », l'employeur interroge le salarié par écrit
  et ne peut le mettre à la retraite en cas de refus.
- BOSS, « Indemnités de rupture », § 1590 et 1600 : « Le salarié ayant atteint
  l'âge de 70 ans peut faire l'objet d'une mise à la retraite d'office » ;
  avant, il faut l'âge du taux plein du 1° de L. 351-8 et l'accord exprès du
  salarié ; § 1610 : sinon la rupture est un licenciement. § 1540 : un départ
  volontaire n'est possible qu'à l'âge où le salarié peut liquider sa pension.

L'âge du taux plein du 1° de L. 351-8 est retenu à 67 ans (la consigne,
BOSS § 1600 : « Cet âge peut donc varier selon l'année de naissance » ; les
générations concernées par un autre âge ont plus de 70 ans en 2026).

Module pur.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from dateutil.relativedelta import relativedelta

AGE_TAUX_PLEIN = 67
AGE_MISE_A_LA_RETRAITE_D_OFFICE = 70


@dataclass(frozen=True)
class AgeLegal:
    annees: int
    mois: int
    #: False : génération née avant le 1er septembre 1961, âge « au plus ».
    exact: bool = True

    @property
    def libelle(self) -> str:
        texte = f"{self.annees} ans" + (f" et {self.mois} mois" if self.mois else "")
        return texte if self.exact else f"{texte} au plus"


def age_legal_de_depart(naissance: date) -> AgeLegal:
    """L'âge à partir duquel l'assuré né ce jour-là peut liquider sa pension (L161-17-2)."""
    if naissance >= date(1969, 1, 1):
        return AgeLegal(64, 0)
    if naissance.year == 1968:
        return AgeLegal(63, 9)
    if naissance.year == 1967:
        return AgeLegal(63, 6)
    if naissance.year == 1966:
        return AgeLegal(63, 3)
    if naissance >= date(1965, 4, 1):
        return AgeLegal(63, 0)
    if naissance >= date(1963, 1, 1):
        return AgeLegal(62, 9)
    if naissance.year == 1962:
        return AgeLegal(62, 6)
    if naissance >= date(1961, 9, 1):
        return AgeLegal(62, 3)
    return AgeLegal(62, 0, exact=False)


def date_de_l_age_legal(naissance: date) -> date:
    age = age_legal_de_depart(naissance)
    return naissance + relativedelta(years=age.annees, months=age.mois)


def a_atteint_l_age_legal(naissance: date, a_la_date: date) -> bool:
    return a_la_date >= date_de_l_age_legal(naissance)


def age_en_annees(naissance: date, a_la_date: date) -> int:
    return relativedelta(a_la_date, naissance).years


def lire_date_de_naissance(employee_data: dict) -> Optional[date]:
    valeur = (employee_data or {}).get("date_naissance")
    if isinstance(valeur, date):
        return valeur
    try:
        return date.fromisoformat(str(valeur)[:10]) if valeur else None
    except ValueError:
        return None
