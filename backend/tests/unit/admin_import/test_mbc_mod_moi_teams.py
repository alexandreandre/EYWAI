"""Tests unitaires — import MOI/MOD MBC."""

from __future__ import annotations

from io import BytesIO
from unittest.mock import patch

import pytest

from app.modules.admin_import.application.mbc_mod_moi_teams import (
    match_employee_by_name,
    normalize_person_name,
    parse_mbc_mod_moi_rows,
    resolve_mbc_company_id,
    run_mbc_mod_moi_teams_import,
)

MBC_COMPANY = {
    "id": "co-mbc",
    "company_name": "Mont Blanc Composite",
    "siret": "75116833700028",
}

EMPLOYEES = [
    {
        "id": "emp-moi",
        "first_name": "Alice",
        "last_name": "MOIUSER",
        "employment_status": "actif",
        "team_id": None,
    },
    {
        "id": "emp-mod",
        "first_name": "Bob",
        "last_name": "MODUSER",
        "employment_status": "actif",
        "team_id": "team-mod-existing",
    },
    {
        "id": "emp-cad",
        "first_name": "Claire",
        "last_name": "CADUSER",
        "employment_status": "actif",
        "team_id": None,
    },
]


def _make_xlsx(rows: list[list[str]]) -> bytes:
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


FIXTURE_ROWS = [
    ["Quadratus - Liste des employés"],
    [],
    [],
    [],
    [
        "Numéro",
        "Identifiant",
        "Nom",
        "Nom marital",
        "Prénom",
        "Service",
        "Date de sortie",
    ],
    ["1", "A1", "MOIUSER", "", "Alice", "MOI", ""],
    ["2", "A2", "MODUSER", "", "Bob", "MOD", ""],
    ["3", "A3", "CADUSER", "", "Claire", "CAD", ""],
    ["4", "A4", "EXITED", "", "Denis", "MOD", "01/01/2025"],
    ["5", "A5", "UNKNOWN", "", "Eve", "MOD", ""],
    ["6", "A6", "OTHER", "", "Pascal", "MAI", ""],
]


class TestNormalizePersonName:
    def test_unicode_and_casefold(self):
        assert normalize_person_name("  ÉLISE  ") == normalize_person_name("elise")
        assert normalize_person_name("François") == "francois"


class TestMatchEmployeeByName:
    def test_exact_match(self):
        emp, reason = match_employee_by_name("Alice", "MOIUSER", EMPLOYEES)
        assert emp is not None
        assert emp["id"] == "emp-moi"
        assert reason is None

    def test_not_found(self):
        emp, reason = match_employee_by_name("Eve", "UNKNOWN", EMPLOYEES)
        assert emp is None
        assert reason == "not_found"

    def test_ambiguous(self):
        dupes = EMPLOYEES + [
            {
                "id": "emp-dup",
                "first_name": "Alice",
                "last_name": "MOIUSER",
                "employment_status": "actif",
                "team_id": None,
            }
        ]
        emp, reason = match_employee_by_name("Alice", "MOIUSER", dupes)
        assert emp is None
        assert reason == "ambiguous"


class TestParseMbcModMoiRows:
    def test_reads_quadra_export(self):
        content = _make_xlsx(FIXTURE_ROWS)
        rows = parse_mbc_mod_moi_rows(content, "paie MBC.xlsx")
        assert len(rows) == 6
        assert rows[0]["team_name"] == "MOI"
        assert rows[2]["team_name"] == "MOI"
        assert rows[5]["team_name"] is None


class TestResolveMbcCompany:
    def test_by_explicit_id(self):
        with patch(
            "app.modules.admin_import.application.mbc_mod_moi_teams.repo.find_company",
            return_value=MBC_COMPANY,
        ):
            company = resolve_mbc_company_id("co-mbc")
            assert company["id"] == "co-mbc"

    def test_by_normalized_name(self):
        with patch(
            "app.modules.admin_import.application.mbc_mod_moi_teams.repo.find_company_by_normalized_name",
            return_value=MBC_COMPANY,
        ):
            company = resolve_mbc_company_id()
            assert company["company_name"] == "Mont Blanc Composite"


@pytest.fixture
def mock_import_deps():
    teams_state = {
        "MOI": {"id": "team-moi", "name": "MOI", "created": False},
        "MOD": {"id": "team-mod", "name": "MOD", "created": False},
    }

    def fake_ensure(company_id, *, dry_run):
        if dry_run:
            return teams_state
        return teams_state

    with patch(
        "app.modules.admin_import.application.mbc_mod_moi_teams.resolve_mbc_company_id",
        return_value=MBC_COMPANY,
    ), patch(
        "app.modules.admin_import.application.mbc_mod_moi_teams._list_active_employees_with_team",
        return_value=EMPLOYEES,
    ), patch(
        "app.modules.admin_import.application.mbc_mod_moi_teams._ensure_mod_moi_teams",
        side_effect=fake_ensure,
    ), patch(
        "app.modules.admin_import.application.mbc_mod_moi_teams.assign_employee_to_team",
    ) as assign_mock:
        yield assign_mock, teams_state


class TestRunMbcModMoiTeamsImport:
    def test_dry_run_report(self, mock_import_deps):
        assign_mock, _ = mock_import_deps
        content = _make_xlsx(FIXTURE_ROWS)
        report = run_mbc_mod_moi_teams_import(
            content=content,
            filename="paie MBC.xlsx",
            company_id="co-mbc",
            dry_run=True,
        )

        summary = report["summary"]
        assert summary["rows_total"] == 6
        assert summary["rows_with_exit_date"] == 1
        assert summary["rows_without_team_mapping"] == 1
        assert summary["rows_eligible"] == 4
        assert summary["team_moi"] == 2
        assert summary["team_mod"] == 2
        assert summary["source_service_moi"] == 1
        assert summary["source_service_cad"] == 1
        assert summary["matched"] == 3
        assert summary["unmatched"] == 1
        assert len(report["unmatched"]) == 1
        assert report["unmatched"][0]["first_name"] == "Eve"
        assert summary["would_assign"] + summary["would_reassign"] + summary["already_correct"] == 3
        assign_mock.assert_not_called()

    def test_apply_assigns_teams(self, mock_import_deps):
        assign_mock, _ = mock_import_deps
        content = _make_xlsx(FIXTURE_ROWS)
        report = run_mbc_mod_moi_teams_import(
            content=content,
            filename="paie MBC.xlsx",
            company_id="co-mbc",
            dry_run=False,
        )

        assert report["summary"]["assigned"] == 3
        assert assign_mock.call_count == 3
        assign_mock.assert_any_call("emp-moi", "team-moi", "co-mbc")
        assign_mock.assert_any_call("emp-mod", "team-mod", "co-mbc")
        assign_mock.assert_any_call("emp-cad", "team-moi", "co-mbc")

    def test_never_guesses_unknown_employee(self, mock_import_deps):
        content = _make_xlsx(FIXTURE_ROWS)
        report = run_mbc_mod_moi_teams_import(
            content=content,
            filename="paie MBC.xlsx",
            company_id="co-mbc",
            dry_run=True,
        )
        unmatched_names = [
            f"{row['first_name']} {row['last_name']}" for row in report["unmatched"]
        ]
        assert unmatched_names == ["Eve UNKNOWN"]
