"""Prévoyance que la loi impose : sans elle, le bulletin ne se génère pas.

Cadres. ANI du 17 novembre 2017 relatif à la prévoyance des cadres (en vigueur
étendu, arrêté du 27 juillet 2018), art. 1er : « Les employeurs s'engagent à
verser, pour tout bénéficiaire visé à l'article 2 du présent accord, une
cotisation à leur charge exclusive, égale à 1,50 % de la tranche de rémunération
inférieure au plafond fixé pour les cotisations de sécurité sociale » ; art. 2.1 :
le régime « s'applique obligatoirement aux ingénieurs et cadres » (Légifrance
KALIARTI000036732016, ouvert le 04/11/2026). Dans la métallurgie, l'article 1er
n'est pas opposable (CCN du 7 février 2022, art. 166.2) mais la convention
impose à son tour une prévoyance des cadres à la charge exclusive de l'employeur :
dans tous les cas, un cadre sans prévoyance est une erreur.

Le moteur ne pose pour un cadre que les lignes de prévoyance de sa fiche : sans
adhésion, ou sans ligne, le bulletin n'en porte aucune (audit du 03/11/2026 :
deux cadres sans prévoyance pendant des mois). D'où le refus, avant tout calcul,
et l'alerte sur la fiche ; c'est la RH qui coche la prévoyance, jamais Martine.

« Cadre » se lit comme pour l'APEC : statut de paie cadre, sauf si la
classification de la fiche le déclare non-cadre (forfait jours non-cadre de la
plasturgie). Un mandataire social n'est pas un salarié de l'accord.

Non-cadres de la plasturgie (IDCC 0292). Accord du 29 octobre 2014 instaurant un
régime de prévoyance, étendu par arrêté du 17 avril 2015 (JORF 27 mai 2015),
art. 3 : « L'accord bénéficie aux salariés (y compris ceux en cumul
emploi-retraite) », hors cadres de l'ANI, « ayant une ancienneté d'au moins
trois mois dans l'entreprise » ; art. 5 : cotisation de 0,8 % du brut, dont
« une cotisation patronale minimale de 0,4 % » (Légifrance KALITEXT000030370171,
ouvert le 04/11/2026). Audit du 03/11/2026 : un CDD non-cadre sans prévoyance
après ses trois mois. Avant trois mois, la loi n'impose rien : la fiche peut
l'affilier plus tôt (contrat de l'entreprise), Martine ne l'exige pas.
L'ancienneté part de la date de reprise si la fiche en porte une, sinon de
l'embauche ; elle est atteinte dès qu'elle l'est dans le mois du bulletin.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Optional

from app.shared.domain.employment_rules import is_cadre
from app.shared.seniority_reference import resolve_date_anciennete_prime

CODE_CADRE_SANS_PREVOYANCE = "prevoyance_cadre_absente"
CODE_CADRE_SANS_LIGNE = "prevoyance_cadre_sans_ligne"
CODE_PLASTURGIE_SANS_PREVOYANCE = "prevoyance_plasturgie_absente"

IDCC_PLASTURGIE = "0292"
#: Accord du 29/10/2014, art. 3 : « une ancienneté d'au moins trois mois ».
MOIS_D_ANCIENNETE_PLASTURGIE = 3


@dataclass(frozen=True)
class PrevoyanceManquante:
    """Ce qui manque, dit pour la fiche et pour le refus de génération."""

    code: str
    #: Sur la fiche, sans nom : le constat et le geste.
    fiche: str
    #: Le refus de génération, avec `{prenom}` ; court (l'écran coupe à 220 signes).
    refus: str

    def refus_pour(self, prenom: str) -> str:
        return self.refus.format(prenom=prenom)


_CADRE_SANS_PREVOYANCE = PrevoyanceManquante(
    code=CODE_CADRE_SANS_PREVOYANCE,
    fiche=(
        "Cadre sans prévoyance : la loi l'impose, payée par l'employeur. Cochez "
        "« Adhésion prévoyance » et saisissez les lignes du contrat de prévoyance. "
        "D'ici là, son bulletin ne se génère pas."
    ),
    refus=(
        "Bulletin non généré : {prenom} est cadre, sans prévoyance sur sa fiche. "
        "La loi l'impose, payée par l'employeur. Cochez « Adhésion prévoyance » sur "
        "la fiche, saisissez les lignes du contrat, puis relancez."
    ),
)

_CADRE_SANS_LIGNE = PrevoyanceManquante(
    code=CODE_CADRE_SANS_LIGNE,
    fiche=(
        "Prévoyance cochée sans ligne : le bulletin de ce cadre n'en porterait "
        "aucune. Saisissez les lignes du contrat de prévoyance (taux salarial et "
        "patronal). D'ici là, son bulletin ne se génère pas."
    ),
    refus=(
        "Bulletin non généré : {prenom} est cadre et sa prévoyance n'a aucune "
        "ligne, le bulletin n'en porterait pas. Saisissez sur la fiche les lignes "
        "du contrat de prévoyance, puis relancez."
    ),
)


_PLASTURGIE_SANS_PREVOYANCE = PrevoyanceManquante(
    code=CODE_PLASTURGIE_SANS_PREVOYANCE,
    fiche=(
        "Sans prévoyance après 3 mois d'ancienneté : la convention de la plasturgie "
        "l'impose (au moins 0,8 % du brut, moitié employeur). Cochez « Adhésion "
        "prévoyance ». D'ici là, son bulletin ne se génère pas."
    ),
    refus=(
        "Bulletin non généré : {prenom} a 3 mois d'ancienneté, sans prévoyance sur "
        "sa fiche. La convention de la plasturgie l'impose. Cochez « Adhésion "
        "prévoyance » sur la fiche, puis relancez."
    ),
)


def _dict(valeur: Any) -> Dict[str, Any]:
    return valeur if isinstance(valeur, dict) else {}


def _non_cadre_a_la_classification(employee: Dict[str, Any]) -> bool:
    classification = _dict(employee.get("classification_conventionnelle"))
    categorie = str(classification.get("statut_categoriel") or "").strip().lower()
    return "non" in categorie and "cadre" in categorie


def _mandataire(employee: Dict[str, Any]) -> bool:
    specs = _dict(employee.get("specificites_paie"))
    if specs.get("is_mandataire") or specs.get("is_mandataire_social"):
        return True
    type_contrat = str(employee.get("contract_type") or "").lower()
    return "mandataire" in type_contrat or "mandat social" in type_contrat


def cadre_de_la_prevoyance(employee: Dict[str, Any]) -> bool:
    """Le salarié relève-t-il de la prévoyance des cadres ?"""
    return (
        is_cadre(employee.get("statut"))
        and not _non_cadre_a_la_classification(employee)
        and not _mandataire(employee)
    )


def _prevoyance(employee: Dict[str, Any]) -> Dict[str, Any]:
    return _dict(_dict(employee.get("specificites_paie")).get("prevoyance"))


def _idcc(valeur: Any) -> str:
    texte = str(valeur or "").strip()
    return texte.zfill(4) if texte.isdigit() else texte


def _stagiaire(employee: Dict[str, Any]) -> bool:
    return "stage" in str(employee.get("contract_type") or "").lower()


def _date(valeur: Any) -> Optional[date]:
    try:
        return date.fromisoformat(str(valeur or "")[:10])
    except ValueError:
        return None


def _plus_mois(jour: date, mois: int) -> date:
    rang = jour.month - 1 + mois
    annee, mois_cible = jour.year + rang // 12, rang % 12 + 1
    return date(annee, mois_cible, min(jour.day, calendar.monthrange(annee, mois_cible)[1]))


def anciennete_plasturgie_atteinte(employee: Dict[str, Any], fin_du_mois: date) -> bool:
    """Les trois mois d'ancienneté sont-ils atteints au plus tard le dernier jour du mois ?"""
    debut = _date(resolve_date_anciennete_prime(employee))
    if debut is None:
        return False
    return _plus_mois(debut, MOIS_D_ANCIENNETE_PLASTURGIE) <= fin_du_mois


