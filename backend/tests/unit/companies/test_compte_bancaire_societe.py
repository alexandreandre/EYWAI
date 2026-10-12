"""Compte bancaire de la société (IBAN, BIC, titulaire), saisi dans les paramètres de paie.

Il vit dans `companies.settings.compte_bancaire` et sert de donneur d'ordre aux
deux remises SEPA (salaires et acomptes). Il n'entre pas dans l'empreinte des
bulletins : le changer ne les fait pas passer « À recalculer ».
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.companies.domain.parametres_paie import (
    CLES_SETTINGS,
    fusionner_reglages,
    valider_compte_bancaire,
)
from app.modules.companies.schemas.requests import CompanyDetailsUpdate

pytestmark = pytest.mark.unit

IBAN = "FR7630001007941234567890185"


class TestValidation:
    def test_compte_complet_normalise(self):
        compte = valider_compte_bancaire(
            {"iban": "fr76 3000 1007 9412 3456 7890 185", "bic": "bnpa frpp", "titulaire": " SAS Exemple "}
        )
        assert compte == {"iban": IBAN, "bic": "BNPAFRPP", "titulaire": "SAS Exemple"}

    def test_bic_et_titulaire_facultatifs(self):
        assert valider_compte_bancaire({"iban": IBAN}) == {"iban": IBAN, "bic": "", "titulaire": ""}

    def test_null_retire_le_compte(self):
        assert valider_compte_bancaire(None) is None

    def test_cle_fausse_refusee_avec_la_raison(self):
        with pytest.raises(ValueError, match="Clé de contrôle"):
            valider_compte_bancaire({"iban": "FR7630001007941234567890186"})

    def test_iban_obligatoire(self):
        with pytest.raises(ValueError, match="IBAN"):
            valider_compte_bancaire({"iban": "", "bic": "BNPAFRPP"})

    def test_bic_invalide_refuse(self):
        with pytest.raises(ValueError, match="BIC"):
            valider_compte_bancaire({"iban": IBAN, "bic": "BNPA"})

    def test_titulaire_trop_long_pour_le_fichier_sepa(self):
        with pytest.raises(ValueError, match="70"):
            valider_compte_bancaire({"iban": IBAN, "titulaire": "X" * 71})

    def test_pas_un_objet(self):
        with pytest.raises(ValueError):
            valider_compte_bancaire("FR76")


class TestCorpsDeRequete:
    def test_le_compte_est_un_reglage_de_settings(self):
        assert "compte_bancaire" in CLES_SETTINGS

    def test_valide_et_garde_dans_le_corps(self):
        corps = CompanyDetailsUpdate(compte_bancaire={"iban": IBAN, "bic": "BNPAFRPP", "titulaire": "SAS"})
        assert corps.to_update_dict() == {
            "compte_bancaire": {"iban": IBAN, "bic": "BNPAFRPP", "titulaire": "SAS"}
        }

    def test_null_explicite_est_garde_pour_retirer_la_cle(self):
        assert CompanyDetailsUpdate(compte_bancaire=None).to_update_dict() == {"compte_bancaire": None}

    def test_refus_en_francais_sans_prefixe(self):
        with pytest.raises(ValidationError) as exc:
            CompanyDetailsUpdate(compte_bancaire={"iban": "FR76300010079412"})
        message = exc.value.errors()[0]["msg"]
        assert "27 caractères attendus" in message
        assert not message.startswith("Value error")


class TestFusion:
    def test_rejoint_settings_sans_toucher_aux_autres_cles(self):
        settings = fusionner_reglages({"x": 1}, {"compte_bancaire": {"iban": IBAN}})
        assert settings == {"x": 1, "compte_bancaire": {"iban": IBAN}}

    def test_none_retire_la_cle(self):
        assert fusionner_reglages({"x": 1, "compte_bancaire": {"iban": IBAN}}, {"compte_bancaire": None}) == {"x": 1}
