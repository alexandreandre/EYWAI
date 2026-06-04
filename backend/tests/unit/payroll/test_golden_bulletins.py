"""Tests de caractérisation (golden) — moteur de paie sans réseau."""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.maintien_salaire_service import (
    _calculer_ijss,
    plafond_ij_pour,
)
from tests.unit.payroll.fixtures.baremes_snapshot import (
    baremes_snapshot_csg_unifie,
)
from tests.unit.payroll.helpers import (
    build_test_contexte,
    run_bulletin_pipeline_forfait,
    run_bulletin_pipeline_heures,
)


class TestGoldenBulletins:
    def test_non_cadre_mensuel(self):
        ctx = build_test_contexte(salaire_base=2000.0, statut="Non-Cadre")
        r = run_bulletin_pipeline_heures(ctx)
        assert r["brut"] == pytest.approx(2000.0, abs=0.02)
        assert r["total_cotisations_salariales"] == pytest.approx(326.78, abs=0.02)
        assert r["total_cotisations_patronales"] == pytest.approx(211.75, abs=0.02)
        assert r["net_imposable"] == pytest.approx(1720.38, abs=0.02)
        assert r["net_a_payer"] == pytest.approx(1673.22, abs=0.02)
        assert r["cout_employeur"] == pytest.approx(2211.75, abs=0.02)

    def test_cadre_mensuel(self):
        ctx = build_test_contexte(salaire_base=3500.0, statut="Cadre")
        r = run_bulletin_pipeline_heures(ctx)
        assert r["brut"] == pytest.approx(3500.0, abs=0.02)
        assert r["net_a_payer"] == pytest.approx(2928.13, abs=0.02)
        assert r["cout_employeur"] == pytest.approx(3873.45, abs=0.02)

    def test_non_cadre_temps_partiel(self):
        """Verrou anti-régression : le SMIC des seuils maladie/AF reste temps plein.

        Si une refonte introduisait un SMIC proratisé pour ces seuils, les
        montants ci-dessous bougeraient pour un temps partiel.
        """
        ctx = build_test_contexte(
            salaire_base=1500.0, statut="Non-Cadre", duree_hebdo=28.0
        )
        r = run_bulletin_pipeline_heures(ctx)
        assert r["brut"] == pytest.approx(1500.0, abs=0.02)
        assert r["total_cotisations_salariales"] == pytest.approx(245.09, abs=0.02)
        assert r["total_cotisations_patronales"] == pytest.approx(158.57, abs=0.02)
        assert r["net_imposable"] == pytest.approx(1290.28, abs=0.02)
        assert r["net_a_payer"] == pytest.approx(1254.91, abs=0.02)
        assert r["cout_employeur"] == pytest.approx(1658.57, abs=0.02)

    def test_forfait_jours(self):
        ctx = build_test_contexte(
            salaire_base=3500.0, statut="Cadre au forfait jour"
        )
        r = run_bulletin_pipeline_forfait(ctx)
        assert r["brut"] == pytest.approx(3500.0, abs=0.02)
        assert r["net_a_payer"] == pytest.approx(2928.13, abs=0.02)

    def test_mois_avec_primes_ppv_et_13e(self):
        ctx = build_test_contexte(salaire_base=2500.0)
        r = run_bulletin_pipeline_heures(
            ctx,
            primes_soumises=[
                {
                    "libelle": "PPV",
                    "montant": 500.0,
                    "prime_id": "prime_partage_valeur",
                },
                {
                    "libelle": "13e mois",
                    "montant": 2500.0,
                    "prime_id": "prime_13eme_mois",
                },
            ],
        )
        assert r["brut"] == pytest.approx(5500.0, abs=0.02)
        assert r["net_a_payer"] == pytest.approx(4704.5, abs=0.02)

    def test_apprenti_pre_2025_exoneration_totale(self):
        ctx = build_test_contexte(
            salaire_base=1200.0,
            type_contrat="Apprentissage",
            date_debut_execution="2024-09-01",
            baremes=baremes_snapshot_csg_unifie(),
        )
        r = run_bulletin_pipeline_heures(ctx)
        assert r["brut"] == pytest.approx(1200.0, abs=0.02)
        assert r["total_cotisations_salariales"] == pytest.approx(0.0, abs=0.02)
        assert r["net_imposable"] == pytest.approx(1200.0, abs=0.02)
        assert r["net_a_payer"] == pytest.approx(1200.0, abs=0.02)

    def test_apprenti_post_2025_csg_sur_residuel(self):
        ctx = build_test_contexte(
            salaire_base=1200.0,
            type_contrat="Apprentissage",
            date_debut_execution="2025-09-01",
            baremes=baremes_snapshot_csg_unifie(),
        )
        r = run_bulletin_pipeline_heures(ctx)
        assert r["brut"] == pytest.approx(1200.0, abs=0.02)
        assert r["total_cotisations_salariales"] == pytest.approx(44.85, abs=0.02)
        assert r["net_imposable"] == pytest.approx(1162.74, abs=0.02)
        assert r["net_a_payer"] == pytest.approx(1155.15, abs=0.02)

    def test_contexte_injecte_sans_supabase(self, monkeypatch):
        def _fail(*_a, **_k):
            raise AssertionError("Supabase ne doit pas être appelé en mode test")

        monkeypatch.setattr(
            "app.modules.payroll.engine.contexte.create_client", _fail
        )
        ctx = build_test_contexte()
        assert ctx.baremes.get("smic", {}).get("cas_general") == 12.31


