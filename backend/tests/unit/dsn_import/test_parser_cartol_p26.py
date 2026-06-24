"""Tests parser / extraction sur fixture CARTOL P26."""

from pathlib import Path

from app.modules.dsn_import.application.cumuls import extract_monthly_totals
from app.modules.dsn_import.application.mapping import build_preview_items, map_establishment_payload
from app.modules.dsn_import.domain.establishment_extract import extract_taux_at_mp, infer_payroll_calendar
from app.modules.dsn_import.domain.parser import parse_dsn_content, parse_dsn_files

FIXTURE = Path(__file__).parent / "fixtures" / "sample_dsn_cartol_p26_slice.txt"


def _parse_fixture():
    content = FIXTURE.read_bytes()
    return parse_dsn_content(content, file_name="sample_dsn_cartol_p26_slice.txt")


def test_parser_cartol_at_mp():
    dsn = _parse_fixture()
    etab = dsn.etablissement
    assert len(etab.composants_cotisation) >= 2
    taux = extract_taux_at_mp(etab)
    assert taux == 4.66


def test_parser_p26_bases_assujetties():
    dsn = _parse_fixture()
    ind = dsn.etablissement.individus[0]
    ver = ind.contrats[0].versements[0]
    assert len(ver.bases_assujetties) >= 1
    ba = ver.bases_assujetties[0]
    assert ba.code == "02"
    assert ba.montant == 2475.52
    bases = ver.rubriques.get("bases")
    assert isinstance(bases, dict)
    assert bases.get("02") == 2475.52


def test_cumuls_brut_from_g78_g79():
    dsn = _parse_fixture()
    ind = dsn.etablissement.individus[0]
    totals = extract_monthly_totals(ind)
    assert totals["brut"] == 2475.52


def test_establishment_payroll_inference():
    dsn = _parse_fixture()
    etab = dsn.etablissement
    calendar = infer_payroll_calendar(etab)
    assert calendar["paie_jour_de_fin"] == 31
    assert calendar["paie_occurrence"] == -1


def test_establishment_payload_enriched():
    dsn = _parse_fixture()
    parsed = parse_dsn_files([(str(FIXTURE), FIXTURE.read_bytes())])
    etabs = parsed.etablissements_by_siret()
    siret, etab = next(iter(etabs.items()))
    payload = map_establishment_payload(etab, parsed.siren or "", parsed)
    assert payload["taux_at_mp"] == 4.66
    assert payload["paie_jour_de_fin"] == 31
    assert payload.get("dsn_organismes")


def test_preview_includes_absence_and_exit_items():
    parsed = parse_dsn_files([(str(FIXTURE), FIXTURE.read_bytes())])
    items, _ = build_preview_items(parsed)
    types = {it["item_type"] for it in items}
    assert "establishment" in types
    assert "employee" in types
    assert any(it["item_type"] == "absence" for it in items)
