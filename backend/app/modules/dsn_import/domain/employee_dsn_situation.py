"""Classifieur de situation d'un salarié face à la DSN de la période (avant paie).

Distingue quatre situations, à partir de signaux DSN + contexte EYWAI, sans aucune
dépendance base / FastAPI (domaine pur, testable) :

- ``ACTIVE_NORMAL``    : salarié en activité, paie normale attendue ;
- ``LIKELY_DEPARTURE`` : fin de contrat DSN sur la période, ou individu disparu de la DSN ;
- ``PROLONGED_ABSENCE``: individu déclaré, sans fin de contrat, mais arrêt/suspension
                         couvrant l'essentiel du mois (arrêt maladie longue durée, congé
                         sans solde…) — la paie ne doit pas être un salaire plein ;
- ``POST_EXIT_PAYMENT``: sortie déjà connue (exit EYWAI ou fin de contrat DSN antérieure)
                         mais réapparition dans la DSN — versement ponctuel (participation,
                         solde de tout compte), pas une paie récurrente.

Aucune décision n'est appliquée : la fonction produit une recommandation à présenter au
gestionnaire avant de lancer la paie.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any, Dict, Optional

# Part des jours ouvrés du mois couverte par un arrêt/suspension au-delà de laquelle on
# considère l'absence comme « quasi tout le mois » (absence prolongée).
FULL_MONTH_ABSENCE_RATIO = 0.8

# Brut mensuel en-deçà duquel on considère la rémunération comme « quasi nulle ».
NEAR_ZERO_BRUT = 50.0


class DsnSituation(str, Enum):
    ACTIVE_NORMAL = "active_normal"
    LIKELY_DEPARTURE = "likely_departure"
    PROLONGED_ABSENCE = "prolonged_absence"
    POST_EXIT_PAYMENT = "post_exit_payment"


@dataclass(frozen=True)
class DsnSituationSignals:
    """Signaux d'un salarié pour une période de paie.

    ``absence_days_in_period`` et ``working_days_in_period`` doivent être exprimés dans la
    même unité (jours ouvrés de la période) pour que le ratio de couverture ait un sens.
    """

    period_start: date
    period_end: date
    working_days_in_period: int
    present_in_dsn: bool = True
    has_fin_contrat: bool = False
    fin_contrat_last_working_day: Optional[date] = None
    exit_last_working_day: Optional[date] = None
    absence_days_in_period: int = 0
    period_brut: Optional[float] = None
    period_net: Optional[float] = None


@dataclass(frozen=True)
class DsnSituationResult:
    situation: DsnSituation
    recommendation: Optional[str]
    evidence: Dict[str, Any]


def _absence_coverage(signals: DsnSituationSignals) -> float:
    if signals.working_days_in_period <= 0:
        return 0.0
    return min(1.0, signals.absence_days_in_period / signals.working_days_in_period)


def _known_exit_before_period(signals: DsnSituationSignals) -> Optional[date]:
    """Date de sortie déjà connue et antérieure au début de la période, s'il y en a une."""
    candidates = [
        d
        for d in (signals.exit_last_working_day, signals.fin_contrat_last_working_day)
        if d is not None and d < signals.period_start
    ]
    return min(candidates) if candidates else None


def _fmt(value: Optional[date]) -> Optional[str]:
    return value.isoformat() if value else None


def classify_dsn_situation(signals: DsnSituationSignals) -> DsnSituationResult:
    coverage = _absence_coverage(signals)
    brut_near_zero = signals.period_brut is not None and signals.period_brut <= NEAR_ZERO_BRUT
    evidence: Dict[str, Any] = {
        "present_in_dsn": signals.present_in_dsn,
        "has_fin_contrat": signals.has_fin_contrat,
        "fin_contrat_last_working_day": _fmt(signals.fin_contrat_last_working_day),
        "exit_last_working_day": _fmt(signals.exit_last_working_day),
        "absence_days_in_period": signals.absence_days_in_period,
        "working_days_in_period": signals.working_days_in_period,
        "absence_coverage": round(coverage, 3),
        "period_brut": signals.period_brut,
        "period_net": signals.period_net,
    }

    # 1) Versement postérieur au départ : une sortie est déjà connue AVANT la période,
    #    et l'individu réapparaît pourtant dans la DSN.
    prior_exit = _known_exit_before_period(signals)
    if signals.present_in_dsn and prior_exit is not None:
        return DsnSituationResult(
            situation=DsnSituation.POST_EXIT_PAYMENT,
            recommendation=(
                f"Sortie déjà enregistrée au {prior_exit.isoformat()} : la DSN de la période "
                "ne contient qu'un versement postérieur au départ (participation, solde de "
                "tout compte…). Traitez-le comme un versement ponctuel, ne générez pas de "
                "bulletin de paie récurrent."
            ),
            evidence=evidence,
        )

    # 2) Fin de contrat DSN tombant sur la période -> départ probable à finaliser.
    if (
        signals.has_fin_contrat
        and signals.fin_contrat_last_working_day is not None
        and signals.fin_contrat_last_working_day <= signals.period_end
    ):
        return DsnSituationResult(
            situation=DsnSituation.LIKELY_DEPARTURE,
            recommendation=(
                f"Fin de contrat déclarée en DSN au "
                f"{signals.fin_contrat_last_working_day.isoformat()}. Clôturez le départ "
                "(solde de tout compte) et retirez le salarié de la paie récurrente."
            ),
            evidence=evidence,
        )

    # 3) Individu absent de la DSN alors qu'il est actif en base -> départ suspecté.
    if not signals.present_in_dsn:
        return DsnSituationResult(
            situation=DsnSituation.LIKELY_DEPARTURE,
            recommendation=(
                "Salarié actif en base mais absent de la DSN de la période : sortie probable. "
                "Vérifiez son départ avant de lancer la paie, ou complétez la DSN."
            ),
            evidence=evidence,
        )

    # 4) Présent, sans fin de contrat, mais arrêt/suspension couvrant l'essentiel du mois.
    if coverage >= FULL_MONTH_ABSENCE_RATIO:
        pay_note = (
            " La rémunération DSN est quasi nulle."
            if brut_near_zero
            else " Un maintien partiel est versé."
        )
        return DsnSituationResult(
            situation=DsnSituation.PROLONGED_ABSENCE,
            recommendation=(
                "Absence prolongée détectée : un arrêt/suspension couvre l'essentiel du mois "
                f"({signals.absence_days_in_period}/{signals.working_days_in_period} jours "
                f"ouvrés), sans fin de contrat.{pay_note} Vérifiez que l'arrêt est bien saisi "
                "avant de générer la paie ; ne produisez pas un bulletin de salaire plein."
            ),
            evidence=evidence,
        )

    return DsnSituationResult(
        situation=DsnSituation.ACTIVE_NORMAL,
        recommendation=None,
        evidence=evidence,
    )
