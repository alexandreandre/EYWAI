"""Rémunération des périodes de congés au départ : les cumuls du mois précédent
alignés sur la période des compteurs (L3141-24 I : rémunération perçue au
cours de la période de référence).

Départ en juin, premier mois de la période 2026-2027 : le run lit les cumuls de
mai, dont `brut_reference_n_1` est le total de la période 2025-2026, close. Il
était ajouté à la période en cours (36 000 € de base pour 1,04 jour), et la
période précédente remontait à 2024-2025.
"""

from __future__ import annotations

import pytest

from app.core import database
from app.modules.payroll.documents.payslip_run_heures import remuneration_des_periodes

pytestmark = pytest.mark.unit


class _Requete:
    def __init__(self, lignes):
        self._lignes = lignes

    def __getattr__(self, _nom):
        return lambda *a, **k: self

    def execute(self):
        return type("R", (), {"data": self._lignes})()


class _Base:
    """Le cumul de mai 2026 (fin de la période 2025-2026) dans employee_schedules."""

    def __init__(self, cumul_de_fin_de_periode):
        self._cumul = cumul_de_fin_de_periode

    def table(self, nom):
        return _Requete([] if nom == "payslips" else self._cumul)


CUMULS_DE_MAI = {
    "cumuls": {
        "brut_reference_n_1": 36000.0,
        "brut_reference_period_start": "2025-06-01",
        "brut_reference_period_end": "2026-05-31",
    }
}
CUMUL_DE_MAI_EN_BASE = [{"cumuls": CUMULS_DE_MAI}]

COMPTEURS_DE_JUIN = {
    "conges_payes": {"pris": 0, "solde": 1.04, "periode": "01/06/2026 – 31/05/2027"},
    "conges_payes_periode_precedente": {"pris": 0, "solde": 25, "periode": "01/06/2025 – 31/05/2026"},
}


def test_un_depart_en_juin_part_de_zero_et_la_periode_close_prend_le_cumul_de_mai(monkeypatch):
    monkeypatch.setattr(database, "supabase", _Base(CUMUL_DE_MAI_EN_BASE))

    precedente, avant_le_mois = remuneration_des_periodes("emp-1", CUMULS_DE_MAI, COMPTEURS_DE_JUIN)

    assert avant_le_mois == 0.0
    assert precedente == 36000.0


def test_un_depart_en_octobre_garde_la_lecture_d_avant(monkeypatch):
    cumuls_de_septembre = {
        "cumuls": {
            "brut_reference_n_1": 12000.0,
            "brut_reference_period_start": "2026-06-01",
            "brut_reference_period_end": "2027-05-31",
        }
    }
    compteurs = {"conges_payes": {"pris": 0, "solde": 8.33, "periode": "01/06/2026 – 31/05/2027"}}
    monkeypatch.setattr(database, "supabase", _Base(CUMUL_DE_MAI_EN_BASE))

    precedente, avant_le_mois = remuneration_des_periodes("emp-1", cumuls_de_septembre, compteurs)

    assert avant_le_mois == 12000.0
    assert precedente == 36000.0


def test_des_cumuls_sans_periode_ne_disent_rien_de_la_periode_en_cours(monkeypatch):
    monkeypatch.setattr(database, "supabase", _Base([]))

    assert remuneration_des_periodes("emp-1", None, COMPTEURS_DE_JUIN) == (None, None)


def test_sans_cumuls_la_periode_precedente_se_lit_quand_meme_a_sa_fin(monkeypatch):
    """Mois repris sans cumul : la période précédente se lit sur le cumul de fin
    de période (ou ses bulletins), sinon les jours N-1 ne se comparent qu'au
    maintien (L3141-24 : le plus favorable)."""
    monkeypatch.setattr(database, "supabase", _Base(CUMUL_DE_MAI_EN_BASE))
    compteurs = {"conges_payes": {"pris": 0, "solde": 8.33, "periode": "01/06/2026 – 31/05/2027"}}

    assert remuneration_des_periodes("emp-1", None, compteurs) == (36000.0, None)
