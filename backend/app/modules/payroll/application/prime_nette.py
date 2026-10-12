"""Le brut d'une prime pour un net voulu, sur le bulletin du mois du salarié.

La fenêtre des primes demande « combien de brut pour que la prime rapporte
100 € nets ? ». La réponse est marginale : le brut X tel que

    net à payer (bulletin du mois avec la prime X)
  − net à payer (bulletin du mois sans elle)  = net voulu,

chaque bulletin étant celui du salarié (salaire, saisies du mois, cumuls),
calculé en bac à sable par l'appelant. Ce n'est pas le brut d'un bulletin
entier dont le net vaudrait 100 € (lot 30).

Le net avance par marches d'arrondi, pas tout à fait régulières : chez
Colorplast (octobre 2026), 129,27 € et 129,29 € bruts ajoutent tous deux
100,00 €, 129,28 € ajoute 100,01 €. Le brut rendu est donc défini sans
ambiguïté : le plus petit centime qui ajoute exactement le net voulu (lot 31).
Il ne dépend pas du chemin de la recherche.

La recherche : le bulletin sans la prime, un premier essai qui donne la pente,
puis la sécante qui part du bulletin sans prime vise ce centime ; le centime
d'en dessous confirme qu'il est le premier. Quatre bulletins en règle
générale (trois à cinq au lot 30, qui pouvait s'arrêter sur un centime plus
haut), trois pour une prime ni soumise ni imposable.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from typing import Any

#: Part du brut d'une prime soumise qui reste au net, pour le premier essai
#: seulement : il ne sert qu'à mesurer la pente.
PART_NETTE_PREMIER_ESSAI = 0.75
#: Bulletins calculés au plus, celui sans la prime compris.
ESSAIS_MAX = 7
CENTIME = 0.01
#: Un net « atteint » le net voulu au demi-centime près (nets arrondis au centime).
_DEMI_CENTIME = 0.005


def _net(bulletin: Mapping[str, Any]) -> float:
    return float(bulletin.get("net_a_payer") or 0.0)


def _cout(bulletin: Mapping[str, Any]) -> float:
    return float((bulletin.get("pied_de_page") or {}).get("cout_total_employeur") or 0.0)


def _taux_du_prelevement(bulletin: Mapping[str, Any]) -> float:
    pas = (bulletin.get("synthese_net") or {}).get("impot_prelevement_a_la_source") or {}
    try:
        return float(pas.get("taux") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _pente_du_premier_essai(
    sans: Mapping[str, Any], soumise_a_cotisations: bool, soumise_a_impot: bool
) -> float:
    """La part nette attendue d'un euro de prime, avant tout essai.

    Sans cotisations, seule la retenue à la source mord sur la prime (son taux
    est sur le bulletin sans prime) ; sans cotisations ni impôt, la prime est
    nette. Une prime soumise part d'une part forfaitaire.
    """
    if soumise_a_cotisations:
        return PART_NETTE_PREMIER_ESSAI
    if not soumise_a_impot:
        return 1.0
    taux = _taux_du_prelevement(sans)
    return 1.0 - taux / 100.0 if 0.0 <= taux < 100.0 else PART_NETTE_PREMIER_ESSAI


def _premier_centime(net_voulu: float, pente: float) -> float:
    """Le premier centime où la droite de pente `pente` atteint le net voulu."""
    return math.ceil(round((net_voulu - _DEMI_CENTIME) / pente * 100, 6)) / 100


def chercher_brut_de_prime(
    net_voulu: float,
    bulletin_avec_prime: Callable[[float], Mapping[str, Any]],
    *,
    soumise_a_cotisations: bool = True,
    soumise_a_impot: bool = True,
) -> dict[str, Any]:
    """Le plus petit brut, au centime, d'une prime qui ajoute `net_voulu` au net à payer.

    `bulletin_avec_prime(montant)` rend le bulletin du mois avec une prime
    brute de `montant` (0 : sans prime). Sans centime exact (une marche
    enjambe le net voulu), le brut dont le net ajouté est le plus proche,
    au moins le net voulu à égalité.
    """
    if net_voulu <= 0:
        raise ValueError("Le net voulu pour la prime doit être strictement positif.")

    sans = bulletin_avec_prime(0.0)
    net_sans, cout_sans = _net(sans), _cout(sans)
    # brut -> (net ajouté, coût ajouté) ; le bulletin sans prime est le point zéro.
    essais: dict[float, tuple[float, float]] = {0.0: (0.0, 0.0)}

    def ajoute(brut: float) -> float:
        if brut not in essais:
            bulletin = bulletin_avec_prime(brut)
            essais[brut] = (
                round(_net(bulletin) - net_sans, 2),
                round(_cout(bulletin) - cout_sans, 2),
            )
        return essais[brut][0]

    def atteint(brut: float) -> bool:
        return ajoute(brut) >= net_voulu - _DEMI_CENTIME

    # 1. La sécante qui part du bulletin sans prime vise le premier centime qui
    #    atteint le net voulu, jusqu'à ce qu'elle vise le centime déjà essayé.
    brut = _premier_centime(
        net_voulu, _pente_du_premier_essai(sans, soumise_a_cotisations, soumise_a_impot)
    )
    while len(essais) < ESSAIS_MAX:
        net = ajoute(brut)
        if net <= 0:
            break
        vise = _premier_centime(net_voulu, net / brut)
        if vise <= 0 or vise == brut or vise in essais:
            break
        brut = vise

    # 2. Au centime : le premier brut qui atteint le net voulu, celui d'en
    #    dessous ne l'atteignant pas.
    while len(essais) < ESSAIS_MAX:
        if atteint(brut):
            dessous = round(brut - CENTIME, 2)
            if dessous <= 0 or not atteint(dessous):
                break
            brut = dessous
        else:
            brut = round(brut + CENTIME, 2)

    candidats = [b for b in essais if b > 0]
    if not candidats:  # ESSAIS_MAX < 2 : aucun essai de prime
        raise ValueError("Aucun essai de prime n'a été calculé.")
    brut_trouve = min(
        candidats,
        key=lambda b: (
            round(abs(essais[b][0] - net_voulu), 2),  # le net le plus proche,
            essais[b][0] < net_voulu - _DEMI_CENTIME,  # au moins le net voulu,
            b,  # puis le plus petit brut.
        ),
    )
    net_ajoute, cout_ajoute = essais[brut_trouve]
    ecart = round(net_ajoute - net_voulu, 2)
    return {
        "mode": "prime",
        "brut_calcule": brut_trouve,
        "net_obtenu": net_ajoute,
        "ecart": ecart,
        "iterations": len(essais),
        "convergence": abs(ecart) <= 0.01,
        "cout_employeur": cout_ajoute,
        "net_a_payer_sans_prime": round(net_sans, 2),
        "net_a_payer_avec_prime": round(net_sans + net_ajoute, 2),
        "bulletin_complet": None,
    }