def prevoyance_manquante(
    employee: Dict[str, Any],
    *,
    idcc: Any = None,
    fin_du_mois: Optional[date] = None,
) -> Optional[PrevoyanceManquante]:
    """La prévoyance que la loi impose et que la fiche n'a pas, ou None.

    `idcc` : la convention du salarié, ou une fonction qui la lit (appelée
    seulement pour un non-cadre sans prévoyance qui a ses trois mois) ; sans
    elle, seule la règle des cadres s'applique. `fin_du_mois` : le dernier jour
    du mois du bulletin, ou du jour où la fiche est lue.
    """
    prevoyance = _prevoyance(employee)
    if cadre_de_la_prevoyance(employee):
        if not prevoyance.get("adhesion"):
            return _CADRE_SANS_PREVOYANCE
        lignes = prevoyance.get("lignes_specifiques")
        if not (isinstance(lignes, list) and lignes):
            return _CADRE_SANS_LIGNE
        return None
    if (
        fin_du_mois is not None
        and not prevoyance.get("adhesion")
        and not _mandataire(employee)
        and not _stagiaire(employee)
        and anciennete_plasturgie_atteinte(employee, fin_du_mois)
        and _idcc(idcc() if callable(idcc) else idcc) == IDCC_PLASTURGIE
    ):
        return _PLASTURGIE_SANS_PREVOYANCE
    return None


def idcc_de_la_classification(employee: Dict[str, Any]) -> str:
    """L'IDCC que la classification de la fiche porte (reprise de la DSN), ou « »."""
    return _idcc(_dict(employee.get("classification_conventionnelle")).get("idcc"))


def alertes_prevoyance_de_la_fiche(
    employee: Dict[str, Any],
    *,
    idcc: Any = None,
    fin_du_mois: Optional[date] = None,
) -> list[Dict[str, str]]:
    """Les alertes à montrer sur la fiche : `[{code, message}]`, vide si rien ne manque."""
    manque = prevoyance_manquante(employee, idcc=idcc, fin_du_mois=fin_du_mois)
    return [{"code": manque.code, "message": manque.fiche}] if manque else []


def dernier_jour_du_mois(annee: int, mois: int) -> date:
    return date(annee, mois, calendar.monthrange(annee, mois)[1])
