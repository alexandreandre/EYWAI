"""Affiliations prévoyance / santé (bloc S21.G00.70) déduites des collègues.

Les affiliations des salariés présents à la reprise viennent des DSN de
l'ancien logiciel (`specificites_paie.affiliations_psc`). Un salarié embauché
depuis n'en a pas, et DSN-VAL refuse ses bases 31 (CCH-11 / CCH-12 sur
S21.G00.78.005). On lui prête le jeu le plus fréquent chez ses collègues de la
même population (cadre / non-cadre) et dans la même situation face à la
mutuelle ce mois-là : un adhérent reçoit prévoyance et santé, un dispensé la
prévoyance seule. Rien dans la DSN ne dit quel contrat est de santé (le bloc
15 n'a pas de nature de garantie, options et populations sont propres à
l'organisme) : c'est la situation des collègues qui le dit.

Seuls les champs du contrat passent (70.013, 70.004, 70.005) ; l'identifiant
technique d'affiliation (70.012) est celui du salarié, numéroté chez lui.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

#: Champs du contrat collectif : identiques pour tous les affiliés au même contrat.
CHAMPS_CONTRAT = ("id_contrat", "option", "population")


@dataclass(frozen=True)
class Collegue:
    cadre: bool
    adherent_mutuelle: bool
    affiliations: Sequence[Mapping[str, Any]] = field(default_factory=tuple)


def _contrat(affiliation: Mapping[str, Any]) -> Tuple[Tuple[str, str], ...]:
    return tuple(
        (champ, str(affiliation[champ]))
        for champ in CHAMPS_CONTRAT
        if affiliation.get(champ) not in (None, "")
    )


def _jeu(affiliations: Sequence[Mapping[str, Any]]) -> Tuple[Tuple[Tuple[str, str], ...], ...]:
    """Le jeu d'un collègue, sans son ordre ni ses identifiants à lui."""
    return tuple(sorted(_contrat(a) for a in affiliations if isinstance(a, Mapping)))


def deduire_affiliations(
    *, cadre: bool, adherent_mutuelle: bool, collegues: Iterable[Collegue]
) -> List[Dict[str, str]]:
    """Le jeu le plus fréquent chez les collègues comparables ; [] sans modèle.

    À égalité, le plus petit jeu dans l'ordre du texte : le choix ne dépend
    pas de l'ordre de lecture des fiches.
    """
    comptes: Counter = Counter(
        _jeu(c.affiliations)
        for c in collegues
        if c.cadre == cadre and c.adherent_mutuelle == adherent_mutuelle and c.affiliations
    )
    comptes.pop((), None)
    if not comptes:
        return []
    modele = min(comptes, key=lambda jeu: (-comptes[jeu], json.dumps(jeu)))
    return [
        {"id_affiliation": str(rang), **dict(contrat)}
        for rang, contrat in enumerate(modele, start=1)
    ]
