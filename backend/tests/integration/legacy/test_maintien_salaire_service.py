"""
Tests unitaires — maintien_salaire_service (Ticket 3).

Contexte paie mocké (duck typing), sans appel Supabase.
"""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.modules.payroll.engine.maintien_salaire_service import (
    calculer_maintien,
    calculer_regularisation_at,
    _calculer_carence,
    _qualifier_arret,
)


def _ctx(
    salaire_mensuel: float = 2500.0,
    pss_annuel: float = 48000.0,
    date_entree: str = "2021-01-15",
) -> SimpleNamespace:
    return SimpleNamespace(
        salaire_base_mensuel=salaire_mensuel,
        baremes={"pss": {"annuel": pss_annuel}},
        contrat={"contrat": {"date_entree": date_entree}},
    )


def _settings_base(**overrides):
    base = {
        "apply_legal_maintenance": True,
        "min_seniority_months": 12,
        "employer_waiting_days": 7,
        "seniority_extension_enabled": False,
        "remove_employer_waiting": False,
        "annual_unique_waiting": False,
        "maintain_100_percent": False,
        "differentiated_at_illness": False,
        "maintain_by_category": False,
        "no_seniority_condition": False,
        "custom_duration_days": None,
        "provident_relay_days": None,
    }
    base.update(overrides)
    return base


class TestQualifierArret:
    def test_maladie_simple_carence_3_taux_50(self):
        q = _qualifier_arret("maladie_simple")
        assert q["carence_ss_jours"] == 3
        assert q["taux_ijss_base"] == 0.50
        assert q["est_at_mp"] is False
        assert q["est_ald"] is False

    def test_at_carence_0_taux_60(self):
        q = _qualifier_arret("accident_travail")
        assert q["carence_ss_jours"] == 0
        assert q["taux_ijss_base"] == 0.60
        assert q["est_at_mp"] is True


class TestCarenceContinuite:
    def test_fractionne_moins_48h_pas_nouvelle_carence(self):
        d0 = date(2025, 6, 10)
        qual = _qualifier_arret("maladie_simple")
        settings = _settings_base()
        arret = {"date_dernier_arret": (d0 - timedelta(days=1)).isoformat()}
        c = _calculer_carence(arret, qual, settings, d0, [])
        assert c["est_continuite"] is True
        assert c["carence_ss_jours"] == 0
        assert c["carence_employeur_jours"] == 0

    def test_fractionne_plus_48h_nouvelle_carence(self):
        d0 = date(2025, 6, 10)
        qual = _qualifier_arret("maladie_simple")
        settings = _settings_base()
        arret = {"date_dernier_arret": (d0 - timedelta(days=50)).isoformat()}
        c = _calculer_carence(arret, qual, settings, d0, [])
        assert c["est_continuite"] is False
        assert c["carence_ss_jours"] == 3
        assert c["carence_employeur_jours"] == 7


