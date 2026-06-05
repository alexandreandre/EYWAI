"""Tests unitaires — socle commun solde de tout compte."""

from __future__ import annotations

from reportlab.lib.styles import getSampleStyleSheet

from app.modules.payroll.solde_de_tout_compte.common import socle_commun
from app.shared.infrastructure.pdf.helpers import setup_custom_styles


class _FakeQuery:
    def __init__(self, data):
        self._data = data

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def maybe_single(self):
        return self

    def execute(self):
        return type("R", (), {"data": self._data})()


class _FakeClient:
    def __init__(self, payslip_row):
        self._row = payslip_row

    def table(self, _name):
        return _FakeQuery(self._row)


def test_build_remunerations_section_uses_neant_without_payslip() -> None:
    styles = setup_custom_styles(getSampleStyleSheet())
    story = []
    total_brut, _, _ = socle_commun.build_remunerations_section(
        story,
        styles,
        {"salaire_de_base": {"valeur": 0}},
        {"last_working_day": "2025-06-15"},
        employee_id="emp-1",
        supabase_client=_FakeClient(None),
    )
    assert total_brut == 0.0
    assert story


def test_build_remunerations_section_reads_last_payslip() -> None:
    styles = setup_custom_styles(getSampleStyleSheet())
    story = []
    payslip = {
        "year": 2025,
        "month": 6,
        "payslip_data": {
            "remuneration_brute_heures_supp": 320.0,
            "total_heures_supp": 8.0,
            "total_primes": 150.0,
        },
    }
    total_brut, _, _ = socle_commun.build_remunerations_section(
        story,
        styles,
        {"salaire_de_base": {"valeur": 2500}, "id": "emp-1"},
        {"last_working_day": "2025-06-30"},
        employee_id="emp-1",
        supabase_client=_FakeClient(payslip),
    )
    assert total_brut > 2500
