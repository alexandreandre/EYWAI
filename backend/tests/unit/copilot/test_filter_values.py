"""Tests du rapprochement des valeurs de filtre proposées par le LLM."""

import pytest

from app.modules.copilot.domain.filter_values import (
    ABSENCE_STATUTS,
    ABSENCE_TYPES,
    ValeurDeFiltreInconnue,
    exiger,
    rapprocher,
)

CONTRATS = ["Apprentissage", "CDD", "CDI"]


class TestRapprocher:
    def test_valeur_exacte(self):
        assert rapprocher("CDI", CONTRATS) == "CDI"

    def test_casse_ignoree(self):
        assert rapprocher("cdi", CONTRATS) == "CDI"

    def test_prefixe_relie_apprenti_a_apprentissage(self):
        """Régression : « Combien d'apprentis ? » renvoyait « aucun »."""
        assert rapprocher("Apprenti", CONTRATS) == "Apprentissage"
        assert rapprocher("apprentis", CONTRATS) == "Apprentissage"

    def test_accents_ignores(self):
        assert rapprocher("validé", ABSENCE_STATUTS) == "validated"

    def test_synonyme_maladie(self):
        assert rapprocher("maladie", ABSENCE_TYPES) == "arret_maladie"

    def test_synonyme_conges_payes(self):
        assert rapprocher("congés payés", ABSENCE_TYPES) == "conge_paye"

    def test_underscore_et_espace_equivalents(self):
        assert rapprocher("arret maladie", ABSENCE_TYPES) == "arret_maladie"

    def test_valeur_inconnue(self):
        assert rapprocher("temps partiel", CONTRATS) is None

    def test_prefixe_ambigu_refuse(self):
        assert rapprocher("arret", ("arret_at", "arret_maternite")) is None

    def test_valeur_vide(self):
        assert rapprocher("", CONTRATS) is None


class TestExiger:
    def test_retourne_la_valeur_reelle(self):
        assert exiger("cdd", CONTRATS, champ="contract_type") == "CDD"

    def test_echoue_en_listant_les_valeurs_possibles(self):
        with pytest.raises(ValeurDeFiltreInconnue) as erreur:
            exiger("intérim", CONTRATS, champ="contract_type")
        message = str(erreur.value)
        assert "contract_type" in message
        assert "Apprentissage" in message
