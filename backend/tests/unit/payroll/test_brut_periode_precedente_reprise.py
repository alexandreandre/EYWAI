"""Rémunération de la période de congés précédente : avant la bascule, les bulletins repris font foi.

CDD de Comitech qui finit le 18/12/2026 : sa période 2025-2026 se lisait sur le
cumul de mai 2026 d'`employee_schedules`, écrit le 21/07 par un rejeu de Martine
et jamais réécrit par la reprise du 29/09 (2 072,64 €), alors que le bulletin de
mai repris de Quadra porte 1 966,83 €. Un mois payé par l'ancien logiciel se lit
sur son bulletin importé, pas sur un cumul calculé par Martine.
"""

from __future__ import annotations

import pytest

from app.core import database
from app.modules.payroll.documents.payslip_run_heures import _brut_de_la_periode_precedente

pytestmark = pytest.mark.unit

CUMULS_DE_JUIN = {"cumuls": {"brut_reference_period_start": "2026-06-01"}}


class _Requete:
    def __init__(self, lignes):
        self._lignes = lignes

    def __getattr__(self, _nom):
        return lambda *a, **k: self

    def execute(self):
        return type("R", (), {"data": self._lignes})()


class _Base:
    def __init__(self, cumuls, bulletins):
        self._tables = {"employee_schedules": cumuls, "payslips": bulletins}

    def table(self, nom):
        return _Requete(self._tables[nom])


CUMUL_DE_MAI_PERIME = [
    {"cumuls": {"cumuls": {"brut_reference_n_1": 2072.64, "brut_reference_period_end": "2026-05-31"}}}
]


def test_un_mois_repris_se_lit_sur_le_bulletin_importe(monkeypatch):
    bulletins = [{"year": 2026, "month": 5, "origine": "importe", "payslip_data": {"salaire_brut": 1966.83}}]
    monkeypatch.setattr(database, "supabase", _Base(CUMUL_DE_MAI_PERIME, bulletins))
    assert _brut_de_la_periode_precedente("emp-1", CUMULS_DE_JUIN) == 1966.83


def test_un_mois_calcule_par_martine_garde_son_cumul(monkeypatch):
    bulletins = [{"year": 2026, "month": 5, "origine": "calcule", "payslip_data": {"salaire_brut": 1966.83}}]
    monkeypatch.setattr(database, "supabase", _Base(CUMUL_DE_MAI_PERIME, bulletins))
    assert _brut_de_la_periode_precedente("emp-1", CUMULS_DE_JUIN) == 2072.64
