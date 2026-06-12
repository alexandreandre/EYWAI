"""Tests unitaires — export virement salaires / IBAN."""

import pytest

from app.modules.exports.infrastructure.export_paiement_salaires import (
    get_paiement_salaires_data,
)

pytestmark = pytest.mark.unit

_VALID_IBAN = "FR7630001007941234567890185"


def _payslip_row(
    employee_id: str,
    first_name: str,
    last_name: str,
    coordonnees_bancaires,
    net_a_payer: float = 1500.0,
):
    return {
        "id": "ps-1",
        "employee_id": employee_id,
        "month": 6,
        "year": 2026,
        "payslip_data": {"net_a_payer": net_a_payer, "salaire_brut": 2000.0},
        "employees": {
            "id": employee_id,
            "first_name": first_name,
            "last_name": last_name,
            "coordonnees_bancaires": coordonnees_bancaires,
            "hire_date": "2024-01-01",
            "contract_type": "CDI",
            "statut": "cadre",
        },
    }


class TestPaiementSalairesIban:
    def test_null_coords_triggers_iban_anomaly(self, monkeypatch):
        row = _payslip_row("emp-1", "Fredo", "André", None)
        monkeypatch.setattr(
            "app.modules.exports.infrastructure.export_paiement_salaires.supabase.table",
            lambda name: _FakeQuery(name, payslips=[row], exits=[]),
        )
        data, _, anomalies, _ = get_paiement_salaires_data("co-1", "2026-06")
        assert data == []
        assert any("IBAN" in a["message"] and "Fredo" in a["message"] for a in anomalies)

    def test_valid_iban_json_string_coords(self, monkeypatch):
        coords = f'{{"iban": "{_VALID_IBAN}", "bic": "BNPAFRPP"}}'
        row = _payslip_row("emp-1", "Fredo", "André", coords)
        monkeypatch.setattr(
            "app.modules.exports.infrastructure.export_paiement_salaires.supabase.table",
            lambda name: _FakeQuery(name, payslips=[row], exits=[]),
        )
        data, totals, anomalies, _ = get_paiement_salaires_data("co-1", "2026-06")
        assert len(data) == 1
        assert data[0]["IBAN"] == _VALID_IBAN
        assert anomalies == []
        assert totals["virements_count"] == 1


class _FakeQuery:
    def __init__(self, table_name: str, payslips: list, exits: list):
        self._table_name = table_name
        self._payslips = payslips
        self._exits = exits

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def in_(self, *_args, **_kwargs):
        return self

    def execute(self):
        data = self._payslips if self._table_name == "payslips" else self._exits
        return _FakeResult(data)


class _FakeResult:
    def __init__(self, data):
        self.data = data
