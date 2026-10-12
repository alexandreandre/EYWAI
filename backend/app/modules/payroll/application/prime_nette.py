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
100,00 €, 129,28 € ajoute 100,01 €. Le brut rendu est le premier centime qui
ajoute exactement le net voulu, celui d'en dessous ne l'atteignant pas
(lot 31) ; s'il n'y en a pas (une marche enjambe le net voulu), le premier
qui l'atteint ou le dépasse, et la recherche dit qu'elle n'a pas convergé.

Sans taux personnalisé, le prélèvement à la source suit la grille du taux
neutre : quand la prime fait passer le net imposable dans la tranche
suivante, tout le salaire est prélevé au nouveau taux et le net recule de
plusieurs euros. Le net voulu peut alors être atteint à deux endroits ; la
recherche garde celui que la sécante croise, comme au lot 30.

La recherche : le bulletin sans la prime, un premier essai, puis des sécantes
par les deux derniers essais (par le bulletin sans prime au premier pas, ou
quand une marche du prélèvement sépare les deux essais), qui visent le
premier centime atteignant le net voulu ; enfin, au centime, le bord. Quatre à
sept bulletins, dix au plus ; trois pour une prime ni soumise ni imposable.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from typing import Any

#: Part du brut d'une prime soumise qui reste au net, pour le premier essai
#: seulement : il ne sert qu'à mesurer la pente.
PART_NETTE_PREMIER_ESSAI = 0.75
#: Bulletins calculés au plus, celui sans la prime compris. Après le premier,
#: un bulletin se calcule en mémoire (lecture seule) : quelques centièmes de
#: seconde.
ESSAIS_MAX = 10
#: Bulletins au plus pour les sécantes : il en reste pour trouver le bord.
ESSAIS_DES_SECANTES = 7
CENTIME = 0.01
#: Pente plausible d'une prime (net ajouté par euro brut) ; hors de ces bornes,
#: une marche du prélèvement sépare les deux essais.
_PENTE_MIN, _PENTE_MAX = 0.05, 1.05
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


def _premier_centime(brut: float) -> float:
    """Le centime atteint ou dépassé par `brut`."""
    return math.ceil(round(brut * 100, 6)) / 100


def chercher_brut_de_prime(
    net_voulu: float,
    bulletin_avec_prime: Callable[[float], Mapping[str, Any]],
    *,
    soumise_a_cotisations: bool = True,
    soumise_a_impot: bool = True,
) -> dict[str, Any]:
    """Le premier brut, au centime, d'une prime qui ajoute `net_voulu` au net à payer.

    `bulletin_avec_prime(montant)` rend le bulletin du mois avec une prime
    brute de `montant` (0 : sans prime). Sans centime exact (une marche
    enjambe le net voulu), le premier qui l'atteint ou le dépasse, avec
    `convergence` à False ; s'il n'est pas atteint, le plus proche.
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

    def exact(brut: float) -> bool:
        return abs(ajoute(brut) - net_voulu) < _DEMI_CENTIME

    seuil = net_voulu - _DEMI_CENTIME

    # 1. Sécantes par les deux derniers essais (par le bulletin sans prime au
    #    premier pas), qui visent le premier centime atteignant le net voulu.
    precedent = 0.0
    brut = _premier_centime(
        seuil / _pente_du_premier_essai(sans, soumise_a_cotisations, soumise_a_impot)
    )
    while len(essais) < ESSAIS_DES_SECANTES:
        net = ajoute(brut)
        if exact(brut):
            break
        pente = (net - essais[precedent][0]) / (brut - precedent)
        if not _PENTE_MIN < pente <= _PENTE_MAX:
            # Une marche du prélèvement entre les deux essais : la droite qui
            # part du bulletin sans prime.
            pente = net / brut
        if not _PENTE_MIN < pente <= _PENTE_MAX:
            break
        vise = _premier_centime(brut + (seuil - net) / pente)
        if vise <= 0 or vise in essais:
            break
        precedent, brut = brut, vise

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

    # 3. Ce bord dépasse le net voulu sans l'ajouter exactement : un ou deux
    #    centimes plus haut peuvent l'ajouter (marches irrégulières).
    if atteint(brut) and not exact(brut):
        for centimes in (1, 2):
            au_dessus = round(brut + centimes * CENTIME, 2)
            if au_dessus not in essais and len(essais) >= ESSAIS_MAX:
                break
            if exact(au_dessus):
                break

    candidats = [b for b in essais if b > 0]
    if not candidats:  # ESSAIS_MAX < 2 : aucun essai de prime
        raise ValueError("Aucun essai de prime n'a été calculé.")
    exacts = [b for b in candidats if exact(b)]
    atteignants = [b for b in candidats if atteint(b)]
    if exacts:
        brut_trouve = min(exacts)
    elif atteignants:
        brut_trouve = min(atteignants)
    else:  # le net voulu n'est pas atteint : le plus proche
        brut_trouve = min(candidats, key=lambda b: (abs(essais[b][0] - net_voulu), b))
    net_ajoute, cout_ajoute = essais[brut_trouve]
    ecart = round(net_ajoute - net_voulu, 2)
    return {
        "mode": "prime",
        "brut_calcule": brut_trouve,
        "net_obtenu": net_ajoute,
        "ecart": ecart,
        "iterations": len(essais),
        # Exactement le net voulu ; sinon la fenêtre dit le net obtenu.
        "convergence": abs(ecart) < _DEMI_CENTIME,
        "cout_employeur": cout_ajoute,
        "net_a_payer_sans_prime": round(net_sans, 2),
        "net_a_payer_avec_prime": round(net_sans + net_ajoute, 2),
        "bulletin_complet": None,
    }
