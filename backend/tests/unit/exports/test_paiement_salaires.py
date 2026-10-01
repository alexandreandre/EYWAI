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
    salary_payment_method: str = "virement",
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
            "salary_payment_method": salary_payment_method,
            "hire_date": "2024-01-01",
            "contract_type": "CDI",
            "statut": "cadre",
        },
    }


class TestPaiementSalairesIban:
    def test_null_coords_triggers_iban_anomaly(self, monkeypatch):
        row = _payslip_row("emp-1", "Salarié", "Fictif", None)
        monkeypatch.setattr(
            "app.modules.exports.infrastructure.export_paiement_salaires.supabase.table",
            lambda name: _FakeQuery(name, payslips=[row], exits=[]),
        )
        data, _, anomalies, _ = get_paiement_salaires_data("co-1", "2026-06")
        assert data == []
        assert any("IBAN" in a["message"] and "Fictif" in a["message"] for a in anomalies)

    def test_valid_iban_json_string_coords(self, monkeypatch):
        coords = f'{{"iban": "{_VALID_IBAN}", "bic": "BNPAFRPP"}}'
        row = _payslip_row("emp-1", "Salarié", "Fictif", coords)
        monkeypatch.setattr(
            "app.modules.exports.infrastructure.export_paiement_salaires.supabase.table",
            lambda name: _FakeQuery(name, payslips=[row], exits=[]),
        )
        data, totals, anomalies, _ = get_paiement_salaires_data("co-1", "2026-06")
        assert len(data) == 1
        assert data[0]["IBAN"] == _VALID_IBAN
        assert anomalies == []
        assert totals["virements_count"] == 1

    def test_cheque_payment_excluded_from_virements(self, monkeypatch):
        coords = f'{{"iban": "{_VALID_IBAN}", "bic": "BNPAFRPP"}}'
        row = _payslip_row(
            "emp-1",
            "Camille",
            "EXEMPLE",
            coords,
            salary_payment_method="cheque",
        )
        monkeypatch.setattr(
            "app.modules.exports.infrastructure.export_paiement_salaires.supabase.table",
            lambda name: _FakeQuery(name, payslips=[row], exits=[]),
        )
        data, totals, anomalies, warnings = get_paiement_salaires_data("co-1", "2026-06")
        assert data == []
        assert totals["virements_count"] == 0
        assert any("chèque" in w.lower() for w in warnings)
        assert anomalies == []


MOTIF_NET_NEGATIF = (
    "net à payer négatif : rien à virer ce mois-ci ; "
    "le report sur le mois suivant se propose depuis son bulletin"
)
_CHEMINS = (
    "app.modules.exports.infrastructure.export_paiement_salaires",
    "app.modules.payroll.exports.paiement_salaires",
)


class TestNetNegatifNeBloquePasLesVirements:
    """Un net ≤ 0 écarte le salarié avec un avertissement nommé ; les autres sont payés."""

    def _donnees(self, module_path, monkeypatch, net):
        import importlib

        module = importlib.import_module(module_path)
        coords = {"iban": _VALID_IBAN, "bic": "BNPAFRPP"}
        lignes = [
            _payslip_row("emp-1", "Salarié", "Fictif", coords, net_a_payer=net),
            _payslip_row("emp-2", "Camille", "Exemple", coords),
        ]
        monkeypatch.setattr(
            f"{module_path}.supabase.table",
            lambda name: _FakeQuery(name, payslips=lignes, exits=[]),
        )
        return module.get_paiement_salaires_data("co-1", "2026-09")

    @pytest.mark.parametrize("module_path", _CHEMINS)
    def test_net_negatif_ecarte_avec_un_avertissement_qui_dit_quoi_faire(self, module_path, monkeypatch):
        data, totals, anomalies, warnings = self._donnees(module_path, monkeypatch, -115.43)
        assert [r["Nom"] for r in data] == ["Exemple"]
        assert totals["virements_count"] == 1
        assert anomalies == []
        assert f"Salarié Fictif : {MOTIF_NET_NEGATIF}" in warnings

    @pytest.mark.parametrize("module_path", _CHEMINS)
    def test_net_nul_ecarte_sans_parler_de_report(self, module_path, monkeypatch):
        data, _, anomalies, warnings = self._donnees(module_path, monkeypatch, 0.0)
        assert [r["Nom"] for r in data] == ["Exemple"]
        assert anomalies == []
        assert "Salarié Fictif : net à payer nul : rien à virer ce mois-ci" in warnings

    def test_l_apercu_permet_de_generer_le_reste(self, monkeypatch):
        from app.modules.exports.infrastructure import export_paiement_salaires, export_sepa

        coords = {"iban": _VALID_IBAN, "bic": "BNPAFRPP"}
        lignes = [
            _payslip_row("emp-1", "Salarié", "Fictif", coords, net_a_payer=-115.43),
            _payslip_row("emp-2", "Camille", "Exemple", coords),
        ]
        monkeypatch.setattr(
            "app.modules.exports.infrastructure.export_paiement_salaires.supabase.table",
            lambda name: _FakeQuery(name, payslips=lignes, exits=[]),
        )
        assert export_paiement_salaires.preview_paiement_salaires("co-1", "2026-09")["can_generate"]
        assert export_sepa.preview_sepa("co-1", "2026-09")["can_generate"]


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
