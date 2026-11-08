"""Les prêts et saisies retenus par l'ancien logiciel au dernier mois repris.

Le capital d'un prêt et l'avis d'une saisie ne sont pas sur le bulletin, et le montant
d'une saisie varie d'un mois à l'autre : Martine ne les invente pas, elle signale ce
qui reste à poser. Module pur.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

Nature = Literal["pret", "saisie"]

_PRET = re.compile(r"pr[eê]t", re.IGNORECASE)
_SAISIE = re.compile(r"\bsaisie\b|^\s*s?atd\b|tiers\s+d[ée]tenteur|pension\s+aliment", re.IGNORECASE)

#: Combien de mois après la bascule on rappelle ce qui reste à poser.
MOIS_DE_RAPPEL = 3


@dataclass(frozen=True)
class RetenueReprise:
    nature: Nature
    libelle: str
    montant: float


def _montant(ligne: Mapping[str, Any]) -> float:
    try:
        return float(ligne.get("montant") or 0)
    except (TypeError, ValueError):
        return 0.0


def _lignes(valeur: Any) -> Iterable[Mapping[str, Any]]:
    return [l for l in valeur if isinstance(l, Mapping)] if isinstance(valeur, list) else []


def retenues_du_bulletin_repris(payslip_data: Mapping[str, Any] | None) -> list[RetenueReprise]:
    """Prêts (primes non soumises négatives) et saisies (retenues sur le net) d'un bulletin repris."""
    donnees = payslip_data or {}
    retenues: list[RetenueReprise] = []
    for ligne in _lignes(donnees.get("primes_non_soumises")):
        libelle = str(ligne.get("libelle") or "").strip()
        if _montant(ligne) < 0 and _PRET.search(libelle):
            retenues.append(RetenueReprise("pret", libelle, abs(_montant(ligne))))
    for ligne in _lignes(donnees.get("retenues_sur_net")):
        libelle = str(ligne.get("libelle") or "").strip()
        if _montant(ligne) > 0 and _SAISIE.search(libelle):
            retenues.append(RetenueReprise("saisie", libelle, _montant(ligne)))
    return retenues


def message_retenue(retenue: RetenueReprise, libelle_mois: str) -> str:
    montant = f"{retenue.montant:.2f}".replace(".", ",")
    if retenue.nature == "pret":
        return (
            f"Retenue de {montant} € en {libelle_mois} chez l'ancien logiciel (« {retenue.libelle} ») "
            "et aucun prêt ouvert dans Martine : ouvrez-le avec son capital restant, sinon rien ne sera retenu."
        )
    return (
        f"Retenue de {montant} € en {libelle_mois} chez l'ancien logiciel (« {retenue.libelle} ») "
        "et aucune saisie ouverte dans Martine : posez-la d'après l'avis reçu, sinon rien ne partira au créancier."
    )
