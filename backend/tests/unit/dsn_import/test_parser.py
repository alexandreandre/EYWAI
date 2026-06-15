"""Tests unitaires du parser DSN."""

from pathlib import Path

import pytest

from app.modules.dsn_import.domain.parser import parse_dsn_content, parse_dsn_files


FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_sample_dsn_mars():
    content = (FIXTURES / "sample_dsn_mars.txt").read_bytes()
    dsn = parse_dsn_content(content, file_name="sample_dsn_mars.txt")

    assert dsn.envoi.periode == "202503"
    assert dsn.etablissement.siret == "44306184100047"
    assert dsn.entreprise.siren == "443061841"
    assert len(dsn.etablissement.individus) == 1

    ind = dsn.etablissement.individus[0]
    assert ind.nom == "MARTIN"
    assert ind.prenom == "Jean"
    assert ind.nir == "180032710123448"
    assert len(ind.contrats) == 1
    assert ind.contrats[0].idcc == "1486"
    assert ind.contrats[0].nature == "01"


def test_parse_tolerates_unknown_rubriques():
    text = (
        "S10.G00.00.005,'202501'\n"
        "S21.G00.99.001,'valeur_inconnue'\n"
        "S21.G00.11.001,'44306184100047'\n"
    )
    dsn = parse_dsn_content(text.encode("utf-8"))
    assert dsn.etablissement.siret == "44306184100047"


def test_parse_multi_files():
    content = (FIXTURES / "sample_dsn_mars.txt").read_bytes()
    parsed = parse_dsn_files([("a.txt", content), ("b.txt", content)])
    assert len(parsed.files) == 2
    assert parsed.period_min == "2025-03"
