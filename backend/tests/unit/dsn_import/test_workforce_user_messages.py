"""Tests fabriques anomalies réconciliation effectifs."""

import pytest

from app.modules.dsn_import.domain.user_messages import (
    employee_workforce_gap_anomaly,
    workforce_reconciliation_summary_anomaly,
)

pytestmark = pytest.mark.unit


def test_workforce_reconciliation_summary_anomaly():
    anomaly = workforce_reconciliation_summary_anomaly(
        company_name="Test SA",
        gap_count=2,
        period="2026-03",
    )
    assert anomaly["code"] == "workforce_reconciliation_required"
    assert "2 écart" in anomaly["message"]
    assert "2026-03" in anomaly["message"]


def test_employee_missing_from_dsn_anomaly():
    gap = {
        "gap_id": "missing:emp-1",
        "employee_id": "emp-1",
        "employee_name": "Alex Jolly",
        "nir_masked": "…1111",
        "gap_type": "missing_from_dsn",
    }
    anomaly = employee_workforce_gap_anomaly(gap=gap)
    assert anomaly["code"] == "employee_missing_from_dsn"
    assert "Alex Jolly" in anomaly["message"]
    assert anomaly["source_ref"] == "gap:emp-1"
