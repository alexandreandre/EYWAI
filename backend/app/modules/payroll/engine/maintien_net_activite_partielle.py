"""Forfait jours en métallurgie : le net ne baisse pas pendant l'activité partielle.

Convention collective nationale de la métallurgie (IDCC 3248), art. 103.5.1 :
« La rémunération nette du salarié ayant conclu une convention individuelle de
forfait en jours sur l'année ne peut être réduite du fait d'une mesure
d'activité partielle mise en œuvre dans les conditions prévues au I de
l'article L. 5122-1 du code du travail. » (Légifrance, lu le 20/11/2026,
data/_sources/activite-partielle/.) L'APLD (art. 53 de la loi 2020-734) en est
exclue : Martine n'en a pas de réglage, l'activité partielle posée est celle de
L. 5122-1.

L'employeur verse donc un complément. Il est cotisé et imposé comme un salaire
(Urssaf, « Les revenus de remplacement » : « Les indemnités complémentaires
sont en principe assujetties comme des revenus d'activité »). Son montant est
celui qui rend au salarié le net avant impôt du mois calculé sans activité
partielle : ni plus, ni moins. Quadra versait de même environ 85 % de la
retenue chez LEWIS, sans ligne séparée.
"""

from __future__ import annotations

from typing import Any, Callable

from app.modules.activite_partielle.domain.calcul import LIBELLE_INDEMNITE, LIBELLES

LIBELLE_COMPLEMENT = "Complément employeur activité partielle"
IDCC_METALLURGIE = "3248"

#: Première estimation des retenues salariales sur le complément (cadre, sous
#: le plafond) ; la suite se règle sur ce que le calcul rend.
_PART_RETENUE_ESTIMEE = 0.25
_PASSES_MAX = 6


def _idcc(valeur: object) -> str:
    return str(valeur or "").strip().lstrip("0")


def s_applique(idcc: object, primes: list[dict[str, Any]]) -> bool:
    """Métallurgie, et une indemnité d'activité partielle dans le mois."""
    if _idcc(idcc) != IDCC_METALLURGIE:
        return False
    return any(
        str(p.get("libelle") or "").startswith(LIBELLE_INDEMNITE) and float(p.get("montant") or 0) > 0
        for p in primes
    )


def _est_de_l_activite_partielle(p: dict[str, Any]) -> bool:
    libelle = str(p.get("libelle") or "")
    return any(libelle.startswith(x) for x in (*LIBELLES, LIBELLE_COMPLEMENT))


def sans_activite_partielle(primes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Les primes du mois comme si l'activité partielle n'avait pas eu lieu."""
    return [p for p in primes if not _est_de_l_activite_partielle(p)]


def avec_complement(primes: list[dict[str, Any]], montant: float) -> list[dict[str, Any]]:
    """Les primes du mois, complément remplacé par `montant` (rien s'il est nul)."""
    gardees = [p for p in primes if str(p.get("libelle") or "") != LIBELLE_COMPLEMENT]
    if montant <= 0:
        return gardees
    return [
        *gardees,
        {
            "prime_id": "complement_activite_partielle",
            "libelle": LIBELLE_COMPLEMENT,
            "montant": round(montant, 2),
            "soumise_a_cotisations": True,
            "soumise_a_impot": True,
        },
    ]


def net_avant_impot(bulletin: dict[str, Any]) -> float:
    """Le net du mois avant impôt sur le revenu (celui que la convention garde)."""
    synthese = bulletin.get("synthese_net") or {}
    valeur = synthese.get("net_social_avant_impot")
    if valeur is None:
        impot = (synthese.get("impot_prelevement_a_la_source") or {}).get("montant") or 0.0
        valeur = float(bulletin.get("net_a_payer") or 0.0) + float(impot)
    return round(float(valeur), 2)


def complement_qui_garde_le_net(
    primes: list[dict[str, Any]],
    calculer_net: Callable[[list[dict[str, Any]]], float],
) -> float:
    """Le complément (au centime) qui rend le net du mois sans activité partielle.

    `calculer_net(primes)` calcule le bulletin avec ces primes et rend son net
    avant impôt. 0 si l'activité partielle ne fait pas baisser le net.
    """
    cible = calculer_net(sans_activite_partielle(primes))
    c0, net0 = 0.0, calculer_net(avec_complement(primes, 0.0))
    if net0 >= cible:
        return 0.0
    c1 = round((cible - net0) / (1 - _PART_RETENUE_ESTIMEE), 2)
    net1 = calculer_net(avec_complement(primes, c1))
    for _ in range(_PASSES_MAX):
        if abs(net1 - cible) < 0.005:
            break
        pente = (net1 - net0) / (c1 - c0) if c1 != c0 else 1 - _PART_RETENUE_ESTIMEE
        if pente <= 0:
            pente = 1 - _PART_RETENUE_ESTIMEE
        c0, net0 = c1, net1
        c1 = round(c1 + (cible - net1) / pente, 2)
        if c1 == c0:
            c1 = round(c1 + (0.01 if net1 < cible else -0.01), 2)
        net1 = calculer_net(avec_complement(primes, c1))
    # Jamais sous le net d'avant, à un centime d'arrondi près du calcul.
    for _ in range(20):
        if net1 >= cible - 0.005:
            break
        c1 = round(c1 + 0.01, 2)
        net1 = calculer_net(avec_complement(primes, c1))
    return max(0.0, c1)
