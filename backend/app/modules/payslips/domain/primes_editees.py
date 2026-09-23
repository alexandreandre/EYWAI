"""Les primes saisies qui ont changé entre deux versions d'un bulletin.

Pourquoi ce module : l'écran « Modifier le bulletin » laissait ajouter une
ligne de prime qui ne bougeait que le brut — ni bases, ni cotisations, ni
cumuls (retour de Gaëlle du 23/09/2026). Désormais une prime ajoutée, corrigée
ou retirée depuis le bulletin devient une variable du mois, et le moteur refait
tout (spec 2026-09-23).

On ne regarde que deux sortes de lignes, dans le brut et dans les primes non
soumises :

- celles qui portent `saisie_id` — imprimées par le moteur depuis une saisie ;
- celles qui portent `nouvelle_saisie` — ajoutées depuis le bulletin avec le
  sélecteur de primes.

Toute autre ligne (salaire de base, absence, prime d'ancienneté calculée) n'est
pas une prime saisie et reste hors du calcul.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Iterator

_SECTIONS = ("calcul_du_brut", "primes_non_soumises")
_TOLERANCE = 0.005


@dataclass(frozen=True)
class DiffPrimes:
    ajoutees: tuple[dict[str, Any], ...] = ()
    modifiees: tuple[tuple[str, float], ...] = ()
    retirees: tuple[str, ...] = ()

    @property
    def vide(self) -> bool:
        return not (self.ajoutees or self.modifiees or self.retirees)

    @property
    def ids_touches(self) -> set[str]:
        return {sid for sid, _ in self.modifiees} | set(self.retirees)


def _lignes(payslip_data: dict[str, Any] | None) -> Iterator[dict[str, Any]]:
    for section in _SECTIONS:
        for ligne in (payslip_data or {}).get(section) or []:
            if isinstance(ligne, dict) and not ligne.get("is_sous_total"):
                yield ligne


def _montant(ligne: dict[str, Any]) -> float:
    """Le brut porte `gain`, les primes non soumises `montant`."""
    for cle in ("gain", "montant"):
        valeur = ligne.get(cle)
        if isinstance(valeur, (int, float)) and not isinstance(valeur, bool):
            return round(float(valeur), 2)
    return 0.0


def _par_saisie(payslip_data: dict[str, Any] | None) -> dict[str, float]:
    return {
        str(ligne["saisie_id"]): _montant(ligne)
        for ligne in _lignes(payslip_data)
        if ligne.get("saisie_id")
    }


def diff_primes(avant: dict[str, Any] | None, apres: dict[str, Any] | None) -> DiffPrimes:
    """Ajoutées, montants corrigés et retirées, d'`avant` à `apres`."""
    ids_avant = _par_saisie(avant)
    ids_apres = _par_saisie(apres)

    ajoutees = tuple(
        {**ligne["nouvelle_saisie"], "amount": _montant(ligne)}
        for ligne in _lignes(apres)
        if isinstance(ligne.get("nouvelle_saisie"), dict)
    )
    modifiees = tuple(
        (sid, montant)
        for sid, montant in ids_apres.items()
        if sid in ids_avant and abs(montant - ids_avant[sid]) > _TOLERANCE
    )
    retirees = tuple(sid for sid in ids_avant if sid not in ids_apres)
    return DiffPrimes(ajoutees, modifiees, retirees)


def sans_marques_de_saisie(payslip_data: dict[str, Any] | None) -> dict[str, Any]:
    """Copie du bulletin sans les blocs `nouvelle_saisie`.

    La marque ne sert qu'à dire au serveur « crée cette variable du mois ». Une
    fois l'écart calculé, le bulletin enregistré ne doit plus la porter : si le
    moteur échouait au recalcul, le prochain enregistrement recréerait la même
    prime une seconde fois.
    """
    propre = copy.deepcopy(payslip_data or {})
    for section in _SECTIONS:
        for ligne in propre.get(section) or []:
            if isinstance(ligne, dict):
                ligne.pop("nouvelle_saisie", None)
    return propre
