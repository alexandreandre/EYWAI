"""Tests reconstruction cumuls."""

from pathlib import Path

from app.modules.dsn_import.application.cumuls import (
    build_cumuls_for_month,
    build_cumuls_summary,
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


def test_build_cumuls_summary():
    items = [
        {
            "mapped_payload": {
                "period": "2026-01",
                "employee_key": "a",
                "month_totals": {"brut": 3000, "net_imposable": 2400, "pas": 300, "heures": 151.67},
            }
        },
        {
            "mapped_payload": {
                "period": "2026-01",
                "employee_key": "b",
                "month_totals": {"brut": 0, "net_imposable": 0, "pas": 0, "heures": 0},
            }
        },
    ]
    summary = build_cumuls_summary(items)
    assert summary["period_count"] == 1
    assert summary["employee_count"] == 2
    assert summary["entry_count"] == 2
    assert summary["by_period"][0]["brut"] == 3000.0
    assert summary["by_period"][0]["employees_without_brut"] == 1

