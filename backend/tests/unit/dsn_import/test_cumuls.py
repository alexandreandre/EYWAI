"""Tests reconstruction cumuls."""

from pathlib import Path

from app.modules.dsn_import.application.cumuls import (
    build_cumuls_for_month,
    extract_monthly_totals,
    plan_cumul_items,
)
from app.modules.dsn_import.domain.parser import parse_dsn_files


FIXTURES = Path(__file__).parent / "fixtures"


def test_extract_monthly_totals():
    content = (FIXTURES / "sample_dsn_mars.txt").read_bytes()
    parsed = parse_dsn_files([("sample.txt", content)])
    ind = list(parsed.etablissements_by_siret().values())[0].individus[0]
    totals = extract_monthly_totals(ind)
    assert totals["brut"] == 3500.0
    assert totals["net_imposable"] == 2800.0
    assert totals["pas"] == 420.0


def test_build_cumuls_cumulative():
    prev = {"cumuls": {"brut_total": 1000.0, "net_imposable": 800.0}}
    month = {"brut": 500.0, "net_imposable": 400.0, "pas": 50.0, "heures": 151.67, "reduction_generale_patronale": 0.0}
    doc = build_cumuls_for_month(prev, month, 3)
    assert doc["cumuls"]["brut_total"] == 1500.0
    assert doc["periode"]["dernier_mois_calcule"] == 3


def test_plan_cumul_items():
    content = (FIXTURES / "sample_dsn_mars.txt").read_bytes()
    parsed = parse_dsn_files([("sample.txt", content)])
    items = plan_cumul_items(parsed)
    assert len(items) == 1
    assert items[0]["item_type"] == "cumul"
