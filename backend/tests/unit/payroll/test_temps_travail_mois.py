"""Tests unitaires — temps retenu mensuel (prorata prime d'ancienneté)."""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.temps_travail_mois import compute_temps_retenu_mois


def _cal_travail(heures: float, *, jour: int = 1) -> dict:
    return {
        "date_complete": f"2026-04-{jour:02d}",
        "type": "travail",
        "heures": heures,
    }


def _cal_arret(jour: int) -> dict:
    return {
        "date_complete": f"2026-04-{jour:02d}",
        "type": "arret_maladie",
        "heures": 0,
    }


class TestTempsTravailMois:
    def test_mode_none_ratio_un(self):
        result = compute_temps_retenu_mois(
            mode="none",
            calendrier_saisie=[],
            duree_hebdo=35.0,
            date_debut=date(2026, 4, 1),
            date_fin=date(2026, 4, 30),
        )
        assert result.ratio == 1.0

    def test_heures_contrat_plein_mois(self):
        heures_jour = 151.67 / 22
        cal = [_cal_travail(heures_jour, jour=d) for d in range(1, 23)]
        result = compute_temps_retenu_mois(
            mode="heures_contrat",
            calendrier_saisie=cal,
            duree_hebdo=35.0,
            date_debut=date(2026, 4, 1),
            date_fin=date(2026, 4, 30),
        )
        assert result.reference == 151.67
        assert result.temps_retenu == pytest.approx(151.67, abs=0.02)
        assert result.ratio == pytest.approx(1.0, abs=0.01)

    def test_heures_contrat_avec_hs(self):
        """153,77 h sur 151,67 h de référence (cas BONNET Excel)."""
        heures_jour = 153.77 / 22
        cal = [_cal_travail(heures_jour, jour=d) for d in range(1, 23)]
        result = compute_temps_retenu_mois(
            mode="heures_contrat",
            calendrier_saisie=cal,
            duree_hebdo=35.0,
            date_debut=date(2026, 4, 1),
            date_fin=date(2026, 4, 30),
        )
        assert result.temps_retenu == 153.77
        assert result.ratio == round(153.77 / 151.67, 6)

    def test_heures_contrat_zero_sans_maintien(self):
        result = compute_temps_retenu_mois(
            mode="heures_contrat",
            calendrier_saisie=[],
            duree_hebdo=35.0,
            date_debut=date(2026, 4, 1),
            date_fin=date(2026, 4, 30),
        )
        assert result.ratio == 0.0

    def test_maintien_compte_heures_journalieres(self):
        cal = [_cal_travail(7.0, jour=1), _cal_arret(2), _cal_arret(3)]
        result = compute_temps_retenu_mois(
            mode="heures_contrat",
            calendrier_saisie=cal,
            duree_hebdo=35.0,
            date_debut=date(2026, 4, 1),
            date_fin=date(2026, 4, 30),
            jours_maintien={2, 3},
            maladie_si_maintien=True,
        )
        assert result.temps_retenu == 7.0 + 14.0
        assert result.detail["heures_maintien"] == 14.0

    def test_maintien_non_compte_sans_jours_maintien(self):
        cal = [_cal_arret(2), _cal_arret(3)]
        result = compute_temps_retenu_mois(
            mode="heures_contrat",
            calendrier_saisie=cal,
            duree_hebdo=35.0,
            date_debut=date(2026, 4, 1),
            date_fin=date(2026, 4, 30),
            jours_maintien=set(),
        )
        assert result.ratio == 0.0

    def test_sans_pointage_policy_plein_mois(self):
        result = compute_temps_retenu_mois(
            mode="heures_contrat",
            calendrier_saisie=[],
            duree_hebdo=35.0,
            date_debut=date(2026, 4, 1),
            date_fin=date(2026, 4, 30),
            sans_pointage_policy="plein_mois",
            actual_hours_raw=[{"jour": 1, "type": "sans_pointage"}],
        )
        assert result.ratio == 1.0
        assert result.detail.get("sans_pointage") is True

    def test_jours_forfait(self):
        cal = [
            {"date_complete": f"2026-04-{d:02d}", "type": "travail"}
            for d in range(1, 19)
        ]
        result = compute_temps_retenu_mois(
            mode="jours_forfait",
            calendrier_saisie=cal,
            duree_hebdo=35.0,
            date_debut=date(2026, 4, 1),
            date_fin=date(2026, 4, 30),
        )
        assert result.temps_retenu == 18.0
        assert 0 < result.ratio <= 1.0
