"""Tests : rapprochement NIR 15↔13 + advisories de situation dans la réconciliation."""

from datetime import date
from unittest.mock import patch

import pytest

from app.modules.dsn_import.application.workforce_reconciliation import compute_workforce_gaps

pytestmark = pytest.mark.unit

COMPANY_ID = "co-1"
MONTHLY = "monthly"
MARCH = {"cumul_periods": ["2026-03"]}


def _employee_item(nir: str, *, is_existing: bool = True):
    return {
        "item_type": "employee",
        "source_ref": f"emp:siret:{nir}",
        "is_existing": is_existing,
        "existing_employee_id": None,
        "mapped_payload": {
            "nir": nir,
            "first_name": "Mohamed",
            "last_name": "Osmani",
            "contract_end_date": None,
        },
    }


def _absence_item(nir: str, days):
    return {
        "item_type": "absence",
        "mapped_payload": {
            "nir": nir,
            "absence_type": "arret_maladie",
            "selected_days": [d.isoformat() for d in days],
        },
    }


def _cumul_item(nir: str, *, brut: float, net: float):
    return {
        "item_type": "cumul",
        "mapped_payload": {
            "nir": nir,
            "period": "2026-03",
            "month_totals": {"brut": brut, "net_imposable": net},
        },
    }


def _march_business_days():
    return [date(2026, 3, d) for d in range(1, 32) if date(2026, 3, d).weekday() < 5]


def _active(nir: str, **overrides):
    base = {
        "id": "emp-osmani",
        "first_name": "Mohamed",
        "last_name": "Osmani",
        "nir": nir,
        "employment_status": "actif",
        "hire_date": "2024-01-08",
    }
    base.update(overrides)
    return base


@patch("app.modules.dsn_import.application.workforce_reconciliation.repo")
class TestNirMatchingAndSituations:
    def test_nir_15_in_db_matches_dsn_13_no_phantom_missing(self, mock_repo):
        # Base : NIR 15 chiffres ; DSN : même NIR à 13 (sans clé). Doit se rapprocher.
        mock_repo.list_active_employees_with_nir.return_value = [_active("187059935222362")]
        mock_repo.list_active_employees_without_nir.return_value = []
        mock_repo.find_company_by_id.return_value = {"company_name": "MBC"}

        summary, anomalies = compute_workforce_gaps(
            [_employee_item("1870599352223")],
            target_company_id=COMPANY_ID,
            import_mode=MONTHLY,
            summary=MARCH,
        )
        missing = [g for g in summary["gaps"] if g["gap_type"] == "missing_from_dsn"]
        assert missing == []

    def test_full_month_arret_zero_pay_emits_prolonged_absence_advisory(self, mock_repo):
        mock_repo.list_active_employees_with_nir.return_value = [_active("187059935222362")]
        mock_repo.list_active_employees_without_nir.return_value = []
        mock_repo.find_company_by_id.return_value = {"company_name": "MBC"}

        items = [
            _employee_item("1870599352223"),
            _absence_item("1870599352223", _march_business_days()),
            _cumul_item("1870599352223", brut=0.0, net=-234.59),
        ]
        summary, anomalies = compute_workforce_gaps(
            items,
            target_company_id=COMPANY_ID,
            import_mode=MONTHLY,
            summary=MARCH,
        )
        advisories = summary.get("advisories") or []
        assert len(advisories) == 1
        assert advisories[0]["situation"] == "prolonged_absence"
        assert advisories[0]["employee_id"] == "emp-osmani"
        assert advisories[0]["recommendation"]
        assert any(a.get("code") == "employee_dsn_situation_advisory" for a in anomalies)

    def test_active_normal_emits_no_advisory(self, mock_repo):
        mock_repo.list_active_employees_with_nir.return_value = [_active("187059935222362")]
        mock_repo.list_active_employees_without_nir.return_value = []
        mock_repo.find_company_by_id.return_value = {"company_name": "MBC"}

        items = [
            _employee_item("1870599352223"),
            _cumul_item("1870599352223", brut=2000.0, net=1550.0),
        ]
        summary, anomalies = compute_workforce_gaps(
            items,
            target_company_id=COMPANY_ID,
            import_mode=MONTHLY,
            summary=MARCH,
        )
        assert (summary.get("advisories") or []) == []

    def test_advisories_do_not_block_commit(self, mock_repo):
        # Une advisory (absence prolongée) ne doit pas ajouter d'écart bloquant.
        mock_repo.list_active_employees_with_nir.return_value = [_active("187059935222362")]
        mock_repo.list_active_employees_without_nir.return_value = []
        mock_repo.find_company_by_id.return_value = {"company_name": "MBC"}

        items = [
            _employee_item("1870599352223"),
            _absence_item("1870599352223", _march_business_days()),
            _cumul_item("1870599352223", brut=0.0, net=-234.59),
        ]
        summary, _ = compute_workforce_gaps(
            items,
            target_company_id=COMPANY_ID,
            import_mode=MONTHLY,
            summary=MARCH,
        )
        assert summary["gaps"] == []
        assert summary["unresolved_count"] == 0
