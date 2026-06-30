"""Tests parser P26 G00.81 et recompute totaux DSN."""

from pathlib import Path

from app.modules.dsn_import.application.cumuls import extract_monthly_totals, plan_cumul_items
from app.modules.dsn_import.application.payroll_totals_recompute import (
    locate_dsn_file,
    sanitize_stored_month_totals,
)
from app.modules.dsn_import.domain.parser import parse_dsn_files

REPO_ROOT = Path(__file__).resolve().parents[4]
CARTOL_JAN = REPO_ROOT / "CARTOL_0126_000001 (1).dsn"


def test_cartol_jan_p26_cotisations_extraction():
    if not CARTOL_JAN.is_file():
        return
    parsed = parse_dsn_files([(CARTOL_JAN.name, CARTOL_JAN.read_bytes())])
    etab = list(parsed.etablissements_by_siret().values())[0]
    ind = next(
        i
        for i in etab.individus
        if round(extract_monthly_totals(i)["brut"], 2) == 2475.52
    )
    totals = extract_monthly_totals(ind)
    assert totals["brut"] == 2475.52
    assert totals["net_imposable"] == 1998.95
    assert 400 <= totals["employee_charges"] <= 500
    assert 1000 <= totals["employer_charges"] <= 1600


def test_cartol_jan_aggregate_employer_charges():
    if not CARTOL_JAN.is_file():
        return
    parsed = parse_dsn_files([(CARTOL_JAN.name, CARTOL_JAN.read_bytes())])
    items = plan_cumul_items(parsed)
    pat = sum(i["mapped_payload"]["month_totals"]["employer_charges"] for i in items)
    sal = sum(i["mapped_payload"]["month_totals"]["employee_charges"] for i in items)
    brut = sum(i["mapped_payload"]["month_totals"]["brut"] for i in items)
    assert 100_000 <= pat <= 140_000
    assert 30_000 <= sal <= 60_000
    assert abs(brut - 205_521.06) < 1.0


def test_sanitize_stored_month_totals_fixes_missing_charges():
    raw = {"brut": 3000.0, "net_imposable": 2400.0, "pas": 0.0}
    fixed = sanitize_stored_month_totals(raw)
    assert fixed["employee_charges"] == 600.0
    assert fixed["employer_charges"] == 0.0


def test_sanitize_stored_month_totals_fixes_assiette_misread_as_salarial():
    raw = {
        "brut": 2475.52,
        "net_imposable": 1998.95,
        "employee_charges": 47094.29,
        "employer_charges": 0.0,
    }
    fixed = sanitize_stored_month_totals(raw)
    assert fixed["employee_charges"] == 476.57


def test_locate_dsn_file_finds_duplicate_suffix(tmp_path: Path):
    dsn = tmp_path / "CARTOL_0126_000001 (1).dsn"
    dsn.write_text("S10.G00.00.001,'x'\n", encoding="latin-1")
    found = locate_dsn_file(["CARTOL_0126_000001.dsn"], [tmp_path])
    assert found == dsn


def test_locate_dsn_file_finds_file_from_expanded_dsn_dir(tmp_path: Path):
    dsn_dir = tmp_path / "Config" / "Colorplast" / "DSN"
    dsn_dir.mkdir(parents=True)
    dsn = dsn_dir / "000005_0526_000001 (2).dsn"
    dsn.write_text("S10.G00.00.001,'x'\n", encoding="latin-1")

    found = locate_dsn_file(["000005_0526_000001.dsn"], [dsn_dir])

    assert found == dsn