class TestCalculerMaintienScenarios:
    """Scénarios bout-en-bout via calculer_maintien."""

    def test_maladie_simple_subrogation_anciennete_ok(self):
        p_debut, p_fin = date(2025, 6, 1), date(2025, 6, 30)
        arret = {
            "arret_type": "maladie_simple",
            "date_debut": "2025-06-01",
            "date_fin": "2025-06-15",
            "subrogation_active": True,
            "nombre_enfants": 0,
            "is_temps_partiel": False,
            "quotite_temps_partiel": 1.0,
            "salaire_periode_reelle": 0.0,
        }
        r = calculer_maintien(
            arret,
            _ctx(),
            _settings_base(),
            p_debut,
            p_fin,
        )
        assert r["qualification"]["carence_ss_jours"] == 3
        assert r["ijss"]["nb_jours_indemnises"] > 0
        assert r["maintien"]["maintien_applicable"] is True
        assert r["subrogation_active"] is True
        assert r["maintien"]["maintien_verse"] == pytest.approx(
            r["maintien"]["maintien_cible"] - r["ijss"]["ijss_theorique"], rel=1e-2, abs=0.05
        )

    def test_at_subrogation_carence_ss_zero(self):
        p_debut, p_fin = date(2025, 6, 1), date(2025, 7, 31)
        arret = {
            "arret_type": "accident_travail",
            "date_debut": "2025-06-01",
            "date_fin": "2025-07-15",
            "subrogation_active": True,
            "nombre_enfants": 0,
            "is_temps_partiel": False,
            "quotite_temps_partiel": 1.0,
            "salaire_periode_reelle": 0.0,
        }
        r = calculer_maintien(arret, _ctx(), _settings_base(), p_debut, p_fin)
        assert r["carence"]["carence_ss_jours"] == 0
        assert r["qualification"]["est_at_mp"] is True
        assert r["ijss"]["nb_jours_indemnises"] > 28
        assert r["ijss"]["taux_applique"] > 0.60

    def test_anciennete_insuffisante(self):
        p_debut, p_fin = date(2025, 6, 1), date(2025, 6, 30)
        arret = {
            "arret_type": "maladie_simple",
            "date_debut": "2025-06-10",
            "date_fin": "2025-06-20",
            "subrogation_active": True,
            "nombre_enfants": 0,
            "salaire_periode_reelle": 0.0,
        }
        ctx = _ctx(date_entree="2025-03-01")
        r = calculer_maintien(
            arret,
            ctx,
            _settings_base(min_seniority_months=12, no_seniority_condition=False),
            p_debut,
            p_fin,
        )
        assert r["maintien"]["maintien_applicable"] is False
        assert any("Ancienneté insuffisante" in a for a in r["alertes"])

    def test_duree_maintien_legale_selon_anciennete(self):
        # Ancienneté 4 ans (2021-01 → 2025-01) → tranche 1-5 ans : 30 j + 30 j = 60 j.
        p_debut, p_fin = date(2025, 1, 1), date(2025, 12, 31)
        arret = {
            "arret_type": "maladie_simple",
            "date_debut": "2025-01-01",
            "date_fin": "2025-06-30",
            "subrogation_active": True,
            "nombre_enfants": 0,
            "salaire_periode_reelle": 0.0,
        }
        r = calculer_maintien(arret, _ctx(), _settings_base(), p_debut, p_fin)
        # 30 j à 90 % + 30 j à 66,66 % = 60 jours maintenus, après 7 j de carence.
        assert r["maintien"]["duree_maintien_legale_jours"] == 60
        assert r["maintien"]["nb_jours_maintien"] == 60
        assert any(
            "Durée maximale du maintien employeur atteinte" in a for a in r["alertes"]
        )

    def test_duree_maintien_legale_anciennete_elevee_180j(self):
        # Ancienneté > 31 ans → 90 j + 90 j = 180 jours, plafond maximal.
        p_debut, p_fin = date(2025, 1, 1), date(2025, 12, 31)
        arret = {
            "arret_type": "maladie_simple",
            "date_debut": "2025-01-01",
            "date_fin": "2025-12-31",
            "subrogation_active": True,
            "nombre_enfants": 0,
            "salaire_periode_reelle": 0.0,
        }
        ctx = _ctx(date_entree="1985-01-01")
        r = calculer_maintien(arret, ctx, _settings_base(), p_debut, p_fin)
        assert r["maintien"]["duree_par_taux_jours"] == 90
        assert r["maintien"]["duree_maintien_legale_jours"] == 180
        assert r["maintien"]["nb_jours_maintien"] == 180

    def test_convention_moins_favorable_que_legal(self):
        p_debut, p_fin = date(2025, 6, 1), date(2025, 6, 30)
        arret = {
            "arret_type": "maladie_simple",
            "date_debut": "2025-06-01",
            "date_fin": "2025-06-10",
            "subrogation_active": True,
            "nombre_enfants": 0,
            "salaire_periode_reelle": 0.0,
        }
        settings = _settings_base(taux_maintien_conventionnel=0.5)
        r = calculer_maintien(arret, _ctx(), settings, p_debut, p_fin)
        assert r["maintien"]["conflit_convention"] is True
        assert any("conventionnelle moins favorable" in a for a in r["alertes"])

    def test_sans_subrogation_pas_deduction_ijss(self):
        p_debut, p_fin = date(2025, 6, 1), date(2025, 6, 30)
        arret = {
            "arret_type": "maladie_simple",
            "date_debut": "2025-06-05",
            "date_fin": "2025-06-20",
            "subrogation_active": False,
            "nombre_enfants": 0,
            "salaire_periode_reelle": 0.0,
        }
        r = calculer_maintien(arret, _ctx(), _settings_base(), p_debut, p_fin)
        assert r["maintien"]["maintien_verse"] == pytest.approx(
            r["maintien"]["maintien_cible"], rel=1e-6
        )
        assert any("IJSS versées directement" in a for a in r["alertes"])

    def test_t11_mi_temps_therapeutique_double_ligne(self):
        p_debut, p_fin = date(2025, 6, 1), date(2025, 6, 30)
        arret = {
            "arret_type": "mi_temps_therapeutique",
            "date_debut": "2025-06-05",
            "date_fin": "2025-06-15",
            "subrogation_active": True,
            "nombre_enfants": 0,
            "is_temps_partiel": False,
            "quotite_temps_partiel": 0.5,
            "salaire_periode_reelle": 0.0,
        }
        r = calculer_maintien(arret, _ctx(), _settings_base(), p_debut, p_fin)
        assert r.get("double_ligne_bulletin") is True
        assert r["salaire_partiel_maintenu"] == pytest.approx(1250.0, rel=1e-3)
        assert r["ijss"]["is_mi_temps_therapeutique"] is True
        assert r["ijss"]["salaire_partiel_maintenu"] == pytest.approx(1250.0, rel=1e-3)
        assert any("Mi-temps thérapeutique" in a for a in r["alertes"])

    def test_t12_temps_partiel_proratisation_maintien_cible(self):
        p_debut, p_fin = date(2025, 6, 1), date(2025, 6, 30)
        base_arret = {
            "arret_type": "maladie_simple",
            "date_debut": "2025-06-10",
            "date_fin": "2025-06-20",
            "subrogation_active": True,
            "nombre_enfants": 0,
            "salaire_periode_reelle": 0.0,
        }
        settings = _settings_base(no_seniority_condition=True)
        r_tp = calculer_maintien(
            {
                **base_arret,
                "is_temps_partiel": True,
                "quotite_temps_partiel": 0.8,
            },
            _ctx(),
            settings,
            p_debut,
            p_fin,
        )
        r_full = calculer_maintien(
            {**base_arret, "is_temps_partiel": False},
            _ctx(),
            settings,
            p_debut,
            p_fin,
        )
        assert r_tp["maintien"]["proratisation_temps_partiel"] is True
        assert r_tp["maintien"]["maintien_cible"] == pytest.approx(
            r_full["maintien"]["maintien_cible"] * 0.8, rel=0.02, abs=1.0
        )

    def test_t13_ald_rechute_sans_nouvelle_carence(self):
        d0 = date(2025, 6, 10)
        qual = _qualifier_arret("ald")
        settings = _settings_base()
        arret = {"arret_type": "ald", "est_rechute_ald": True}
        c = _calculer_carence(arret, qual, settings, d0, [])
        assert c["carence_ss_jours"] == 0
        assert c["carence_employeur_jours"] == 0
        assert c["est_continuite"] is True
        assert "ALD" in c["motif_carence"] and "rechute" in c["motif_carence"].lower()

    def test_t14_regularisation_at_delta_ijss(self):
        _p_debut, _p_fin = date(2025, 6, 1), date(2025, 6, 30)
        arret = {
            "arret_type": "accident_travail",
            "date_debut": "2025-06-01",
            "date_fin": "2025-06-30",
            "subrogation_active": True,
            "nombre_enfants": 0,
            "is_temps_partiel": False,
            "quotite_temps_partiel": 1.0,
            "salaire_periode_reelle": 0.0,
        }
        reg = calculer_regularisation_at(
            arret, _ctx(), _settings_base(no_seniority_condition=True)
        )
        assert reg["type"] == "regularisation_at"
        assert reg["delta_ijss"] > 0
        assert "Requalification AT" in reg["alerte"]

    def test_t15_prevoyance_relais_et_nb_jours_arret(self):
        p_debut, p_fin = date(2025, 1, 1), date(2025, 12, 31)
        arret = {
            "arret_type": "maladie_simple",
            "date_debut": "2025-01-01",
            "date_fin": "2025-02-04",
            "subrogation_active": True,
            "nombre_enfants": 0,
            "salaire_periode_reelle": 0.0,
        }
        r = calculer_maintien(
            arret,
            _ctx(),
            _settings_base(provident_relay_days=30),
            p_debut,
            p_fin,
        )
        assert r["nb_jours_arret_total"] == 35
        assert r["prevoyance"]["prevoyance_declenchee"] is True
        assert any("Prévoyance relais" in a for a in r["alertes"])
