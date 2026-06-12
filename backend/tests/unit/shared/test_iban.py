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
