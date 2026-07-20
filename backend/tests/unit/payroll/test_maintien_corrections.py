"""
Tests des corrections du moteur de maintien de salaire :
- barème de durée selon l'ancienneté (D1226-1),
- déduction de la carence employeur,
- suppression de la carence employeur pour AT/MP,
- majoration IJSS 3 enfants à partir du 31e jour,
- complément de prévoyance cadre.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.modules.payroll.engine.maintien_salaire_service import (
    calculer_maintien,
    duree_maintien_par_taux,
    _calculer_carence,
    _qualifier_arret,
    _statut_est_cadre,
    _taux_ijss_pour_jour_arret,
)


def _ctx(
    salaire_mensuel: float = 3000.0,
    pss_annuel: float = 48000.0,
    date_entree: str = "2021-01-15",
    statut: str = "Non-Cadre",
) -> SimpleNamespace:
    return SimpleNamespace(
        salaire_base_mensuel=salaire_mensuel,
        statut_salarie=statut,
        baremes={
            "pss": {"annuel": pss_annuel},
            "ij_plafonds": {
                "maladie": 51.0,
                "maternite_paternite": 95.22,
                "at_mp": 205.47,
                "at_mp_majoree": 274.0,
            },
        },
        contrat={"contrat": {"date_entree": date_entree, "statut": statut}},
    )


def _settings(**overrides):
    base = {
        "apply_legal_maintenance": True,
        "min_seniority_months": 12,
        "employer_waiting_days": 7,
        "no_seniority_condition": False,
        "custom_duration_days": None,
        "provident_relay_days": None,
        "provident_maintenance_rate": None,
        "provident_cadre_only": True,
    }
    base.update(overrides)
    return base


class TestDureeMaintienAnciennete:
    @pytest.mark.parametrize(
        "mois,attendu",
        [
            (12, 30),     # 1 an
            (59, 30),     # < 5 ans
            (71, 30),     # 5 ans 11 mois
            (72, 40),     # 6 ans
            (132, 50),    # 11 ans
            (192, 60),    # 16 ans
            (252, 70),    # 21 ans
            (312, 80),    # 26 ans
            (372, 90),    # 31 ans
            (600, 90),    # plafond
        ],
    )
    def test_bareme_par_tranche(self, mois, attendu):
        assert duree_maintien_par_taux(mois) == attendu

    def test_moins_dun_an_renvoie_base(self):
        assert duree_maintien_par_taux(6) == 30


class TestCarenceEmployeur:
    def test_carence_deduite_du_maintien(self):
        # Arrêt 10 jours, carence employeur 7 j → maintien sur les jours 8, 9, 10.
        p_debut, p_fin = date(2025, 6, 1), date(2025, 6, 30)
        arret = {
            "arret_type": "maladie_simple",
            "date_debut": "2025-06-01",
            "date_fin": "2025-06-10",
            "subrogation_active": False,
            "nombre_enfants": 0,
            "salaire_periode_reelle": 0.0,
        }
        r = calculer_maintien(arret, _ctx(), _settings(), p_debut, p_fin)
        assert r["maintien"]["carence_employeur_jours"] == 7
        assert r["maintien"]["nb_jours_maintien"] == 3

    def test_at_mp_pas_de_carence_employeur(self):
        d0 = date(2025, 6, 10)
        qual = _qualifier_arret("accident_travail")
        c = _calculer_carence({"arret_type": "accident_travail"}, qual, _settings(), d0, [])
        assert c["carence_employeur_jours"] == 0
        assert "AT/MP" in c["motif_carence"]


class TestCongeMaternite:
    """Régime de parentalité : maintien 100 % inconditionnel, sans barème
    dégressif D1226-1 (propre à la maladie) ni carence. Réf. Code du travail
    L1225-17 et s. ; CCN métallurgie IDCC 3248 art. 92 (maintien 100 %)."""

    def test_qualification_maternite(self):
        q = _qualifier_arret("maternite")
        assert q["est_maternite"] is True
        assert q["carence_ss_jours"] == 0  # IJSS maternité dès le 1er jour
        assert q["est_at_mp"] is False

    def test_maladie_non_maternite(self):
        assert _qualifier_arret("maladie_simple")["est_maternite"] is False

    def test_pas_de_carence_employeur_maternite(self):
        d0 = date(2026, 5, 1)
        qual = _qualifier_arret("maternite")
        c = _calculer_carence({"arret_type": "maternite"}, qual, _settings(), d0, [])
        assert c["carence_employeur_jours"] == 0
        assert c["carence_ss_jours"] == 0

    def test_maintien_100_pct_plein_mois_sans_palier(self):
        # Congé maternité tout le mois de mai : maintien = 100 % du salaire,
        # AUCUNE carence (contrairement aux 7 j employeur de la maladie),
        # AUCUN barème dégressif → maintien couvre les 31 jours calendaires.
        p_debut, p_fin = date(2026, 5, 1), date(2026, 5, 31)
        arret = {
            "arret_type": "maternite",
            "date_debut": "2026-05-01",
            "date_fin": "2026-05-31",
            "subrogation_active": True,
            "nombre_enfants": 0,
            "salaire_periode_reelle": 0.0,
        }
        ctx = _ctx(salaire_mensuel=1870.83)
        r = calculer_maintien(arret, ctx, _settings(), p_debut, p_fin)
        m = r["maintien"]
        assert m["maintien_applicable"] is True
        assert m["taux_maintien"] == pytest.approx(1.0)
        assert m["carence_employeur_jours"] == 0
        assert m["nb_jours_maintien"] == 31
        assert m.get("est_maternite") is True
        # brut_journalier = salaire / 30,42 ; maintien = 31 j × brut_journalier
        brut_j = 1870.83 / 30.42
        assert m["maintien_cible"] == pytest.approx(round(brut_j * 31, 2), abs=0.05)

    def test_maternite_ignore_le_bareme_maladie_degressif(self):
        # Un arrêt maladie long verrait son taux baisser après le 1er palier ;
        # la maternité reste à 100 % quelle que soit l'ancienneté / la durée.
        p_debut, p_fin = date(2026, 5, 1), date(2026, 5, 31)
        base = {
            "date_debut": "2026-05-01",
            "date_fin": "2026-05-31",
            "subrogation_active": True,
            "nombre_enfants": 0,
            "salaire_periode_reelle": 0.0,
        }
        ctx = _ctx(salaire_mensuel=1870.83, date_entree="2010-01-01")
        mat = calculer_maintien({**base, "arret_type": "maternite"}, ctx, _settings(), p_debut, p_fin)
        assert mat["maintien"]["taux_maintien"] == pytest.approx(1.0)


class TestMajoration3Enfants:
    def test_taux_avant_j31(self):
        assert _taux_ijss_pour_jour_arret("maladie_simple", 30, 3) == pytest.approx(0.50)

    def test_taux_a_partir_j31(self):
        assert _taux_ijss_pour_jour_arret("maladie_simple", 31, 3) == pytest.approx(0.66)

    def test_moins_de_3_enfants_pas_de_majoration(self):
        assert _taux_ijss_pour_jour_arret("maladie_simple", 40, 2) == pytest.approx(0.50)


class TestStatutCadre:
    @pytest.mark.parametrize(
        "statut,attendu",
        [
            ("Cadre", True),
            ("cadre", True),
            ("Cadre forfait jour", True),
            ("Non-Cadre", False),
            ("Non Cadre", False),
            ("", False),
            (None, False),
        ],
    )
    def test_detection(self, statut, attendu):
        assert _statut_est_cadre(statut) is attendu


class TestAncienneteDifferentieeAmAt:
    def test_am_onze_mois_pas_de_maintien(self):
        p_debut, p_fin = date(2025, 6, 1), date(2025, 6, 30)
        arret = {
            "arret_type": "maladie_simple",
            "date_debut": "2025-06-01",
            "date_fin": "2025-06-10",
            "subrogation_active": False,
            "nombre_enfants": 0,
            "salaire_periode_reelle": 0.0,
        }
        ctx = _ctx(date_entree="2024-07-15")
        r = calculer_maintien(
            arret,
            ctx,
            _settings(min_seniority_months=12, min_seniority_months_at_mp=3),
            p_debut,
            p_fin,
        )
        assert r["maintien"]["maintien_applicable"] is False

    def test_at_quatre_mois_avec_seuil_trois(self):
        p_debut, p_fin = date(2025, 6, 1), date(2025, 6, 30)
        arret = {
            "arret_type": "accident_travail",
            "date_debut": "2025-06-01",
            "date_fin": "2025-06-10",
            "subrogation_active": True,
            "nombre_enfants": 0,
            "salaire_periode_reelle": 0.0,
        }
        ctx = _ctx(date_entree="2025-02-01")
        r = calculer_maintien(
            arret,
            ctx,
            _settings(min_seniority_months=12, min_seniority_months_at_mp=3),
            p_debut,
            p_fin,
        )
        assert r["maintien"]["maintien_applicable"] is True
        assert r["maintien"]["nb_jours_maintien"] > 0

    def test_at_deux_mois_pas_de_maintien(self):
        p_debut, p_fin = date(2025, 6, 1), date(2025, 6, 30)
        arret = {
            "arret_type": "accident_travail",
            "date_debut": "2025-06-01",
            "date_fin": "2025-06-10",
            "subrogation_active": False,
            "nombre_enfants": 0,
            "salaire_periode_reelle": 0.0,
        }
        ctx = _ctx(date_entree="2025-04-15")
        r = calculer_maintien(
            arret,
            ctx,
            _settings(min_seniority_months=12, min_seniority_months_at_mp=3),
            p_debut,
            p_fin,
        )
        assert r["maintien"]["maintien_applicable"] is False


class TestIjssBrutOverride:
    def test_override_remplace_theorique(self):
        p_debut, p_fin = date(2025, 6, 1), date(2025, 6, 30)
        arret = {
            "arret_type": "maladie_simple",
            "date_debut": "2025-06-01",
            "date_fin": "2025-06-10",
            "subrogation_active": True,
            "ijss_brut_override": 448.0,
            "nombre_enfants": 0,
            "salaire_periode_reelle": 0.0,
        }
        r = calculer_maintien(arret, _ctx(), _settings(), p_debut, p_fin)
        assert r["ijss"]["ijss_theorique"] == pytest.approx(448.0)
        assert r["ijss"].get("ijss_brut_override") is True

    def test_complement_prevoyance_cadre_apres_maintien_legal(self):
        # Cadre, 4 ans → maintien légal 60 j. Prévoyance 80 % au-delà (franchise défaut 60).
        p_debut, p_fin = date(2025, 1, 1), date(2025, 12, 31)
        arret = {
            "arret_type": "maladie_simple",
            "date_debut": "2025-01-01",
            "date_fin": "2025-03-31",  # 90 jours
            "subrogation_active": True,
            "nombre_enfants": 0,
            "salaire_periode_reelle": 0.0,
        }
        settings = _settings(provident_maintenance_rate=0.80)
        r = calculer_maintien(arret, _ctx(statut="Cadre"), settings, p_debut, p_fin)
        prev = r["prevoyance"]
        assert prev["eligible"] is True
        assert prev["taux_cible"] == pytest.approx(0.80)
        assert prev["montant"] > 0
        assert prev["nb_jours"] > 0
        assert any("Complément prévoyance" in a for a in r["alertes"])

    def test_prevoyance_non_cadre_ignoree_si_reservee_cadres(self):
        p_debut, p_fin = date(2025, 1, 1), date(2025, 12, 31)
        arret = {
            "arret_type": "maladie_simple",
            "date_debut": "2025-01-01",
            "date_fin": "2025-03-31",
            "subrogation_active": True,
            "nombre_enfants": 0,
            "salaire_periode_reelle": 0.0,
        }
        settings = _settings(provident_maintenance_rate=0.80, provident_cadre_only=True)
        r = calculer_maintien(arret, _ctx(statut="Non-Cadre"), settings, p_debut, p_fin)
        assert r["prevoyance"]["eligible"] is False
        assert r["prevoyance"]["montant"] == 0.0

    def test_prevoyance_montant_hors_cout_employeur(self):
        # La prévoyance ne gonfle pas le complément employeur (versée par l'assureur).
        p_debut, p_fin = date(2025, 1, 1), date(2025, 12, 31)
        arret = {
            "arret_type": "maladie_simple",
            "date_debut": "2025-01-01",
            "date_fin": "2025-03-31",
            "subrogation_active": True,
            "nombre_enfants": 0,
            "salaire_periode_reelle": 0.0,
        }
        sans = calculer_maintien(arret, _ctx(statut="Cadre"), _settings(), p_debut, p_fin)
        avec = calculer_maintien(
            arret,
            _ctx(statut="Cadre"),
            _settings(provident_maintenance_rate=0.80),
            p_debut,
            p_fin,
        )
        assert avec["maintien"]["complement_employeur"] == pytest.approx(
            sans["maintien"]["complement_employeur"]
        )
