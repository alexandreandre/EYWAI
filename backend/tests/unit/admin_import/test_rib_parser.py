"""Tests unitaires — parsing cellule RIB."""

import pytest

from app.modules.admin_import.application.rib_parser import (
    build_coordonnees_bancaires,
    parse_rib_cell,
)


class TestParseRibCell:
    def test_extracts_iban_with_spaces(self):
        iban, bic, valid, err = parse_rib_cell("FR14 2004 1010 0505 0001 3M02 606")
        assert valid is True
        assert err == ""
        assert iban == "FR1420041010050500013M02606"
        assert bic == ""

    def test_extracts_iban_and_bic(self):
        raw = "IBAN FR1420041010050500013M02606 BIC BNPAFRPPXXX"
        iban, bic, valid, err = parse_rib_cell(raw)
        assert valid is True
        assert iban == "FR1420041010050500013M02606"
        assert bic == "BNPAFRPPXXX"

    def test_rejects_empty(self):
        _, _, valid, err = parse_rib_cell("")
        assert valid is False
        assert "vide" in err.lower()

    def test_rejects_invalid_iban(self):
        _, _, valid, err = parse_rib_cell("FR76 1234")
        assert valid is False

    def test_bic_hint_column(self):
        iban, bic, valid, _ = parse_rib_cell(
            "FR1420041010050500013M02606",
            bic_hint="SOGEFRPP",
        )
        assert valid is True
        assert bic == "SOGEFRPP"


class TestBuildCoordonneesBancaires:
    def test_builds_payload(self):
        payload = build_coordonnees_bancaires("FR1420041010050500013M02606", "BNPAFRPP")
        assert payload["iban"] == "FR1420041010050500013M02606"
        assert payload["bic"] == "BNPAFRPP"
