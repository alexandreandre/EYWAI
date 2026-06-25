"""Tests unitaires — fallback filiale ciblée import CP."""

from unittest.mock import patch

from app.modules.admin_import.application.cp_import import (
    _apply_target_company_scope,
    parse_cp_import_files,
)
from app.modules.admin_import.application.cp_payslip_parser import ParsedPayslipPage

CARTOL = {
    "id": "co-cartol",
    "company_name": "Cartol Industrie",
    "siret": "95147478200019",
}

LEWIS = {
    "id": "co-lewis",
    "company_name": "LEWIS",
    "siret": "95147478200020",
}


class TestApplyTargetCompanyScope:
    def test_fallback_when_siret_unresolved(self):
        company, warnings = _apply_target_company_scope(
            None,
            ["Entreprise SIRET 95147478200020 introuvable dans EYWAI."],
            CARTOL,
            "95147478200020",
        )
        assert company is CARTOL
        assert any("rapprochement sur Cartol Industrie" in w for w in warnings)
        assert not any("introuvable dans EYWAI" in w for w in warnings)

    def test_keeps_match_when_same_company(self):
        company, warnings = _apply_target_company_scope(
            CARTOL,
            [],
            CARTOL,
            "95147478200019",
        )
        assert company is CARTOL
        assert warnings == []

    def test_forces_target_when_resolved_elsewhere(self):
        company, warnings = _apply_target_company_scope(
            LEWIS,
            [],
            CARTOL,
            "95147478200020",
        )
        assert company is CARTOL
        assert any("rapprochement forcé" in w for w in warnings)


class TestParseCpImportTargetCompany:
    def test_unknown_siret_uses_target_company_for_matching(self):
        page = ParsedPayslipPage(
            source_file="05-26 CARTOL.pdf",
            page_index=1,
            parse_format="cegid_clarifie",
            siret="95147478200020",
            company_name="CARTOL",
            matricule="ALVES",
            raw_name="ALVES Lucas",
            year=2026,
            month=5,
            period_label="Mai 2026",
            cp_n1_solde=0.0,
            cp_n_solde=3.67,
        )
        employees = [
            {
                "id": "e-alves",
                "first_name": "Lucas",
                "last_name": "ALVES",
                "email": "",
                "employee_folder_name": "ALVES_Lucas",
                "time_tracking_id": "ALVES",
            },
        ]

        with patch(
            "app.modules.admin_import.application.cp_import.parse_pdf_file",
            return_value=([page], []),
        ), patch(
            "app.modules.admin_import.application.cp_import.repo.find_company",
            return_value=CARTOL,
        ), patch(
            "app.modules.admin_import.application.cp_import.repo.resolve_company_from_payslip",
            return_value=(None, ["Entreprise SIRET 95147478200020 introuvable dans EYWAI."]),
        ), patch(
            "app.modules.admin_import.application.cp_import.repo.list_employees_by_company_ids",
            return_value={"co-cartol": employees},
        ), patch(
            "app.modules.admin_import.application.cp_import.get_adjustments_by_employees_year",
            return_value={},
        ), patch(
            "app.modules.admin_import.application.cp_import._compute_current_cp_soldes",
            return_value=(None, None),
        ):
            result = parse_cp_import_files(
                [("05-26 CARTOL.pdf", b"%PDF")],
                target_company_id="co-cartol",
            )

        assert result["summary"]["error"] == 0
        assert result["summary"]["ready"] == 1
        row = result["rows"][0]
        assert row["company_id"] == "co-cartol"
        assert row["employee_id"] == "e-alves"
        assert row["review_status"] == "ok"
        assert not any("introuvable dans EYWAI" in w for w in row["warnings"])
