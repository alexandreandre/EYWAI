"""Tests parseur import virements CPAM."""

from app.modules.ijss_tracking.infrastructure.parsers.bank_recap_parser import (
    detect_column_mapping,
    parse_bank_recap_file,
)


def test_detect_column_mapping():
    headers = ["Date", "Montant", "Libellé", "Référence"]
    mapping = detect_column_mapping(headers)
    assert "amount" in mapping
    assert "payment_date" in mapping


def test_parse_csv_bank_recap():
    content = b"Date;Montant;Libelle\n2026-06-15;842,50;CPAM DUPONT JEAN\n"
    result = parse_bank_recap_file("recap.csv", content)
    assert result["line_count"] == 1
    assert result["lines"][0]["amount"] == 842.50
