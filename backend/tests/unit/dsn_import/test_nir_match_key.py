"""Tests unitaires : clé de rapprochement NIR (matching base 15 ↔ DSN 13)."""

import pytest

from app.modules.dsn_import.domain.normalize import nir_match_key

pytestmark = pytest.mark.unit


def test_nir_15_digits_reduced_to_13_drops_cle():
    # NIR base (15) = NIR (13) + clé (2). La DSN émet souvent le NIR à 13.
    assert nir_match_key("187059935222362") == "1870599352223"


def test_nir_13_digits_unchanged():
    assert nir_match_key("1870599352223") == "1870599352223"


def test_base_15_and_dsn_13_produce_same_key():
    assert nir_match_key("187059935222362") == nir_match_key("1870599352223")


def test_spaces_and_separators_removed():
    assert nir_match_key("1 87 05 99 352 223 62") == "1870599352223"
    assert nir_match_key("1-87-05-99-352-223-62") == "1870599352223"


def test_corsican_nir_keeps_letter_truncates_by_char_count():
    # Départements 2A / 2B : le NIR contient une lettre — ne pas filtrer les chiffres.
    assert nir_match_key("1850522A1234578") == "1850522A12345"


def test_ntt_or_non_standard_returned_cleaned():
    # NTT (numéro technique temporaire) : ni 13 ni 15 → renvoyé nettoyé, sans troncature.
    assert nir_match_key("NTT12345") == "NTT12345"


def test_empty_and_none():
    assert nir_match_key("") == ""
    assert nir_match_key(None) == ""
    assert nir_match_key("   ") == ""