class TestGoldenArretMaladieIjPlafond:
    def test_plafond_ij_pour_maladie(self):
        plafonds = {"maladie": 51.0, "at_mp": 205.47, "at_mp_majoree": 274.0}
        assert plafond_ij_pour("maladie_simple", 1, plafonds) == 51.0
        assert plafond_ij_pour("accident_travail", 10, plafonds) == 205.47
        assert plafond_ij_pour("accident_travail", 30, plafonds) == 274.0

    def test_ijss_plafonnee_quand_depassement(self):
        ctx = build_test_contexte(salaire_base=12000.0)
        arret = {
            "arret_type": "maladie_simple",
            "date_debut": "2026-04-01",
            "date_fin": "2026-04-15",
            "nombre_enfants": 0,
            "is_temps_partiel": False,
            "quotite_temps_partiel": 1.0,
        }
        qualification = {
            "carence_ss_jours": 3,
            "taux_ijss_base": 0.5,
            "est_at_mp": False,
        }
        carence = {"carence_ss_jours": 3}
        res = _calculer_ijss(
            arret,
            qualification,
            carence,
            ctx,
            date(2026, 4, 1),
            date(2026, 4, 30),
        )
        assert res["ijss_journaliere"] <= 51.0 + 0.01

    def test_ijss_non_plafonnee_si_plafonds_absents(self):
        ctx = build_test_contexte(salaire_base=12000.0)
        ctx.baremes.pop("ij_plafonds", None)
        arret = {
            "arret_type": "maladie_simple",
            "date_debut": "2026-04-01",
            "date_fin": "2026-04-15",
            "nombre_enfants": 0,
            "is_temps_partiel": False,
            "quotite_temps_partiel": 1.0,
        }
        qual = {"carence_ss_jours": 3, "taux_ijss_base": 0.5, "est_at_mp": False}
        carence = {"carence_ss_jours": 3}
        res_sans = _calculer_ijss(
            arret, qual, carence, ctx, date(2026, 4, 1), date(2026, 4, 30)
        )
        ctx2 = build_test_contexte(salaire_base=12000.0)
        res_avec = _calculer_ijss(
            arret, qual, carence, ctx2, date(2026, 4, 1), date(2026, 4, 30)
        )
        assert res_avec["ijss_journaliere"] <= 51.0 + 0.01
        assert res_sans["ijss_journaliere"] > res_avec["ijss_journaliere"]
