"""Tests messages utilisateur import DSN."""

from fastapi import HTTPException

from app.modules.dsn_import.domain.user_messages import (
    employee_other_company_anomaly,
    humanize_commit_error,
    issue_to_legacy_string,
    target_siret_missing_anomaly,
)


def test_employee_other_company_anomaly_message():
    anomaly = employee_other_company_anomaly(
        source_ref="emp:80248516900022:1630899139837",
        employee_name="Vitor DA SILVA CARDOSO",
        nir="1630899139837",
        target_company_name="Colorplast",
        existing_company_name="Comitech Composite",
    )
    assert anomaly["code"] == "employee_other_company"
    assert "Comitech Composite" in anomaly["message"]
    assert "Colorplast" in anomaly["message"]
    assert anomaly["hint"]


def test_target_siret_missing_anomaly():
    anomaly = target_siret_missing_anomaly(
        target_company_name="Colorplast",
        dsn_siret="80248516900022",
    )
    assert anomaly["code"] == "target_siret_missing"
    assert "80248516900022" in anomaly["message"]


def test_humanize_commit_error_duplicate_nir():
    exc = Exception(
        'duplicate key value violates unique constraint "employees_nir_key" '
        'Key (nir)=(1630899139837) already exists.'
    )
    issue = humanize_commit_error(
        exc,
        source_ref="emp:80248516900022:1630899139837",
        item_label="Vitor DA SILVA CARDOSO",
    )
    assert issue["code"] == "duplicate_nir"
    assert "9837" in issue["message"]
    assert issue["hint"]


def test_humanize_commit_error_runtime_cross_company():
    issue = humanize_commit_error(
        RuntimeError(
            "NIR 1630899139837 déjà enregistré chez Comitech Composite — "
            "ignorez ce salarié à l'import ou corrigez la fiche manuellement."
        ),
        source_ref="emp:80248516900022:1630899139837",
    )
    assert issue["code"] == "employee_cross_company"
    assert "Comitech Composite" in issue["message"]


def test_humanize_commit_error_http_nir():
    issue = humanize_commit_error(
        HTTPException(status_code=400, detail="Ce numéro de sécurité sociale est déjà enregistré."),
        source_ref="emp:1:2",
    )
    assert issue["code"] == "duplicate_nir"


def test_issue_to_legacy_string():
    issue = humanize_commit_error(RuntimeError("Salarié NIR 123 introuvable pour cumuls"))
    legacy = issue_to_legacy_string(issue)
    assert "cumuls" in legacy.lower()


def test_humanize_commit_error_exit_transition():
    from app.modules.employee_exits.application.dto import EmployeeExitApplicationError

    issue = humanize_commit_error(
        EmployeeExitApplicationError(
            400,
            "Transition invalide de 'licenciement_convocation' vers 'licenciement_effective'. "
            "Transitions valides: licenciement_notifie, annulee",
        ),
        source_ref="exit:1:2:licenciement:031",
    )
    assert issue["code"] == "exit_transition_invalid"
    assert "clôture automatique" in issue["message"].lower()


def test_humanize_commit_error_fin_periode_essai_constraint():
    exc = Exception(
        "{'message': 'new row for relation \"employee_exits\" violates check constraint "
        "\"employee_exits_exit_type_check\"', 'code': '23514', "
        "'details': 'Failing row contains (..., fin_periode_essai, ...)'}"
    )
    issue = humanize_commit_error(exc, source_ref="exit:1:fin_periode_essai:037")
    assert issue["code"] == "exit_type_not_supported"


def test_humanize_commit_error_absence_blocked_by_exit():
    exc = Exception(
        "Impossible de créer une demande d'absence: le salarié est en processus de sortie "
        "(dernier jour: 2026-01-31)"
    )
    issue = humanize_commit_error(exc, source_ref="abs:1")
    assert issue["code"] == "absence_blocked_by_exit"


def test_humanize_commit_error_batch_creation_failed():
    issue = humanize_commit_error(RuntimeError("Impossible de créer le batch d'import"))
    assert issue["code"] == "batch_creation_failed"


def test_humanize_commit_error_employee_check_constraint():
    issue = humanize_commit_error(
        RuntimeError(
            'new row for relation "employees" violates check constraint '
            '"employees_salary_payment_method_check"'
        ),
        source_ref="emp:1:2",
    )
    assert issue["code"] == "employee_validation"
    assert "mode de paiement" in issue["message"]
    assert issue["meta"]["constraint"] == "employees_salary_payment_method_check"
