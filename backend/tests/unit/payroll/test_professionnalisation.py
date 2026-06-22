"""Tests du contrat de professionnalisation (volet patronal + salaire minimum)."""

from __future__ import annotations


import pytest

from app.modules.payroll.engine.calcul_cotisations import calculer_cotisations
from app.modules.payroll.engine.exoneration_alternance import (
    age_a_date,
    controle_salaire_minimum_alternant,
    exonerations_patronales_professionnalisation,
)
from tests.unit.payroll.fixtures.baremes_snapshot import baremes_snapshot_csg_unifie
from tests.unit.payroll.helpers import build_test_contexte


class TestAge:
    def test_age_a_date(self):
        assert age_a_date("1980-06-15", __import__("datetime").date(2025, 6, 14)) == 44
        assert age_a_date("1980-06-15", __import__("datetime").date(2025, 6, 15)) == 45

    def test_age_none_si_absent(self):
        assert age_a_date("") is None


class TestExoPatronalePro:
    def test_vide_par_defaut_pas_de_double_comptage(self):
        """Sans config d'exonération patronale, aucune ligne (réduction générale couvre)."""
        ctx = build_test_contexte(
            type_contrat="Contrat de professionnalisation",
            date_naissance="1975-01-01",
        )
        assert exonerations_patronales_professionnalisation(ctx, 2000.0) == []

    def test_applique_si_config_et_public_eligible(self):
        b = baremes_snapshot_csg_unifie()
        b["alternance"]["professionnalisation"]["exonerations_patronales"] = [
            {
                "public": "demandeur_emploi_45_plus",
                "criteres": {"age_min": 45, "demandeur_emploi": True},
                "cotisations": [
                    {
                        "id": "exo_pro",
                        "libelle": "Exonération pro >=45 ans",
                        "taux_patronal": 0.10,
                    }
                ],
            }
        ]
        ctx = build_test_contexte(
            type_contrat="Contrat de professionnalisation",
            date_naissance="1970-01-01",
            baremes=b,
        )
        ctx.contrat["specificites_paie"]["demandeur_emploi"] = True
        lignes = exonerations_patronales_professionnalisation(ctx, 2000.0)
        assert len(lignes) == 1
        assert lignes[0]["montant_patronal"] == pytest.approx(-200.0, abs=0.01)

    def test_non_applique_si_public_non_eligible(self):
        b = baremes_snapshot_csg_unifie()
        b["alternance"]["professionnalisation"]["exonerations_patronales"] = [
            {
                "criteres": {"age_min": 45, "demandeur_emploi": True},
                "cotisations": [{"taux_patronal": 0.10}],
            }
        ]
        ctx = build_test_contexte(
            type_contrat="Contrat de professionnalisation",
            date_naissance="1995-01-01",
            baremes=b,
        )
        assert exonerations_patronales_professionnalisation(ctx, 2000.0) == []


class TestSalaireMinimum:
    def test_aucun_controle_sans_grille(self):
        ctx = build_test_contexte(
            type_contrat="Apprentissage", date_debut_execution="2025-09-01"
        )
        assert controle_salaire_minimum_alternant(ctx, 500.0) is None

    def test_alerte_si_sous_minimum(self):
        b = baremes_snapshot_csg_unifie()
        b["alternance"]["apprenti"]["grille_remuneration"] = [
            {"age_min": 18, "age_max": 25, "pct_smic": 0.51}
        ]
        ctx = build_test_contexte(
            type_contrat="Apprentissage",
            date_debut_execution="2025-09-01",
            date_naissance="2005-01-01",
            baremes=b,
        )
        minimum = ctx.smic_mensuel * 0.51
        alerte = controle_salaire_minimum_alternant(ctx, minimum - 100)
        assert alerte is not None
        assert alerte["code"] == "salaire_minimum_alternant"
        assert alerte["severity"] == "warning"

    def test_pas_alerte_si_au_dessus(self):
        b = baremes_snapshot_csg_unifie()
        b["alternance"]["apprenti"]["grille_remuneration"] = [
            {"age_min": 18, "age_max": 25, "pct_smic": 0.51}
        ]
        ctx = build_test_contexte(
            type_contrat="Apprentissage",
            date_debut_execution="2025-09-01",
            date_naissance="2005-01-01",
            baremes=b,
        )
        minimum = ctx.smic_mensuel * 0.51
        assert controle_salaire_minimum_alternant(ctx, minimum + 100) is None


class TestProCotisationsNormales:
    def test_pro_cotisations_salariales_normales(self):
        """Le contrat pro a des cotisations salariales normales (pas d'exo apprenti)."""
        b = baremes_snapshot_csg_unifie()
        ctx_pro = build_test_contexte(
            type_contrat="Contrat de professionnalisation",
            salaire_base=1500.0,
            baremes=b,
        )
        ctx_cdi = build_test_contexte(
            type_contrat="CDI", salaire_base=1500.0, baremes=b
        )
        _, tot_pro = calculer_cotisations(ctx_pro, 1500.0, 0.0, 0.0)
        _, tot_cdi = calculer_cotisations(ctx_cdi, 1500.0, 0.0, 0.0)
        assert tot_pro == pytest.approx(tot_cdi, abs=0.01)
