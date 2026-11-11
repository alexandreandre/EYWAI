"""Prévoyance que la loi impose : sans elle, le bulletin le signale.

Depuis le 11/11/2026 (périmètre validé par Elsa, R109 et R111), c'est une
alerte, plus un refus : un cadre multi-employeurs peut être couvert par
ailleurs, et la RH tranche. Le bulletin se calcule sans ligne de prévoyance et
porte l'alerte jusqu'à ce que la fiche soit complétée.

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
deux cadres sans prévoyance pendant des mois). D'où l'alerte, sur la fiche et
sur le bulletin ; c'est la RH qui coche la prévoyance, jamais Martine.

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
CODE_CADRE_SOUS_LE_MINIMUM = "prevoyance_cadre_sous_le_minimum"

IDCC_PLASTURGIE = "0292"
#: Accord du 29/10/2014, art. 3 : « une ancienneté d'au moins trois mois ».
MOIS_D_ANCIENNETE_PLASTURGIE = 3
#: ANI du 17/11/2017, art. 1er : 1,50 % de la tranche A, à la charge exclusive de
#: l'employeur, affecté par priorité au décès. La part patronale du régime frais
#: de santé compte pour vérifier ce minimum (Cass. soc. 30/03/2022, n° 20-15.022,
#: lu sur sources secondaires : Lefebvre Dalloz, CMS, LégiSocial ; Légifrance ne
#: répond pas), sauf cadre dispensé de ce régime (sa part de santé est nulle ici).
TAUX_MINIMUM_CADRES = 0.015
#: L'article 1er n'est pas opposable dans la métallurgie (voir plus haut) : le
#: minimum en pourcentage ne s'y contrôle pas.
IDCC_METALLURGIE = "3248"


@dataclass(frozen=True)
class PrevoyanceManquante:
    """Ce qui manque, dit pour la fiche et pour le bulletin."""

    code: str
    #: Sur la fiche, sans nom : le constat et le geste.
    fiche: str
    #: Sur le bulletin : le constat et le geste ; court (l'écran coupe à 220 signes).
    bulletin: str

    def alerte_du_bulletin(self) -> Dict[str, Any]:
        """L'alerte que porte le bulletin ; elle n'arrête pas le calcul."""
        return {
            "code": self.code,
            "severity": "warning",
            "critique": False,
            "message": self.bulletin,
        }


_CADRE_SANS_PREVOYANCE = PrevoyanceManquante(
    code=CODE_CADRE_SANS_PREVOYANCE,
    fiche=(
        "Cadre sans prévoyance : la loi l'impose, payée par l'employeur. Cochez "
        "« Adhésion prévoyance » et saisissez les lignes du contrat de prévoyance. "
        "D'ici là, son bulletin n'en porte aucune et le signale."
    ),
    bulletin=(
        "Cadre sans prévoyance sur sa fiche : le bulletin n'en porte aucune. La loi "
        "l'impose, payée par l'employeur. S'il est couvert, cochez « Adhésion "
        "prévoyance » sur la fiche, saisissez les lignes du contrat, puis recalculez."
    ),
)

_CADRE_SANS_LIGNE = PrevoyanceManquante(
    code=CODE_CADRE_SANS_LIGNE,
    fiche=(
        "Prévoyance cochée sans ligne : le bulletin de ce cadre n'en porterait "
        "aucune. Saisissez les lignes du contrat de prévoyance (taux salarial et "
        "patronal). D'ici là, son bulletin n'en porte aucune et le signale."
    ),
    bulletin=(
        "Cadre, prévoyance cochée sans ligne : le bulletin n'en porte aucune. "
        "Saisissez sur la fiche les lignes du contrat de prévoyance (taux salarial "
        "et patronal), puis recalculez."
    ),
)


_PLASTURGIE_SANS_PREVOYANCE = PrevoyanceManquante(
    code=CODE_PLASTURGIE_SANS_PREVOYANCE,
    fiche=(
        "Sans prévoyance après 3 mois d'ancienneté : la convention de la plasturgie "
        "l'impose (au moins 0,8 % du brut, moitié employeur). Cochez « Adhésion "
        "prévoyance ». D'ici là, son bulletin n'en porte aucune et le signale. Une dispense du "
        "salarié n'est possible que si l'acte de l'entreprise la prévoit (CSS "
        "R242-1-6) : Martine ne la gère pas, à régler avec le contrat de prévoyance."
    ),
    bulletin=(
        "3 mois d'ancienneté, sans prévoyance sur sa fiche : le bulletin n'en porte "
        "aucune. La convention de la plasturgie l'impose. S'il est couvert, cochez "
        "« Adhésion prévoyance » sur la fiche, puis recalculez."
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


def _taux_patronal_tranche_a(lignes: Any) -> float:
    """Taux patronal des lignes assises sur la tranche A ; le salaire total la contient."""
    taux = 0.0
    for ligne in lignes if isinstance(lignes, list) else []:
        if not isinstance(ligne, dict) or ligne.get("base") == "tranche_2":
            continue
        try:
            taux += float(ligne.get("patronal") or 0.0)
        except (TypeError, ValueError):
            continue
    return taux


def _pourcent(taux: float) -> str:
    return f"{taux * 100:.3f}".rstrip("0").rstrip(".").replace(".", ",")


def _euros(montant: float) -> str:
    return f"{montant:.2f}".replace(".", ",")


def alerte_minimum_cadre(
    lignes: Any, *, sante_patronale: float, tranche_a: float, idcc: Any = None
) -> Optional[Dict[str, Any]]:
    """Avertissement si la part patronale (santé comprise) est sous 1,50 % de la
    tranche A. N'arrête jamais le bulletin : le contrat peut être à corriger, pas
    le calcul. Métallurgie exclue (voir `IDCC_METALLURGIE`)."""
    if tranche_a <= 0 or _idcc(idcc() if callable(idcc) else idcc) == IDCC_METALLURGIE:
        return None
    taux = _taux_patronal_tranche_a(lignes)
    # + 1e-9 : un demi-centime tombé juste sous sa vraie valeur en binaire.
    verse = round(tranche_a * taux + float(sante_patronale or 0.0) + 1e-9, 2)
    minimum = round(tranche_a * TAUX_MINIMUM_CADRES + 1e-9, 2)
    if verse + 0.01 >= minimum:
        return None
    return {
        "code": CODE_CADRE_SOUS_LE_MINIMUM,
        "severity": "warning",
        "critique": False,
        "message": (
            f"Prévoyance cadre sous le minimum : part patronale de {_euros(verse)} € "
            f"(taux de {_pourcent(taux)} % sur la tranche A, part santé comprise), pour un "
            f"minimum de {_euros(minimum)} € soit 1,50 % de la tranche A (ANI du "
            "17/11/2017). Vérifiez le contrat de prévoyance et les lignes de la fiche."
        ),
    }


def idcc_de_la_classification(employee: Dict[str, Any]) -> str:
    """L'IDCC que la classification de la fiche porte (reprise de la DSN), ou « »."""
    return _idcc(_dict(employee.get("classification_conventionnelle")).get("idcc"))


