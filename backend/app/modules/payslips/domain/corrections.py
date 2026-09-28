"""Ce qui se corrige sur un bulletin : ses heures sup et ses primes du mois.

Un bulletin ne se corrige plus en retouchant ses lignes. Les montants retouchés
à la main laissaient les bases, les cotisations, le net et les cumuls de
l'ancien calcul (audit du 28/09). On corrige ses variables du mois, puis le
moteur recalcule le bulletin en entier. Le reste (planning, absences, salaire,
primes fixes) se corrige à sa source, sur son propre écran.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.modules.payslips.domain.heures_sup import quantites_heures_sup_conjoncturelles
from app.modules.payslips.domain.primes_editees import (
    DiffPrimes,
    primes_saisies_du_bulletin,
)

_TOLERANCE = 0.005


@dataclass(frozen=True)
class CorrectionsBulletin:
    #: (heures au premier palier, heures au second palier) déclarées depuis le
    #: bulletin ; elles priment sur le planning, même nulles.
    heures_sup: tuple[float, float] | None = None
    #: Retirer les heures sup déclarées depuis le bulletin : le planning refait foi.
    revenir_au_planning: bool = False
    primes: DiffPrimes = DiffPrimes()

    @property
    def change_des_variables(self) -> bool:
        return (
            self.heures_sup is not None
            or self.revenir_au_planning
            or not self.primes.vide
        )


def _heures(valeur: float) -> str:
    texte = f"{round(float(valeur), 2):.2f}".rstrip("0").rstrip(".")
    return texte.replace(".", ",")


def _euros(valeur: float) -> str:
    return f"{float(valeur):.2f}".replace(".", ",") + " €"


def resume_des_corrections(corrections: CorrectionsBulletin) -> str:
    """Une phrase pour l'historique quand la RH n'en a pas écrit."""
    parties: list[str] = []
    if corrections.revenir_au_planning:
        parties.append("heures sup du planning")
    if corrections.heures_sup is not None:
        hs25, hs50 = corrections.heures_sup
        parties.append(f"heures sup {_heures(hs25)} h à 25 % et {_heures(hs50)} h à 50 %")
    for prime in corrections.primes.ajoutees:
        parties.append(f"prime ajoutée « {prime.get('name')} » {_euros(prime.get('amount') or 0)}")
    if corrections.primes.modifiees:
        n = len(corrections.primes.modifiees)
        parties.append(f"{n} prime{'s' if n > 1 else ''} corrigée{'s' if n > 1 else ''}")
    if corrections.primes.retirees:
        n = len(corrections.primes.retirees)
        parties.append(f"{n} prime{'s' if n > 1 else ''} retirée{'s' if n > 1 else ''}")
    if not parties:
        return "Notes modifiées"
    texte = ", ".join(parties)
    return texte[0].upper() + texte[1:]


def _declarees(payslip_data: dict[str, Any] | None) -> tuple[float, float] | None:
    declarees = (payslip_data or {}).get("heures_sup_declarees")
    if not isinstance(declarees, dict):
        return None
    return (
        round(float(declarees.get("hs25") or 0.0), 2),
        round(float(declarees.get("hs50") or 0.0), 2),
    )


def _proches(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return all(abs(x - y) <= _TOLERANCE for x, y in zip(a, b))


def _heures_pour_revenir(
    courant: dict[str, Any] | None, cible: dict[str, Any] | None
) -> tuple[float, float] | None:
    """Les heures sup à déclarer pour retrouver celles de la version cible.

    Une version récente dit si ses heures ont été déclarées au bulletin ; une
    plus ancienne ne le dit pas, et on reprend alors les quantités qu'elle
    imprimait. Rien à déclarer quand elles sont déjà celles du bulletin.
    """
    cible_declarees = _declarees(cible)
    if cible_declarees is not None:
        courant_declarees = _declarees(courant)
        if courant_declarees is not None and _proches(cible_declarees, courant_declarees):
            return None
        return cible_declarees
    heures_cible = quantites_heures_sup_conjoncturelles(cible)
    heures_courant = quantites_heures_sup_conjoncturelles(courant)
    if _proches(heures_cible, heures_courant):
        return None
    return (round(heures_cible[0], 2), round(heures_cible[1], 2))


def corrections_pour_revenir(
    courant: dict[str, Any] | None,
    cible: dict[str, Any] | None,
    *,
    saisies_existantes: set[str] | frozenset[str] = frozenset(),
) -> CorrectionsBulletin:
    """Ce qu'il faut corriger pour que le bulletin retrouve les heures sup et
    les primes saisies d'une version antérieure.

    Restaurer ne recopie plus l'ancien bulletin (ses cotisations et son net
    n'auraient pas suivi) : on revient à ses variables, et le moteur recalcule.
    Une prime de la version dont la saisie a disparu est recréée, avec le régime
    de la section où elle était imprimée ; `saisies_existantes` évite de recréer
    une saisie encore présente dans le mois.
    """
    primes_courant = primes_saisies_du_bulletin(courant)
    primes_cible = primes_saisies_du_bulletin(cible)

    retirees = tuple(sid for sid in primes_courant if sid not in primes_cible)
    modifiees: list[tuple[str, float]] = []
    ajoutees: list[dict[str, Any]] = []
    for sid, prime in primes_cible.items():
        if sid in primes_courant:
            if abs(prime.montant - primes_courant[sid].montant) > _TOLERANCE:
                modifiees.append((sid, prime.montant))
        elif sid in saisies_existantes:
            modifiees.append((sid, prime.montant))
        else:
            ajoutees.append(
                {
                    "name": prime.libelle,
                    "amount": prime.montant,
                    "is_socially_taxed": prime.soumise,
                    "is_taxable": prime.soumise,
                    "catalog_prime_id": None,
                }
            )
    return CorrectionsBulletin(
        heures_sup=_heures_pour_revenir(courant, cible),
        primes=DiffPrimes(tuple(ajoutees), tuple(modifiees), retirees),
    )
