"""Lecture du salaire de base mensuel appliqué par un bulletin déjà généré."""

import pytest

from app.modules.payroll.engine.salaire_paye import (
    base_mensuelle_du_bulletin,
    heures_base_mensuelles,
)

pytestmark = pytest.mark.unit


class TestHeuresBaseMensuelles:
    def test_temps_plein_et_39h_donnent_151_67(self):
        assert heures_base_mensuelles(35) == 151.67
        assert heures_base_mensuelles(39) == 151.67
        assert heures_base_mensuelles(None) == 151.67

    def test_temps_partiel_au_prorata(self):
        assert heures_base_mensuelles(24) == 104.0


class TestBaseMensuelleDuBulletin:
    def test_valeur_memorisee_prioritaire(self):
        data = {
            "parametres": {"salaire_base_mensuel": 1867.06},
            "calcul_du_brut": [{"libelle": "Salaire de base", "taux": 12.2, "gain": 1850.37}],
        }
        assert base_mensuelle_du_bulletin(data, 151.67) == 1867.06

    def test_bulletin_ancien_reconstruit_depuis_le_taux(self):
        # Demory, juin 2026 : 151,67 h × 12,31 = 1 867,06, le SMIC revalorisé.
        data = {
            "parametres": {"smic_horaire": 12.31},
            "calcul_du_brut": [
                {"libelle": "Salaire de base", "quantite": 151.67, "taux": 12.31, "gain": 1867.06},
                {"libelle": "Heures suppl. structurelles majorées à 25%", "quantite": 17.33},
            ],
        }
        assert base_mensuelle_du_bulletin(data, 151.67) == 1867.06

    def test_mois_de_sortie_ne_lit_pas_le_montant_proratise(self):
        # Demory, juillet 2026 : 126 h payées, mais le mensuel reste 1 867,06.
        data = {"calcul_du_brut": [{"libelle": "Salaire de base", "quantite": 126.0, "taux": 12.31, "gain": 1551.06}]}
        assert base_mensuelle_du_bulletin(data, 151.67) == 1867.06

    def test_forfait_sans_taux_lit_le_montant(self):
        data = {"calcul_du_brut": [{"libelle": "Salaire de base (forfait jours)", "taux": None, "gain": 3200.0}]}
        assert base_mensuelle_du_bulletin(data, 151.67) == 3200.0

    def test_illisible_rend_none(self):
        assert base_mensuelle_du_bulletin(None, 151.67) is None
        assert base_mensuelle_du_bulletin({}, 151.67) is None
        assert base_mensuelle_du_bulletin({"calcul_du_brut": [{"libelle": "Prime"}]}, 151.67) is None
        assert (
            base_mensuelle_du_bulletin(
                {"calcul_du_brut": [{"libelle": "Salaire de base", "taux": "12,31"}]}, 151.67
            )
            is None
        )