def alertes_prevoyance_de_la_fiche(
    employee: Dict[str, Any],
    *,
    idcc: Any = None,
    fin_du_mois: Optional[date] = None,
    plafond_mensuel: Optional[float] = None,
    sante_patronale: Any = None,
) -> list[Dict[str, str]]:
    """Les alertes à montrer sur la fiche : `[{code, message}]`, vide si rien ne manque.

    `plafond_mensuel` et `sante_patronale` (montant, ou fonction qui le lit, None si
    illisible) servent au contrôle du minimum des cadres ; sans eux il ne se fait pas.
    """
    manque = prevoyance_manquante(employee, idcc=idcc, fin_du_mois=fin_du_mois)
    if manque:
        return [{"code": manque.code, "message": manque.fiche}]
    if not plafond_mensuel or not cadre_de_la_prevoyance(employee):
        return []
    lignes = _prevoyance(employee).get("lignes_specifiques")
    if _taux_patronal_tranche_a(lignes) >= TAUX_MINIMUM_CADRES:
        return []
    sante = sante_patronale() if callable(sante_patronale) else sante_patronale
    if sante is None:
        return []
    alerte = alerte_minimum_cadre(
        lignes,
        sante_patronale=float(sante),
        tranche_a=_tranche_a_de_la_fiche(employee, float(plafond_mensuel)),
        idcc=idcc,
    )
    return [{"code": alerte["code"], "message": alerte["message"]}] if alerte else []


def _tranche_a_de_la_fiche(employee: Dict[str, Any], plafond_mensuel: float) -> float:
    """Le salaire de base de la fiche, plafonné ; à défaut le plafond entier."""
    salaire = _dict(employee.get("salaire_de_base")).get("valeur")
    try:
        montant = float(salaire)
    except (TypeError, ValueError):
        return plafond_mensuel
    return min(montant, plafond_mensuel) if montant > 0 else plafond_mensuel


def dernier_jour_du_mois(annee: int, mois: int) -> date:
    return date(annee, mois, calendar.monthrange(annee, mois)[1])
