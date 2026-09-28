"""Sans maintien de salaire sur la période, pas de subrogation.

Colorplast, août 2026 : la société ne maintient pas le salaire (maintien légal
désactivé, comme le fait Quadra) et sa subrogation est réglée « quand il y a
maintien ». L'arrêt saisi à l'écran arrivait pourtant avec la subrogation
active : 393,18 € d'IJSS entraient au net du bulletin, alors que la caisse les
verse directement à la salariée (le bulletin Quadra n'en porte aucune), et le
complément employeur sortait négatif.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.maintien_salaire_service import calculer_maintien

from .test_maintien_corrections import _ctx, _settings

pytestmark = pytest.mark.unit

AOUT = (date(2026, 8, 1), date(2026, 8, 31))


def _arret(**extra):
    return {
        "arret_type": "maladie_simple",
        "date_debut": "2026-08-17",
        "date_fin": "2026-09-03",
        "subrogation_active": True,
        "nombre_enfants": 0,
        "salaire_periode_reelle": 0.0,
        **extra,
    }


def test_sans_maintien_la_subrogation_tombe_et_les_ijss_restent_hors_bulletin():
    r = calculer_maintien(
        _arret(), _ctx(salaire_mensuel=2278.11), _settings(apply_legal_maintenance=False,
                                                           employer_waiting_days=3),
        *AOUT,
    )
    assert r["ijss"]["ijss_theorique"] > 0
    assert r["maintien"]["maintien_cible"] == 0
    assert r["subrogation_active"] is False
    assert r["maintien"]["maintien_verse"] == 0
    assert "IJSS versées directement au salarié" in r["alertes"]


def test_avec_maintien_la_subrogation_demandee_reste_active():
    r = calculer_maintien(_arret(), _ctx(), _settings(employer_waiting_days=3), *AOUT)
    assert r["maintien"]["maintien_cible"] > 0
    assert r["subrogation_active"] is True
    assert r["maintien"]["maintien_verse"] == pytest.approx(
        r["maintien"]["maintien_cible"] - r["ijss"]["ijss_theorique"], abs=0.01
    )


def test_sans_subrogation_demandee_rien_ne_change():
    r = calculer_maintien(
        _arret(subrogation_active=False), _ctx(),
        _settings(apply_legal_maintenance=False), *AOUT,
    )
    assert r["subrogation_active"] is False
    assert r["maintien"]["maintien_verse"] == 0
