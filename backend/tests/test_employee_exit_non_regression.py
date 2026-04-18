"""
Non-régression : bundle sortie (3 PDF + traçage + portabilité conditionnelle).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.employee_exits.application import commands


def _exit_row(exit_type: str) -> dict:
    return {
        "id": "exit-uuid-1",
        "employee_id": "emp-1",
        "company_id": "comp-1",
        "exit_type": exit_type,
        "last_working_day": "2025-12-31",
        "employees": {
            "first_name": "Jean",
            "last_name": "Dupont",
            "hire_date": "2020-01-15",
            "job_title": "Technicien",
            "date_naissance": "1990-05-10",
            "salaire_de_base": {"valeur": 2500.0},
        },
    }


@pytest.fixture
def mock_sb():
    return MagicMock(name="supabase_client")


@patch.object(commands, "get_company_by_id", return_value={"company_name": "ACME", "siret": "123"})
@patch.object(
    commands,
    "get_exit_storage_provider",
    return_value=MagicMock(),
)
@patch.object(commands, "get_indemnity_calculator")
@patch.object(commands, "get_exit_document_generator")
@patch.object(commands, "ExitDocumentRepository")
@patch.object(commands, "EmployeeExitRepository")
def test_exit_generates_three_core_documents(
    mock_exit_repo_cls,
    mock_doc_repo_cls,
    mock_get_gen,
    mock_get_calc,
    mock_get_storage,
    mock_get_company,
    mock_sb,
):
    exit_row = _exit_row("demission")
    inst_exit = MagicMock()
    inst_exit.get_with_employee.return_value = exit_row
    inst_exit.update.return_value = exit_row
    mock_exit_repo_cls.return_value = inst_exit

    inst_doc = MagicMock()
    inst_doc.create.return_value = {"id": "doc-row-id"}
    mock_doc_repo_cls.return_value = inst_doc

    gen = MagicMock()
    gen.generate_solde_tout_compte.return_value = b"%PDF-solde"
    gen.generate_certificat_travail.return_value = b"%PDF-cert"
    gen.generate_attestation_pole_emploi.return_value = b"%PDF-pe"
    mock_get_gen.return_value = gen

    calc = MagicMock()
    calc.calculate.return_value = {
        "indemnite_conges": {"jours_restants": 0},
        "total_net_indemnities": 0.0,
    }
    mock_get_calc.return_value = calc

    storage = mock_get_storage.return_value

    with patch.object(commands.document_service, "trace_existing_document", return_value="t1"):
        with patch.object(commands.document_service, "generate_document"):
            commands._run_post_create_indemnities_and_docs(
                "exit-uuid-1", "comp-1", "user-1", mock_sb
            )

    assert inst_doc.create.call_count == 3
    assert gen.generate_certificat_travail.called
    assert gen.generate_attestation_pole_emploi.called
    assert gen.generate_solde_tout_compte.called
    assert storage.upload.call_count == 3


@patch.object(commands, "get_company_by_id", return_value={"company_name": "ACME", "siret": "123"})
@patch.object(commands, "get_exit_storage_provider", return_value=MagicMock())
@patch.object(commands, "get_indemnity_calculator")
@patch.object(commands, "get_exit_document_generator")
@patch.object(commands, "ExitDocumentRepository")
@patch.object(commands, "EmployeeExitRepository")
def test_licenciement_adds_two_portability_documents(
    mock_exit_repo_cls,
    mock_doc_repo_cls,
    mock_get_gen,
    mock_get_calc,
    mock_get_storage,
    mock_get_company,
    mock_sb,
):
    exit_row = _exit_row("licenciement")
    inst_exit = MagicMock()
    inst_exit.get_with_employee.return_value = exit_row
    inst_exit.update.return_value = exit_row
    mock_exit_repo_cls.return_value = inst_exit

    inst_doc = MagicMock()
    inst_doc.create.return_value = {"id": "doc-row-id"}
    mock_doc_repo_cls.return_value = inst_doc

    gen = MagicMock()
    gen.generate_solde_tout_compte.return_value = b"%PDF-solde"
    gen.generate_certificat_travail.return_value = b"%PDF-cert"
    gen.generate_attestation_pole_emploi.return_value = b"%PDF-pe"
    mock_get_gen.return_value = gen

    calc = MagicMock()
    calc.calculate.return_value = {
        "indemnite_conges": {"jours_restants": 0},
        "total_net_indemnities": 0.0,
    }
    mock_get_calc.return_value = calc

    storage = mock_get_storage.return_value

    with patch.object(commands.document_service, "trace_existing_document", return_value="t1"):
        with patch.object(
            commands.document_service,
            "generate_document",
            return_value={
                "document_id": "stub-gd",
                "is_eywai_template": True,
                "file_url": "",
                "status": "brouillon",
            },
        ):
            with patch.object(commands.document_service, "delete_generated_document"):
                with patch.object(
                    commands.portability_generator,
                    "generate_portabilite_mutuelle",
                    return_value=b"%PDF-mut",
                ):
                    with patch.object(
                        commands.portability_generator,
                        "generate_portabilite_prevoyance",
                        return_value=b"%PDF-prev",
                    ):
                        commands._run_post_create_indemnities_and_docs(
                            "exit-uuid-1", "comp-1", "user-1", mock_sb
                        )

    assert inst_doc.create.call_count == 5
    assert storage.upload.call_count == 5


@patch.object(commands, "get_company_by_id", return_value={"company_name": "ACME", "siret": "123"})
@patch.object(commands, "get_exit_storage_provider", return_value=MagicMock())
@patch.object(commands, "get_indemnity_calculator")
@patch.object(commands, "get_exit_document_generator")
@patch.object(commands, "ExitDocumentRepository")
@patch.object(commands, "EmployeeExitRepository")
def test_demission_no_portability_extra(
    mock_exit_repo_cls,
    mock_doc_repo_cls,
    mock_get_gen,
    mock_get_calc,
    mock_get_storage,
    mock_get_company,
    mock_sb,
):
    exit_row = _exit_row("demission")
    inst_exit = MagicMock()
    inst_exit.get_with_employee.return_value = exit_row
    inst_exit.update.return_value = exit_row
    mock_exit_repo_cls.return_value = inst_exit

    inst_doc = MagicMock()
    inst_doc.create.return_value = {"id": "doc-row-id"}
    mock_doc_repo_cls.return_value = inst_doc

    gen = MagicMock()
    gen.generate_solde_tout_compte.return_value = b"%PDF-solde"
    gen.generate_certificat_travail.return_value = b"%PDF-cert"
    gen.generate_attestation_pole_emploi.return_value = b"%PDF-pe"
    mock_get_gen.return_value = gen

    calc = MagicMock()
    calc.calculate.return_value = {
        "indemnite_conges": {"jours_restants": 0},
        "total_net_indemnities": 0.0,
    }
    mock_get_calc.return_value = calc

    storage = mock_get_storage.return_value

    with patch.object(commands.document_service, "trace_existing_document", return_value="t1"):
        with patch.object(commands.document_service, "generate_document") as mock_gen:
            commands._run_post_create_indemnities_and_docs(
                "exit-uuid-1", "comp-1", "user-1", mock_sb
            )
            mock_gen.assert_not_called()

    assert inst_doc.create.call_count == 3
    assert storage.upload.call_count == 3


@patch.object(commands, "get_company_by_id", return_value={"company_name": "ACME", "siret": "123"})
@patch.object(commands, "get_exit_storage_provider", return_value=MagicMock())
@patch.object(commands, "get_indemnity_calculator")
@patch.object(commands, "get_exit_document_generator")
@patch.object(commands, "ExitDocumentRepository")
@patch.object(commands, "EmployeeExitRepository")
def test_rupture_conventionnelle_portability(
    mock_exit_repo_cls,
    mock_doc_repo_cls,
    mock_get_gen,
    mock_get_calc,
    mock_get_storage,
    mock_get_company,
    mock_sb,
):
    exit_row = _exit_row("rupture_conventionnelle")
    inst_exit = MagicMock()
    inst_exit.get_with_employee.return_value = exit_row
    inst_exit.update.return_value = exit_row
    mock_exit_repo_cls.return_value = inst_exit

    inst_doc = MagicMock()
    inst_doc.create.return_value = {"id": "doc-row-id"}
    mock_doc_repo_cls.return_value = inst_doc

    gen = MagicMock()
    gen.generate_solde_tout_compte.return_value = b"%PDF-solde"
    gen.generate_certificat_travail.return_value = b"%PDF-cert"
    gen.generate_attestation_pole_emploi.return_value = b"%PDF-pe"
    mock_get_gen.return_value = gen

    calc = MagicMock()
    calc.calculate.return_value = {
        "indemnite_conges": {"jours_restants": 0},
        "total_net_indemnities": 0.0,
    }
    mock_get_calc.return_value = calc

    storage = mock_get_storage.return_value

    with patch.object(commands.document_service, "trace_existing_document", return_value="t1"):
        with patch.object(
            commands.document_service,
            "generate_document",
            return_value={
                "document_id": "stub-gd",
                "is_eywai_template": True,
                "file_url": "",
                "status": "brouillon",
            },
        ):
            with patch.object(commands.document_service, "delete_generated_document"):
                with patch.object(
                    commands.portability_generator,
                    "generate_portabilite_mutuelle",
                    return_value=b"%PDF-mut",
                ):
                    with patch.object(
                        commands.portability_generator,
                        "generate_portabilite_prevoyance",
                        return_value=b"%PDF-prev",
                    ):
                        commands._run_post_create_indemnities_and_docs(
                            "exit-uuid-1", "comp-1", "user-1", mock_sb
                        )

    assert inst_doc.create.call_count == 5


@patch.object(commands, "get_company_by_id", return_value={"company_name": "ACME", "siret": "123"})
@patch.object(commands, "get_exit_storage_provider", return_value=MagicMock())
@patch.object(commands, "get_indemnity_calculator")
@patch.object(commands, "get_exit_document_generator")
@patch.object(commands, "ExitDocumentRepository")
@patch.object(commands, "EmployeeExitRepository")
def test_trace_failure_does_not_abort_exit_bundle(
    mock_exit_repo_cls,
    mock_doc_repo_cls,
    mock_get_gen,
    mock_get_calc,
    mock_get_storage,
    mock_get_company,
    mock_sb,
):
    exit_row = _exit_row("demission")
    inst_exit = MagicMock()
    inst_exit.get_with_employee.return_value = exit_row
    inst_exit.update.return_value = exit_row
    mock_exit_repo_cls.return_value = inst_exit

    inst_doc = MagicMock()
    inst_doc.create.return_value = {"id": "doc-row-id"}
    mock_doc_repo_cls.return_value = inst_doc

    gen = MagicMock()
    gen.generate_solde_tout_compte.return_value = b"%PDF-solde"
    gen.generate_certificat_travail.return_value = b"%PDF-cert"
    gen.generate_attestation_pole_emploi.return_value = b"%PDF-pe"
    mock_get_gen.return_value = gen

    calc = MagicMock()
    calc.calculate.return_value = {
        "indemnite_conges": {"jours_restants": 0},
        "total_net_indemnities": 0.0,
    }
    mock_get_calc.return_value = calc

    with patch.object(
        commands.document_service,
        "trace_existing_document",
        side_effect=RuntimeError("insert generated_documents KO"),
    ):
        commands._run_post_create_indemnities_and_docs(
            "exit-uuid-1", "comp-1", "user-1", mock_sb
        )

    assert inst_doc.create.call_count == 3
    assert gen.generate_certificat_travail.called
