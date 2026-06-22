"""Tests unitaires — commit import CP."""

from unittest.mock import patch

from app.modules.admin_import.application.cp_import import commit_cp_import
from app.modules.admin_import.schemas.requests import CpImportCommitBody, CpImportCommitRow


class TestCommitCpImport:
    def test_applies_confirmed_rows(self):
        with patch(
            "app.modules.admin_import.application.cp_import.repo"
        ) as mock_repo, patch(
            "app.modules.admin_import.application.cp_import.apply_cp_solde_import"
        ) as mock_apply:
            mock_repo.list_company_employees.return_value = [
                {"id": "emp-1", "first_name": "Samir", "last_name": "BOUFRIDA"}
            ]
            body = CpImportCommitBody(
                rows=[
                    CpImportCommitRow(
                        row_index=1,
                        company_id="co-1",
                        employee_id="emp-1",
                        year=2026,
                        cp_n1_solde=0.0,
                        cp_n_solde=11.96,
                        source_file="test.pdf",
                        period_label="Mai 2026",
                        confirmed=True,
                    )
                ]
            )
            result = commit_cp_import(body)
            assert result["applied"] == 1
            mock_apply.assert_called_once()
            kwargs = mock_apply.call_args.kwargs
            assert kwargs["cp_n1_solde"] == 0.0
            assert kwargs["cp_n_solde"] == 11.96
            assert "Mai 2026" in kwargs["note"]

    def test_skips_unconfirmed(self):
        body = CpImportCommitBody(
            rows=[
                CpImportCommitRow(
                    row_index=1,
                    company_id="co-1",
                    employee_id="emp-1",
                    year=2026,
                    confirmed=False,
                )
            ]
        )
        result = commit_cp_import(body)
        assert result["applied"] == 0
        assert result["skipped"] == 1
