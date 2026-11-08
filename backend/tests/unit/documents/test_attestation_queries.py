"""Les bulletins d'une attestation de salaire : validés ET remis, de ce salarié et de cette société."""
from __future__ import annotations

from datetime import date

import pytest

from app.modules.documents.infrastructure import attestation_queries

pytestmark = pytest.mark.unit


class _Requete:
    def __init__(self, lignes, filtres):
        self._lignes = lignes
        self._filtres = filtres

    def select(self, *_):
        return self

    def eq(self, colonne, valeur):
        self._filtres.append((colonne, valeur))
        return self

    def limit(self, *_):
        return self

    def execute(self):
        return type("R", (), {"data": self._lignes})()


class _Base:
    def __init__(self, lignes):
        self.lignes = lignes
        self.filtres: list = []
        self.tables: list = []

    def table(self, nom):
        self.tables.append(nom)
        return _Requete(self.lignes, self.filtres)


def test_seuls_les_bulletins_remis_comptent(monkeypatch):
    base = _Base(
        [
            # Octobre validé le 3/11 : remis le 3/11 (jour de mise à disposition : le 1er).
            {"year": 2026, "month": 10, "status": "valide", "validated_at": "2026-11-03T09:00:00+00:00",
             "payslip_data": {}},
            # Novembre validé en avance : remis le 1er décembre, pas encore.
            {"year": 2026, "month": 11, "status": "valide", "validated_at": "2026-11-04T09:00:00+00:00",
             "payslip_data": {}},
        ]
    )
    monkeypatch.setattr(attestation_queries, "supabase", base)
    monkeypatch.setattr(attestation_queries, "jour_de_la_societe", lambda _: 1)
    monkeypatch.setattr(attestation_queries, "aujourd_hui_local", lambda: date(2026, 11, 5))

    remis = attestation_queries.bulletins_remis_du_salarie("sal-1", "soc-1")

    assert [(b["year"], b["month"]) for b in remis] == [(2026, 10)]
    assert ("employee_id", "sal-1") in base.filtres
    assert ("company_id", "soc-1") in base.filtres
    assert ("status", "valide") in base.filtres


def test_le_dernier_jour_du_dernier_depart(monkeypatch):
    base = _Base(
        [
            {"last_working_day": "2023-06-30", "status": "archivee"},
            {"last_working_day": "2026-10-31", "status": "demission_effective"},
            {"last_working_day": None, "status": "demission_effective"},
            {"last_working_day": "2027-01-31", "status": "annulee"},
        ]
    )
    monkeypatch.setattr(attestation_queries, "supabase", base)
    assert attestation_queries.dernier_jour_de_depart("sal-1", "soc-1") == date(2026, 10, 31)
    assert base.tables == ["employee_exits"]
    assert ("employee_id", "sal-1") in base.filtres
    assert ("company_id", "soc-1") in base.filtres


def test_sans_depart(monkeypatch):
    monkeypatch.setattr(attestation_queries, "supabase", _Base([]))
    assert attestation_queries.dernier_jour_de_depart("sal-1", "soc-1") is None
