"""Salarié × mois : SMIC de référence selon Quadra, la loi et EYWAI ; impact et pré-classement.

Le point non tranché n° 1 (maintien subrogé à 100 %, voir `oracle_smic.py`) a deux
lectures légales possibles (« smic_entier » et « rapport_salaires ») tant qu'Alexandre
n'a pas arbitré. `LigneComparee.smic_loi_variante` porte la seconde lecture quand elle
existe ; `preclasser` compare alors Quadra et EYWAI aux deux lectures, pas à une seule,
et pré-classe « point_non_tranche » quand l'une des deux parties suit une lecture sans
suivre l'autre — sans jamais faire disparaître un vrai écart Quadra ou une vraie
erreur EYWAI derrière ce point non tranché (voir `preclasser`).
"""
from __future__ import annotations

from dataclasses import dataclass

from scripts.verification_rgdu.oracle import Parametres, reduction_cumulee

TOLERANCE_SMIC = round(0.5 * 12.02, 2)   # 0,5 h
TOLERANCE_EUROS = 1.0


@dataclass
class LigneComparee:
    societe: str
    cle: str
    mois: int
    smic_quadra: float | None
    source_quadra: str
    smic_loi: float | None
    smic_eywai: float | None
    brut_cumule: float
    smic_cumule_prec: float
    preclassement: str = ""
    impact_quadra: float = 0.0
    impact_eywai: float = 0.0
    # Point non tranché n° 1 (maintien subrogé) : seconde lecture légale, quand elle existe.
    smic_loi_variante: float | None = None
    variante: str = ""          # nom du point non tranché, ex. « point_1_subrogation »
    note: str = ""              # texte libre pour l'appelant (raison, lecture suivie, etc.)


def impact_en_euros(brut_cumule: float, smic_cumule_prec: float, smic_mois_ref: float,
                    smic_mois_autre: float, prm: Parametres) -> float:
    ref = reduction_cumulee(brut_cumule, smic_cumule_prec + smic_mois_ref, prm)
    autre = reduction_cumulee(brut_cumule, smic_cumule_prec + smic_mois_autre, prm)
    return round(autre - ref, 2)


def _ecart(a: float | None, b: float | None) -> float | None:
    return None if a is None or b is None else abs(a - b)


def _suit(valeur: float | None, reference: float, l: LigneComparee, prm: Parametres) -> bool:
    """`valeur` (Quadra ou EYWAI) est-elle, à la tolérance près (SMIC et impact en
    euros), la même lecture que `reference` ?"""
    ecart = _ecart(valeur, reference)
    if ecart is None or ecart > TOLERANCE_SMIC:
        return False
    impact = impact_en_euros(l.brut_cumule, l.smic_cumule_prec, reference, valeur, prm)
    return abs(impact) <= TOLERANCE_EUROS


def _nom_lecture(suit_principale: bool, suit_variante: bool) -> str:
    if suit_principale and suit_variante:
        return "les deux lectures"
    if suit_principale:
        return "la lecture principale"
    if suit_variante:
        return "la variante"
    return "aucune des deux lectures"


def _segment_eywai(l: LigneComparee, e_suit_principale: bool, e_suit_variante: bool) -> str:
    if l.smic_eywai is None:
        return "EYWAI : non calculé"
    return f"EYWAI suit {_nom_lecture(e_suit_principale, e_suit_variante)}"


def _preclasser_avec_variante(l: LigneComparee, prm: Parametres, q_ok: bool, e_ok: bool) -> str | None:
    """Point non tranché n° 1 : deux lectures légales distinctes de la loi.

    Renvoie « point_non_tranche » quand Quadra ou EYWAI suit, dans la tolérance,
    l'une des deux lectures sans suivre l'autre. Renvoie `None` (classement
    ordinaire contre `smic_loi`, jamais « point_non_tranche ») dans deux cas
    symétriques :
    - Quadra ne suit NI la lecture principale NI la variante : il est hors
      tolérance quelle que soit la lecture retenue, trancher le point légal ne le
      rapprocherait pas de la loi — l'écart ne doit pas se cacher derrière un
      point non tranché, quoi que fasse EYWAI ;
    - ni Quadra ni EYWAI ne suit une lecture sans suivre l'autre (les deux
      suivent les deux, ou aucune des deux).
    Renvoie « erreur_eywai » (jamais « point_non_tranche ») quand Quadra suit une
    lecture et qu'EYWAI ne suit ni l'une ni l'autre : ce n'est pas un point à
    trancher, c'est une vraie erreur EYWAI.
    """
    q_suit_principale = q_ok
    q_suit_variante = _suit(l.smic_quadra, l.smic_loi_variante, l, prm)
    quadra_suit_une = q_suit_principale or q_suit_variante

    if l.smic_eywai is None:
        e_suit_principale = e_suit_variante = False
    else:
        e_suit_principale = e_ok
        e_suit_variante = _suit(l.smic_eywai, l.smic_loi_variante, l, prm)

    point = f" ({l.variante})" if l.variante else ""

    if not quadra_suit_une:
        # Garde miroir de celle qui protège « erreur_eywai » ci-dessous : Quadra
        # est hors tolérance quelle que soit la lecture, ce n'est pas un point à
        # trancher. Classement ordinaire, quoi que suive EYWAI ; la note dit
        # seulement, pour mémoire, la lecture qu'EYWAI suit.
        if l.smic_eywai is not None and (e_suit_principale or e_suit_variante):
            l.note = (
                f"point non tranché{point} : Quadra ne suit ni l'une ni l'autre lecture "
                f"(trancher le point légal ne le rapprocherait pas de la loi) ; "
                f"{_segment_eywai(l, e_suit_principale, e_suit_variante)}"
            )
        return None

    eywai_suit_aucune = l.smic_eywai is not None and not e_suit_principale and not e_suit_variante
    if eywai_suit_aucune:
        l.note = (
            f"point non tranché{point} : Quadra suit une des deux lectures légales, "
            "EYWAI ne suit ni l'une ni l'autre : reste une erreur EYWAI, pas un point à trancher."
        )
        return "erreur_eywai"

    q_exactement_une = q_suit_principale != q_suit_variante
    e_exactement_une = l.smic_eywai is not None and e_suit_principale != e_suit_variante
    if not (q_exactement_une or e_exactement_une):
        return None

    l.note = (
        f"point non tranché{point} : "
        f"Quadra suit {_nom_lecture(q_suit_principale, q_suit_variante)} ; "
        f"{_segment_eywai(l, e_suit_principale, e_suit_variante)}"
    )
    return "point_non_tranche"


