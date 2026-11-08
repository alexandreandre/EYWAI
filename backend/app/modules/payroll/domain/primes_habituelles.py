"""Les primes que l'ancien logiciel versait chaque mois.

Martine ne calcule pas ces primes (présence, assiduité, poste…) : la RH les saisit.
Après la bascule, rien ne dit que la saisie est à faire : Martine rappelle celles
versées les deux derniers mois repris. Module pur.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

_PRIME = re.compile(r"\bprime\b|\bgratification\b|\bbonus\b|\bastreinte\b", re.IGNORECASE)
_CALCULEE_PAR_MARTINE = re.compile(r"anciennet", re.IGNORECASE)
_MOTS_VIDES = frozenset({"prime", "primes", "de", "du", "des", "la", "le", "les", "d", "l", "soumises"})


@dataclass(frozen=True)
class PrimeHabituelle:
    libelle: str
    montant: float


def _sans_accent(texte: str) -> str:
    return unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode().lower()


def _mots(libelle: str) -> frozenset[str]:
    return frozenset(m for m in re.findall(r"[a-z0-9]+", _sans_accent(libelle)) if m not in _MOTS_VIDES)


def _gain(ligne: Mapping[str, Any]) -> float:
    try:
        return float(ligne.get("gain") or 0)
    except (TypeError, ValueError):
        return 0.0


def _lignes(payslip_data: Mapping[str, Any] | None) -> Iterable[Mapping[str, Any]]:
    valeur = (payslip_data or {}).get("calcul_du_brut")
    return [l for l in valeur if isinstance(l, Mapping)] if isinstance(valeur, list) else []


def _primes(payslip_data: Mapping[str, Any] | None) -> dict[frozenset[str], PrimeHabituelle]:
    primes: dict[frozenset[str], PrimeHabituelle] = {}
    for ligne in _lignes(payslip_data):
        libelle = str(ligne.get("libelle") or "").strip()
        if _gain(ligne) > 0 and _PRIME.search(libelle) and not _CALCULEE_PAR_MARTINE.search(libelle):
            primes[_mots(libelle)] = PrimeHabituelle(libelle, _gain(ligne))
    return primes


def primes_habituelles(
    dernier: Mapping[str, Any] | None, avant_dernier: Mapping[str, Any] | None
) -> list[PrimeHabituelle]:
    """Les primes du dernier bulletin repris déjà présentes le mois d'avant."""
    d_avant = _primes(avant_dernier)
    return [prime for mots, prime in _primes(dernier).items() if mots in d_avant]


def deja_saisie(libelle: str, saisies: Iterable[str]) -> bool:
    """Une variable du mois porte déjà cette prime (mêmes mots, sans « prime de »)."""
    mots = _mots(libelle)
    return any(mots & _mots(nom) for nom in saisies)


def message_prime(prime: PrimeHabituelle, libelle_mois: str) -> str:
    montant = f"{prime.montant:.2f}".replace(".", ",")
    return (
        f"« {prime.libelle} » versée chaque mois par l'ancien logiciel "
        f"({montant} € en {libelle_mois}) et rien de saisi ce mois-ci. "
        "Saisissez-la dans Primes si elle continue : Martine ne la calcule pas."
    )
