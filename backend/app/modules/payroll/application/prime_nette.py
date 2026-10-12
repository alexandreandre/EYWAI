"""Le brut d'une prime pour un net voulu, sur le bulletin du mois du salarié.

La fenêtre des primes demande « combien de brut pour que la prime rapporte
100 € nets ? ». La réponse est marginale : le brut X tel que

    net à payer (bulletin du mois avec la prime X)
  − net à payer (bulletin du mois sans elle)  = net voulu,

chaque bulletin étant celui du salarié (salaire, saisies du mois, cumuls),
calculé en bac à sable par l'appelant. Ce n'est pas le brut d'un bulletin
entier dont le net vaudrait 100 € (lot 30).

Chaque bulletin coûte une génération complète : la recherche part du bulletin
sans la prime, essaie un premier brut, puis avance par sécantes, au centime.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Mapping

#: Part du brut d'une prime qui reste au net, pour le premier essai seulement.
PART_NETTE_PREMIER_ESSAI = 0.75
#: Bulletins calculés au plus (le premier est celui sans la prime).
ESSAIS_MAX = 6


def _net(bulletin: Mapping[str, Any]) -> float:
    return float(bulletin.get("net_a_payer") or 0.0)


def _cout(bulletin: Mapping[str, Any]) -> float:
    return float((bulletin.get("pied_de_page") or {}).get("cout_total_employeur") or 0.0)


def chercher_brut_de_prime(
    net_voulu: float,
    bulletin_avec_prime: Callable[[float], Mapping[str, Any]],
) -> Dict[str, Any]:
    """Le brut (au centime) d'une prime qui ajoute `net_voulu` au net à payer.

    `bulletin_avec_prime(montant)` rend le bulletin du mois avec une prime
    brute de `montant` (0 : sans prime).
    """
    if net_voulu <= 0:
        raise ValueError("Le net voulu pour la prime doit être strictement positif.")

    sans = bulletin_avec_prime(0.0)
    net_sans, cout_sans = _net(sans), _cout(sans)
    essais = 1
    # (brut, net ajouté, coût ajouté) ; le bulletin sans prime est le point zéro.
    points: list[tuple[float, float, float]] = [(0.0, 0.0, 0.0)]
    meilleur: tuple[float, float, float] | None = None

    brut = round(net_voulu / PART_NETTE_PREMIER_ESSAI, 2)
    while essais < ESSAIS_MAX:
        bulletin = bulletin_avec_prime(brut)
        essais += 1
        point = (brut, round(_net(bulletin) - net_sans, 2), round(_cout(bulletin) - cout_sans, 2))
        points.append(point)
        if meilleur is None or abs(point[1] - net_voulu) < abs(meilleur[1] - net_voulu):
            meilleur = point
        if abs(point[1] - net_voulu) < 0.005:
            break
        (brut_a, net_a, _), (brut_b, net_b, _) = points[-2], points[-1]
        if net_b == net_a:
            break
        suivant = round(brut_b + (net_voulu - net_b) * (brut_b - brut_a) / (net_b - net_a), 2)
        if suivant <= 0 or any(abs(suivant - p[0]) < 0.005 for p in points):
            break
        brut = suivant

    if meilleur is None:  # ESSAIS_MAX < 2 : aucun essai de prime
        raise ValueError("Aucun essai de prime n'a été calculé.")
    brut_trouve, net_ajoute, cout_ajoute = meilleur
    ecart = round(net_ajoute - net_voulu, 2)
    return {
        "mode": "prime",
        "brut_calcule": brut_trouve,
        "net_obtenu": net_ajoute,
        "ecart": ecart,
        "iterations": essais,
        "convergence": abs(ecart) <= 0.01,
        "cout_employeur": cout_ajoute,
        "net_a_payer_sans_prime": round(net_sans, 2),
        "net_a_payer_avec_prime": round(net_sans + net_ajoute, 2),
        "bulletin_complet": None,
    }
