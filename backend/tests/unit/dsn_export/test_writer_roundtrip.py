"""Tests writer NEODeS plat + round-trip parseur."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.modules.dsn_export.domain.writer import (
    DsnWriterError,
    encode_dsn_bytes,
    format_rubrique_line,
    quote_value,
)
from app.modules.dsn_import.application.cumuls import extract_monthly_totals
from app.modules.dsn_import.domain.parser import parse_dsn_content

FIXTURES = Path(__file__).parent / "fixtures"
MINIMAL = FIXTURES / "sample_p26_minimal.txt"


def test_quote_value_escapes_apostrophe():
    assert quote_value("L'ACME") == "'L''ACME'"


def test_quote_value_rejects_forbidden_chars():
    with pytest.raises(DsnWriterError):
        quote_value("a < b")


def test_format_rubrique_line():
    assert format_rubrique_line("S21.G00.30.002", "DUPONT") == "S21.G00.30.002,'DUPONT'"


def test_roundtrip_raw_rubriques_preserves_key_fields():
    original = parse_dsn_content(MINIMAL.read_bytes(), file_name="sample_p26_minimal.txt")
    encoded = encode_dsn_bytes(original)
    assert encoded.decode("iso-8859-15").startswith("S10.G00.00.001,")
    replayed = parse_dsn_content(encoded, file_name="roundtrip.txt")
    assert replayed.dsn_format == "modern"
    assert replayed.envoi.norme == "P26V01"
    assert replayed.entreprise.siren == original.entreprise.siren
    assert replayed.etablissement.nic == original.etablissement.nic
    ind0 = original.etablissement.individus[0]
    ind1 = replayed.etablissement.individus[0]
    assert ind1.nir == ind0.nir
    assert ind1.nom == ind0.nom
    assert ind1.prenom == ind0.prenom
    tot0 = extract_monthly_totals(ind0)
    tot1 = extract_monthly_totals(ind1)
    assert abs(tot0["brut"] - tot1["brut"]) < 0.01
    assert abs(tot0["net_imposable"] - tot1["net_imposable"]) < 0.01
    assert abs(tot0["pas"] - tot1["pas"]) < 0.01