def preclasser(l: LigneComparee, prm: Parametres) -> str:
    """Pré-classe une ligne salarié × mois. Valeurs renvoyées :

    - « identique » : Quadra et, s'il est connu, EYWAI collent à la loi à moins
      d'un centime de SMIC (et d'impact nul en euros) ;
    - « arrondi » : les deux collent à la loi dans la tolérance (0,5 h de SMIC,
      1 € de réduction), mais pas à moins d'un centime ;
    - « a_juger_quadra » : Quadra s'écarte de la loi au-delà de la tolérance,
      EYWAI (s'il est connu) la suit — y compris quand Quadra ne suit NI la
      lecture principale NI la variante du point non tranché n° 1 : trancher ce
      point ne le rapprocherait pas de la loi, ce n'est jamais un
      « point_non_tranche » (voir plus bas) ;
    - « erreur_eywai » : Quadra suit la loi, EYWAI s'en écarte seul — y compris
      quand Quadra ne suit que l'une des deux lectures du point non tranché n° 1
      et qu'EYWAI ne suit ni l'une ni l'autre (voir plus bas) ;
    - « a_juger_les_deux » : Quadra et EYWAI s'écartent tous deux de la loi ;
    - « donnee_manquante » : le SMIC légal ou celui de Quadra est inconnu ;
    - « point_non_tranche » : le point non tranché n° 1 (maintien subrogé) porte
      deux lectures légales distinctes (`smic_loi_variante` renseigné et
      s'écartant de `smic_loi` au-delà de la tolérance), et Quadra ou EYWAI suit,
      dans la tolérance, l'une des deux lectures sans suivre l'autre. Le
      classement final (`methode_legale_differente` ou non) attend l'arbitrage
      d'Alexandre à la tâche 9. Deux gardes symétriques l'empêchent de masquer
      une vraie erreur : si Quadra ne suit aucune des deux lectures, la ligne
      reste « a_juger_quadra » (ou « a_juger_les_deux ») quoi que fasse EYWAI ;
      si EYWAI ne suit ni l'une ni l'autre lecture alors que Quadra en suit une,
      la ligne reste « erreur_eywai ».

    `impact_quadra` et `impact_eywai` sont toujours calculés par rapport à
    `smic_loi` (la lecture principale), quel que soit le classement renvoyé.
    """
    if l.smic_loi is None or l.smic_quadra is None:
        return "donnee_manquante"

    l.impact_quadra = impact_en_euros(l.brut_cumule, l.smic_cumule_prec, l.smic_loi, l.smic_quadra, prm)
    if l.smic_eywai is not None:
        l.impact_eywai = impact_en_euros(l.brut_cumule, l.smic_cumule_prec, l.smic_loi, l.smic_eywai, prm)

    q_ok = _ecart(l.smic_quadra, l.smic_loi) <= TOLERANCE_SMIC and abs(l.impact_quadra) <= TOLERANCE_EUROS
    e = _ecart(l.smic_eywai, l.smic_loi)
    e_ok = e is None or (e <= TOLERANCE_SMIC and abs(l.impact_eywai) <= TOLERANCE_EUROS)

    if l.smic_loi_variante is not None and _ecart(l.smic_loi_variante, l.smic_loi) > TOLERANCE_SMIC:
        resultat = _preclasser_avec_variante(l, prm, q_ok, e_ok)
        if resultat is not None:
            return resultat

    if q_ok and e_ok:
        exact = _ecart(l.smic_quadra, l.smic_loi) < 0.01 and (e is None or e < 0.01)
        return "identique" if exact else "arrondi"
    if not q_ok and e_ok:
        return "a_juger_quadra"
    if q_ok and not e_ok:
        return "erreur_eywai"
    return "a_juger_les_deux"
