"""Coût de la relecture, au tarif du modèle.

Tarif de claude-opus-5-5 : 4 $ le million de jetons en entrée, 20 $ en sortie ;
lecture du cache 0,20 $, écriture du cache à une heure 2 fois le prix d'entrée.

Les jetons par bulletin et le change sont des estimations, à régler sur le banc
d'essai : l'écran dit « environ ».
"""

from __future__ import annotations

from typing import Any

_MILLION = 1_000_000
_TARIF_ENTREE = 4.0
_TARIF_SORTIE = 20.0
_TARIF_LECTURE_CACHE = 0.20
_TARIF_ECRITURE_CACHE = 8.0

_JETONS_ENTREE_PAR_BULLETIN = 7_000
_JETONS_SORTIE_PAR_BULLETIN = 3_000
_EUROS_PAR_DOLLAR = 0.90
_MINIMUM_POUR_MOYENNE = 5


def cout_usd(usage: dict[str, Any]) -> float:
    def jetons(cle: str) -> int:
        return int(usage.get(cle) or 0)

    return (
        jetons("input_tokens") * _TARIF_ENTREE
        + jetons("output_tokens") * _TARIF_SORTIE
        + jetons("cache_read_input_tokens") * _TARIF_LECTURE_CACHE
        + jetons("cache_creation_input_tokens") * _TARIF_ECRITURE_CACHE
    ) / _MILLION


def usd_vers_eur(montant: float) -> float:
    return round(montant * _EUROS_PAR_DOLLAR, 4)


def cout_unitaire_eur(couts_usd_recents: list[float]) -> float:
    """Prix d'un bulletin : la moyenne réelle dès qu'il y a assez de relectures, sinon l'estimation."""
    if len(couts_usd_recents) < _MINIMUM_POUR_MOYENNE:
        return estimer_cout_eur(1)
    return usd_vers_eur(sum(couts_usd_recents) / len(couts_usd_recents))


def phrase_cout_reel(montant_usd: float) -> str:
    """La phrase qui dit à Elsa ce que la relecture a coûté."""
    euros = usd_vers_eur(montant_usd)
    if euros < 0.01:
        return "Coût réel : moins de 0,01 €."
    return f"Coût réel : {euros:.2f} €.".replace(".", ",", 1)


def estimer_cout_eur(nombre_de_bulletins: int) -> float:
    return usd_vers_eur(
        nombre_de_bulletins
        * cout_usd(
            {
                "input_tokens": _JETONS_ENTREE_PAR_BULLETIN,
                "output_tokens": _JETONS_SORTIE_PAR_BULLETIN,
            }
        )
    )
