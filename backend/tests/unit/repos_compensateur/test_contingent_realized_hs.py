"""Tests contingent HS avec HS réalisées (modulation)."""

from app.modules.repos_compensateur.domain.rules import heures_hs_pour_contingent_mois


def test_contingent_uses_realized_when_higher_than_paid():
    bulletin = {
        "calcul_du_brut": [
            {"libelle": "Heures supplémentaires 25%", "quantite": 6},
        ]
    }
    events = {"hs_realisees_mois": 20.0}
    assert heures_hs_pour_contingent_mois(bulletin, events) == 20.0


def test_contingent_falls_back_to_paid():
    bulletin = {
        "calcul_du_brut": [
            {"libelle": "Heures supplémentaires 25%", "quantite": 8},
        ]
    }
    assert heures_hs_pour_contingent_mois(bulletin, None) == 8.0
