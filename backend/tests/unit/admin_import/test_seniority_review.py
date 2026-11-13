"""Garde-fous de revue d'ancienneté, sans base ni données de salariés réels."""

from unittest.mock import patch

import pytest

from app.modules.admin_import.application import seniority_import as service
from app.modules.admin_import.application.seniority_excel import (
    parse_seniority_date_cell,
)
from app.modules.admin_import.schemas.requests import SeniorityImportCommitBody
from app.modules.admin_import.schemas.responses import SeniorityImportParseResponse


@pytest.fixture
def isolated_import():
    employees = [
        {
            "id": "sal-test", "first_name": "Alix", "last_name": "EXEMPLE",
            "time_tracking_id": "TEST001", "employment_status": "actif",
            "hire_date": "2020-01-06", "seniority_reference_date": "2019-01-07",
        },
    ]
    with (
        patch.object(service.repo, "find_company", return_value={"id": "co-test"}),
        patch.object(service, "_list_employees_for_seniority", return_value=employees),
        patch.object(service.employee_commands, "update_employee") as update,
    ):
        yield employees, update


def commit_row(**changes):
    return {
        "row_index": 5, "employee_id": "sal-test",
        "seniority_date": "2018-09-03", "confirmed": True, **changes,
    }


@pytest.mark.parametrize("raw", ["31/02/2026", "31/04/2026", "31022026", "2026-02-31"])
def test_date_impossible_reste_bloquante(raw):
    assert parse_seniority_date_cell(raw) is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("29/02/2024", "2024-02-29"), ("2018-09-03", "2018-09-03"), ("44927", "2023-01-01")],
)
def test_formats_date_valides_conserves(raw, expected):
    assert parse_seniority_date_cell(raw) == expected


def test_apercu_transmet_les_dates_du_salarie_pour_association_manuelle(isolated_import):
    content = b"Numero;Date ancien;Nom\nTEST001;03/09/2018;EXEMPLE\n"
    result = service.parse_seniority_import_file(content, "anciennete.csv", "co-test")
    response = SeniorityImportParseResponse(**result)
    assert response.roster[0].current_seniority_date == "2019-01-07"
    assert response.roster[0].current_hire_date == "2020-01-06"
    assert response.rows[0].current_hire_date == "2020-01-06"


def test_matricule_seul_suffit_si_unique_dans_la_societe(isolated_import):
    content = b"Numero;Date ancien\nTEST001;03/09/2018\n"
    result = service.parse_seniority_import_file(content, "anciennete.csv", "co-test")
    assert result["summary"]["ready"] == 1
    assert result["rows"][0]["employee_id"] == "sal-test"


def test_deux_dates_pour_un_salarie_ne_sont_pas_pretes_automatiquement(isolated_import):
    content = (
        b"Numero;Date ancien;Nom\n"
        b"TEST001;03/09/2018;EXEMPLE\nTEST001;04/09/2018;EXEMPLE\n"
    )
    result = service.parse_seniority_import_file(content, "anciennete.csv", "co-test")
    assert result["summary"]["ready"] == 0
    assert result["summary"]["warning"] == 2
    assert all("Plusieurs lignes" in row["warnings"][-1] for row in result["rows"])


@pytest.mark.parametrize(
    "changes",
    [{"confirmed": False}, {"employee_id": "hors-societe"},
     {"seniority_date": "2026-02-31"}, {"seniority_date": "03092018"},
     {"seniority_date": "2019-01-07"}, {"seniority_date": ""}],
)
def test_ligne_non_retenue_invalide_ou_identique_sans_ecriture(isolated_import, changes):
    _, update = isolated_import
    result = service.commit_seniority_import(
        SeniorityImportCommitBody(company_id="co-test", rows=[commit_row(**changes)]),
    )
    assert result["applied"] == 0
    assert result["skipped"] == 1
    update.assert_not_called()


def test_deux_lignes_confirmees_n_ecrasent_pas_successivement_la_meme_date(isolated_import):
    _, update = isolated_import
    result = service.commit_seniority_import(SeniorityImportCommitBody(
        company_id="co-test", rows=[commit_row(), commit_row(row_index=6, seniority_date="2017-01-02")],
    ))
    assert result["applied"] == 0
    assert result["skipped"] == 2
    assert len(result["errors"]) == 2
    update.assert_not_called()


def test_une_seule_ligne_confirmee_modifie_uniquement_la_reference(isolated_import):
    employees, update = isolated_import
    update.return_value = employees[0]
    result = service.commit_seniority_import(SeniorityImportCommitBody(
        company_id="co-test", rows=[commit_row(), commit_row(row_index=6, confirmed=False)],
    ))
    assert result["applied"] == 1
    assert result["skipped"] == 1
    update.assert_called_once_with("sal-test", {"seniority_reference_date": "2018-09-03"})
    assert employees[0]["hire_date"] == "2020-01-06"


def test_reapplication_date_identique_sans_seconde_ecriture(isolated_import):
    employees, update = isolated_import

    def apply_patch(_employee_id, employee_patch):
        employees[0].update(employee_patch)
        return employees[0]

    update.side_effect = apply_patch
    body = SeniorityImportCommitBody(company_id="co-test", rows=[commit_row()])
    assert service.commit_seniority_import(body)["applied"] == 1
    assert service.commit_seniority_import(body)["skipped"] == 1
    assert update.call_count == 1
