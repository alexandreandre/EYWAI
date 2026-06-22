"""Tests unitaires — conversion RIB français."""

from app.modules.admin_import.application.rib_parser import (
    french_rib_to_iban,
    normalize_french_rib,
    parse_rib_cell,
)


class TestFrenchRib:
    def test_normalizes_alphanumeric_rib(self):
        assert normalize_french_rib("30002073740000000002Q21") == "30002073740000000002Q21"

    def test_normalizes_digit_rib(self):
        assert normalize_french_rib("10278 37405 00012488001 54") == "10278374050001248800154"

    def test_converts_to_iban(self):
        iban = french_rib_to_iban("10278374050001248800154")
        assert iban == "FR7610278374050001248800154"

    def test_parse_rib_cell_from_french_rib(self):
        iban, _bic, valid, err = parse_rib_cell("10278374050001248800154")
        assert valid is True, err
        assert iban == "FR7610278374050001248800154"

    def test_parse_rib_cell_with_letter_account(self):
        iban, _bic, valid, err = parse_rib_cell("30002073740000000002Q21")
        assert valid is True, err
