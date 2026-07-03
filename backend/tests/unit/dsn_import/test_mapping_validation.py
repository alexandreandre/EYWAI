"""Tests mapping et validation DSN."""

from pathlib import Path

from app.modules.dsn_import.application.mapping import (
    apply_legal_name_to_preview,
    build_preview_items,
    map_employee_payload,
)
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
    assert payload["is_forfait_jour"] is True
    assert payload["employment_status"] == "actif"


def test_apply_legal_name_targets_company_not_group():
    items = [
        {
            "item_type": "group",
            "mapped_payload": {"group_name": "Groupe 123456789"},
            "label": "Groupe 123456789",
        },
        {
            "item_type": "establishment",
            "mapped_payload": {"company_name": "Établissement CERIZAY (00020)"},
            "label": "Établissement CERIZAY (00020)",
        },
    ]
    apply_legal_name_to_preview(items, "CARTOL (CARTOL INDUSTRIE)", single_establishment=True)

    assert items[0]["mapped_payload"]["group_name"] == "Groupe CARTOL"
    assert items[0]["is_scaffold"] is True
    assert items[1]["mapped_payload"]["company_name"] == "CARTOL (CARTOL INDUSTRIE)"
    assert items[1]["label"] == "CARTOL (CARTOL INDUSTRIE)"
