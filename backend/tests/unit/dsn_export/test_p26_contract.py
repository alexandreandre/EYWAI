"""Contrat P26V01 : fixtures anonymisées et non-conformité de l'ancien XML."""

from __future__ import annotations

from pathlib import Path

from app.modules.dsn_import.domain.parser import parse_dsn_content
from app.modules.dsn_import.domain.validation import validate_parsed_dsn
from app.modules.dsn_import.domain.parser import parse_dsn_files

FIXTURES = Path(__file__).parent / "fixtures"
MINIMAL = FIXTURES / "sample_p26_minimal.txt"


def test_p26_fixture_is_modern_and_parsable():
    content = MINIMAL.read_bytes()
    dsn = parse_dsn_content(content, file_name="sample_p26_minimal.txt")
    assert dsn.dsn_format == "modern"
    assert dsn.envoi.norme == "P26V01"
    assert dsn.declaration.mois_principal.startswith("01")
    assert dsn.entreprise.siren == "123456789"
    assert dsn.etablissement.nic == "00015"
    assert len(dsn.etablissement.individus) == 1
    ind = dsn.etablissement.individus[0]
    assert ind.nir == "1850175123456"
    assert ind.nom == "DUPONT"
    assert ind.prenom == "JEAN"
    assert ind.contrats[0].nature == "01"
    ver = ind.contrats[0].versements[0]
    assert abs(ver.net_fiscal - 2000.0) < 0.01
    assert abs(ver.pas - 100.0) < 0.01
    rem_brut = [r for r in ver.remunerations if r.type_code.startswith("001")]
    assert rem_brut
    assert abs(rem_brut[0].montant - 2500.0) < 0.01
    assert ver.bases_assujetties or ver.cotisations_individuelles
    assert dsn.etablissement.organismes_psc


def test_p26_fixture_validates_without_blocking():
    parsed = parse_dsn_files([("sample_p26_minimal.txt", MINIMAL.read_bytes())])
    anomalies = validate_parsed_dsn(parsed)
    blocking = [a for a in anomalies if a.get("severity") == "blocking"]
    assert blocking == [], blocking


def test_legacy_xml_export_does_not_satisfy_p26_contract():
    """L'ancien prototype XML P24 n'est pas un fichier plat P26V01."""
    fake_xml = b"""<?xml version="1.0"?>
<DSN xmlns="http://www.neodes.fr/dsn" norme="P24V01" mode="test">
  <S10><S10.G00.00.006>P24V01</S10.G00.00.006></S10>
  <S21>
    <Individu>
      <Identite>
        <S21.G00.30.001>DUPONT</S21.G00.30.001>
        <S21.G00.30.002>JEAN</S21.G00.30.002>
        <S21.G00.30.003>1850175123456</S21.G00.30.003>
      </Identite>
    </Individu>
  </S21>
</DSN>
"""
    dsn = parse_dsn_content(fake_xml, file_name="legacy.xml")
    # Aucune rubrique plate → structure vide / non P26
    assert dsn.envoi.norme != "P26V01" or not dsn.etablissement.individus
    assert not any(
        line.rubrique.startswith("S21.G00.30.") for line in dsn.raw_rubriques
    )
