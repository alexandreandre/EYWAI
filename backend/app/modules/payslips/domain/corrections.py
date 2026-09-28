"""Ce qui se corrige sur un bulletin : ses heures sup et ses primes du mois.

Un bulletin ne se corrige plus en retouchant ses lignes. Les montants retouchés
à la main laissaient les bases, les cotisations, le net et les cumuls de
l'ancien calcul (audit du 28/09). On corrige ses variables du mois, puis le
moteur recalcule le bulletin en entier. Le reste (planning, absences, salaire,
primes fixes) se corrige à sa source, sur son propre écran.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.payslips.domain.primes_editees import DiffPrimes


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
