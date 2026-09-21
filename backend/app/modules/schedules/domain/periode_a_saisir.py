"""La période à saisir pour la paie d'un mois — règles pures.

Le bulletin porte le mois civil ; les heures (heures sup, paniers) suivent la
fenêtre des variables (`shared.domain.periode_variables`). Le moteur lit
l'union des deux (`payslip_run_heures.creer_calendrier_etendu`). Le contrôle
amont doit juger la même union : sinon il bloque des jours que le moteur ne
lit pas (27–31/07 chez Colorplast, juillet 2026) et se tait sur ceux qu'il lit
(22–30/06). Constat du 20/09/2026, dossier Michel BUGNY.

Module pur : l'appelant fournit la fenêtre, les calendriers et le contrat.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Iterable, Literal, Mapping

from app.modules.schedules.domain.ecart_rules import is_day_ready_for_payroll

Motif = Literal["planning_absent", "prevu_sans_reel", "prevu_sans_heures", "reel_a_zero"]
#: (année, mois) → (calendrier prévu, calendrier réel) tels que stockés.
Calendriers = Mapping[tuple[int, int], tuple[list[dict[str, Any]], list[dict[str, Any]]]]


@dataclass(frozen=True)
class JourASaisir:
    jour: date
    #: Dans la fenêtre des variables : le moteur lira ce jour pour les heures.
    bloquant: bool
    motif: Motif


@dataclass(frozen=True)
class PeriodeASaisir:
    debut: date
    fin: date
    fenetre: tuple[date, date]
    mois_civil: tuple[date, date]
    manquants: tuple[JourASaisir, ...]
    #: D'où vient la fenêtre : « regle » (société) ou « manuel » (surcharge du mois).
    origine: str = "regle"

    @property
    def bloquants(self) -> tuple[JourASaisir, ...]:
        return tuple(j for j in self.manquants if j.bloquant)

    @property
    def informatifs(self) -> tuple[JourASaisir, ...]:
        return tuple(j for j in self.manquants if not j.bloquant)

    @property
    def statut(self) -> str:
        """`a_saisir` dès qu'un jour de la fenêtre manque, `saisi` sinon."""
        return "a_saisir" if self.bloquants else "saisi"


def _motif(planned: dict[str, Any] | None, actual: dict[str, Any] | None) -> Motif:
    """Pourquoi un jour n'est pas prêt — la décision, elle, reste à `is_day_ready_for_payroll`."""
    if not planned:
        return "planning_absent"
    if planned.get("heures_prevues") is None:
        return "prevu_sans_heures"
    if not actual or actual.get("heures_faites") is None:
        return "prevu_sans_reel"
    return "reel_a_zero"


def _par_jour(entrees: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for entree in entrees:
        try:
            out[int(entree["jour"])] = entree
        except (KeyError, TypeError, ValueError):
            continue
    return out


def periode_a_saisir(
    *,
    annee: int,
    mois: int,
    fenetre: tuple[date, date],
    calendriers: Calendriers,
    date_entree: date | None = None,
    date_sortie: date | None = None,
    forfait: bool = False,
    origine: str = "regle",
) -> PeriodeASaisir:
    """Les jours manquants sur l'union du mois civil et de la fenêtre des variables.

    - Un forfait jour est jugé sur le mois civil seul : présence en jours, pas
      d'heures, la fenêtre des variables ne le concerne pas.
    - Rien n'est attendu avant l'entrée ni après la sortie, comme le moteur qui
      écarte tout événement hors contrat.
    - Un mois sans ligne de planning attend ses jours ouvrés (lundi à vendredi),
      pas le week-end.
    """
    mois_civil = (date(annee, mois, 1), date(annee, mois, calendar.monthrange(annee, mois)[1]))
    if forfait:
        fenetre = mois_civil
    debut, fin = min(mois_civil[0], fenetre[0]), max(mois_civil[1], fenetre[1])
    par_mois = {cle: (_par_jour(prevu), _par_jour(reel)) for cle, (prevu, reel) in calendriers.items()}

    manquants: list[JourASaisir] = []
    jour = debut
    while jour <= fin:
        hors_contrat = (date_entree is not None and jour < date_entree) or (
            date_sortie is not None and jour > date_sortie
        )
        if not hors_contrat:
            dans_fenetre = fenetre[0] <= jour <= fenetre[1]
            planning = par_mois.get((jour.year, jour.month))
            if planning is None:
                if jour.weekday() < 5:
                    manquants.append(JourASaisir(jour, dans_fenetre, "planning_absent"))
            else:
                planned, actual = planning[0].get(jour.day), planning[1].get(jour.day)
                if not is_day_ready_for_payroll(planned, actual, forfait=forfait):
                    manquants.append(JourASaisir(jour, dans_fenetre, _motif(planned, actual)))
        jour += timedelta(days=1)
    return PeriodeASaisir(debut, fin, fenetre, mois_civil, tuple(manquants), origine)


def plages(jours: Iterable[date]) -> list[tuple[date, date]]:
    """Regroupe des dates triées en plages de jours consécutifs."""
    groupes: list[tuple[date, date]] = []
    for jour in sorted(jours):
        if groupes and jour == groupes[-1][1] + timedelta(days=1):
            groupes[-1] = (groupes[-1][0], jour)
        else:
            groupes.append((jour, jour))
    return groupes


def libelle_plages(jours: Iterable[date]) -> str:
    """« 22/06–26/06, 29/06–30/06 » — pour un message qui nomme ce qui manque."""
    return ", ".join(
        f"{a:%d/%m}" if a == b else f"{a:%d/%m}–{b:%d/%m}" for a, b in plages(jours)
    )


__all__ = ["JourASaisir", "PeriodeASaisir", "libelle_plages", "periode_a_saisir", "plages"]
