"""Tests calcul prime d'ancienneté métallurgie."""

from __future__ import annotations

from app.modules.collective_agreements.rules.prime_calcul import calculer_montant_prime_anciennete


class TestPrimeCalculMetallurgie:
    def test_formule_illustration_officielle(self):
        """([5 × 1,45 %] × 100) × 8 = 58 € mensuels."""
        regles = {
            "bareme": [],
            "base_de_calcul": {
                "methode": "metallurgie_prime_anciennete",
                "valeur": 5.0,
            },
            "taux_par_classe": {"1": 0.0145},
        }
        contrat = {
            "remuneration": {
                "classification_conventionnelle": {"classe_emploi": 1},
            }
        }
        result = calculer_montant_prime_anciennete(
            regles_prime=regles,
            contrat=contrat,
            anciennete_annees=8.0,
            salaire_base_mensuel=2000.0,
            minima_applicables=[],
        )
        assert result is not None
        base, montant, libelle = result
        assert round(base, 2) == 7.25
        assert montant == 58.0
        assert "métallurgie" in libelle.lower() or "metallurgie" in libelle.lower()

    def test_classic_bareme_still_works(self):
        regles = {
            "bareme": [{"annees_min": 3, "taux": 0.03}],
            "base_de_calcul": {"methode": "pourcentage_salaire_de_base", "valeur": 1.0},
        }
        result = calculer_montant_prime_anciennete(
            regles_prime=regles,
            contrat={},
            anciennete_annees=5.0,
            salaire_base_mensuel=3000.0,
            minima_applicables=[],
        )
        assert result is not None
        _, montant, _ = result
        assert montant == 90.0

    def test_non_cadre_non_exclu_par_regle_cadre(self):
        regles = {
            "bareme": [],
            "base_de_calcul": {
                "methode": "metallurgie_prime_anciennete",
                "valeur": 5.7,
            },
            "taux_par_classe": {"4": 0.0195},
            "eligibilite": {"min_annees": 3, "statuts_exclus": ["Cadre"]},
        }
        contrat = {
            "remuneration": {
                "classification_conventionnelle": {"classe_emploi": 4},
            }
        }
        result = calculer_montant_prime_anciennete(
            regles_prime=regles,
            contrat=contrat,
            anciennete_annees=7.0,
            salaire_base_mensuel=2000.0,
            minima_applicables=[],
            statut="Non-cadre",
        )
        assert result is not None
