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
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.shared.domain.employment_rules import is_cadre

CODE_CADRE_SANS_PREVOYANCE = "prevoyance_cadre_absente"
CODE_CADRE_SANS_LIGNE = "prevoyance_cadre_sans_ligne"


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


def prevoyance_manquante(employee: Dict[str, Any]) -> Optional[PrevoyanceManquante]:
    """La prévoyance que la loi impose et que la fiche n'a pas, ou None."""
    if not cadre_de_la_prevoyance(employee):
        return None
    prevoyance = _prevoyance(employee)
    if not prevoyance.get("adhesion"):
        return _CADRE_SANS_PREVOYANCE
    lignes = prevoyance.get("lignes_specifiques")
    if not (isinstance(lignes, list) and lignes):
        return _CADRE_SANS_LIGNE
    return None


def alertes_prevoyance_de_la_fiche(employee: Dict[str, Any]) -> list[Dict[str, str]]:
    """Les alertes à montrer sur la fiche : `[{code, message}]`, vide si rien ne manque."""
    manque = prevoyance_manquante(employee)
    return [{"code": manque.code, "message": manque.fiche}] if manque else []
