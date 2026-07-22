"""Tests unitaires : classifieur de situation salarié vs DSN (avant paie).

Distingue actif normal / départ probable / absence prolongée / versement post-départ.
Domaine pur, sans DB.
"""

from datetime import date

import pytest

from app.modules.dsn_import.domain.employee_dsn_situation import (
    DsnSituation,
    DsnSituationSignals,
    classify_dsn_situation,
)

pytestmark = pytest.mark.unit

PERIOD_START = date(2026, 3, 1)
PERIOD_END = date(2026, 3, 31)
WORKING_DAYS = 22


def _signals(**overrides):
    base = dict(
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        working_days_in_period=WORKING_DAYS,
        present_in_dsn=True,
        has_fin_contrat=False,
        fin_contrat_last_working_day=None,
        exit_last_working_day=None,
        absence_days_in_period=0,
        period_brut=2000.0,
        period_net=1550.0,
    )
    base.update(overrides)
    return DsnSituationSignals(**base)


def test_active_normal_no_recommendation():
    res = classify_dsn_situation(_signals())
    assert res.situation == DsnSituation.ACTIVE_NORMAL
    assert res.recommendation is None


def test_partial_absence_stays_active_normal():
    # Une semaine d'arrêt ≠ absence prolongée.
    res = classify_dsn_situation(_signals(absence_days_in_period=5, period_brut=1500.0))
    assert res.situation == DsnSituation.ACTIVE_NORMAL


def test_full_month_arret_zero_pay_is_prolonged_absence():
    # Profil OSMANI mars : arrêt ~tout le mois, brut ≈ 0, pas de fin de contrat.
    res = classify_dsn_situation(
        _signals(absence_days_in_period=20, period_brut=0.0, period_net=-234.59)
    )
    assert res.situation == DsnSituation.PROLONGED_ABSENCE
    assert res.recommendation is not None
    assert res.evidence["absence_coverage"] >= 0.8


def test_full_month_arret_with_partial_maintien_is_prolonged_absence():
    # Profil OSMANI avril : arrêt tout le mois mais maintien partiel (brut > 0).
    # La couverture d'arrêt suffit — indépendante du brut.
    res = classify_dsn_situation(
        _signals(absence_days_in_period=22, period_brut=900.0, period_net=766.45)
    )
    assert res.situation == DsnSituation.PROLONGED_ABSENCE


def test_fin_contrat_in_period_is_departure():
    res = classify_dsn_situation(
        _signals(has_fin_contrat=True, fin_contrat_last_working_day=date(2026, 3, 15))
    )
    assert res.situation == DsnSituation.LIKELY_DEPARTURE
    assert res.recommendation is not None


def test_absent_from_dsn_is_departure():
    res = classify_dsn_situation(_signals(present_in_dsn=False, period_brut=None, period_net=None))
    assert res.situation == DsnSituation.LIKELY_DEPARTURE


def test_exit_before_period_but_present_is_post_exit_payment():
    # Sortie EYWAI déjà enregistrée avant la période, mais réapparaît dans la DSN
    # (participation / solde) → versement post-départ, pas une paie récurrente.
    res = classify_dsn_situation(
        _signals(exit_last_working_day=date(2026, 1, 31), period_brut=0.0, period_net=2974.29)
    )
    assert res.situation == DsnSituation.POST_EXIT_PAYMENT
    assert res.recommendation is not None


def test_prior_fin_contrat_in_dsn_is_post_exit_payment():
    # Fin de contrat DSN datée d'une période antérieure + réapparition.
    res = classify_dsn_situation(
        _signals(
            has_fin_contrat=True,
            fin_contrat_last_working_day=date(2025, 12, 31),
            period_brut=0.0,
        )
    )
    assert res.situation == DsnSituation.POST_EXIT_PAYMENT


def test_zero_working_days_does_not_crash():
    res = classify_dsn_situation(
        _signals(working_days_in_period=0, absence_days_in_period=0, period_brut=2000.0)
    )
    assert res.situation == DsnSituation.ACTIVE_NORMAL


def test_evidence_exposes_signals():
    res = classify_dsn_situation(_signals(absence_days_in_period=20, period_brut=0.0))
    assert res.evidence["period_brut"] == 0.0
    assert res.evidence["absence_days_in_period"] == 20
    assert "situation" not in res.evidence  # évidence = données brutes, pas la conclusion
