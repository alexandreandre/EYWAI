"""Tests unitaires — utilitaires IBAN."""

import pytest

from app.shared.utils.iban import (
    extract_iban,
    has_valid_iban,
    parse_coordonnees_bancaires,
    validate_iban,
)

pytestmark = pytest.mark.unit


class TestIbanUtils:
    def test_parse_null_coords(self):
        assert parse_coordonnees_bancaires(None) == {}
        assert extract_iban(None) == ""
        assert has_valid_iban(None) is False

    def test_parse_json_string_coords(self):
        raw = '{"iban": "FR7630001007941234567890185", "bic": "BNPAFRPP"}'
        assert extract_iban(raw) == "FR7630001007941234567890185"
        assert has_valid_iban(raw) is True

    def test_extract_iban_uppercase_key(self):
        assert extract_iban({"IBAN": "fr76 3000 1007 9412 3456 7890 185"}) == (
            "FR7630001007941234567890185"
        )

    def test_bic_only_is_not_valid(self):
        assert has_valid_iban({"bic": "BNPAFRPP"}) is False

    def test_short_iban_is_invalid(self):
        assert validate_iban("FR761234567890") is False

    def test_bien_forme_ne_regarde_ni_la_cle_ni_la_longueur_du_pays(self):
        from app.shared.utils.iban import iban_bien_forme

        assert iban_bien_forme("FR7630001007941234567890186") is True
        assert iban_bien_forme("FR76300010079412") is True
        assert iban_bien_forme("FR761234567890") is False
        assert iban_bien_forme("1234567890123456") is False
        assert iban_bien_forme("") is False


class TestIbanCle:
    """Clé de contrôle (mod 97) et longueur propre au pays."""

    def test_iban_connu_valide(self):
        assert validate_iban("FR14 2004 1010 0505 0001 3M02 606") is True
        assert validate_iban("DE89370400440532013000") is True

    def test_cle_fausse_refusee(self):
        # même IBAN avec un chiffre changé
        assert validate_iban("FR7630001007941234567890186") is False

    def test_iban_francais_de_17_caracteres_refuse(self):
        assert validate_iban("FR76300010079412") is False

    def test_longueur_du_pays_exigee(self):
        # clé juste, mais un IBAN allemand compte 22 caractères
        assert validate_iban("DE44500105175407324931") is True
        assert validate_iban("DE8937040044053201300") is False

    def test_motif_donne_la_raison(self):
        from app.shared.utils.iban import iban_problem

        assert iban_problem("FR7630001007941234567890185") is None
        assert "27" in iban_problem("FR76300010079412")
        assert "clé" in iban_problem("FR7630001007941234567890186").lower()
        assert iban_problem("") is not None
