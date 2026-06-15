"""Tests mapping et validation DSN."""

from pathlib import Path

from app.modules.dsn_import.application.mapping import build_preview_items, map_employee_payload
from app.modules.dsn_import.domain.parser import parse_dsn_content
from app.modules.dsn_import.domain.validation import validate_parsed_dsn
from app.modules.dsn_import.domain.parser import parse_dsn_files


FIXTURES = Path(__file__).parent / "fixtures"


def test_validate_parsed_dsn_ok():
    content = (FIXTURES / "sample_dsn_mars.txt").read_bytes()
    parsed = parse_dsn_files([("sample.txt", content)])
    anomalies = validate_parsed_dsn(parsed)
    blocking = [a for a in anomalies if a.get("severity") == "blocking"]
    assert blocking == []


def test_build_preview_items():
    content = (FIXTURES / "sample_dsn_mars.txt").read_bytes()
    parsed = parse_dsn_files([("sample.txt", content)])
    items, summary = build_preview_items(parsed)

    types = {i["item_type"] for i in items}
    assert "group" in types
    assert "establishment" in types
    assert "employee" in types
    assert "collective_agreement" in types
    assert summary["employee_count"] == 1


def test_map_employee_contract_type():
    content = (FIXTURES / "sample_dsn_mars.txt").read_bytes()
    dsn = parse_dsn_content(content)
    ind = dsn.etablissement.individus[0]
    payload = map_employee_payload(ind, dsn.etablissement, dsn.etablissement.siret)
    assert payload["contract_type"] == "CDI"
    assert payload["statut"] == "Cadre"
    assert payload["employment_status"] == "en_onboarding"
