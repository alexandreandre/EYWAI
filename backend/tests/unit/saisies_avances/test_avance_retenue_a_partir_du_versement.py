"""Une avance ne se retient que sur un bulletin du mois de son versement ou d'après. [G7]

`get_advances_to_repay` ne lisait pas le mois : une avance versée en octobre
était retenue sur le prochain bulletin généré, fût-il celui de septembre, ou de
janvier lors d'une reprise. Une avance versée en octobre ne peut pas être
retenue sur septembre.

Date de versement : le premier versement enregistré, sinon la date de versement
de l'avance, sinon la date de la demande.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.modules.saisies_avances.infrastructure import queries

pytestmark = pytest.mark.unit


class _Requete:
    def __init__(self, lignes: list[dict[str, Any]]):
        self._lignes = list(lignes)

    def select(self, *_a, **_k):
        return self

    def eq(self, colonne, valeur):
        self._lignes = [l for l in self._lignes if l.get(colonne) == valeur]
        return self

    def in_(self, colonne, valeurs):
        self._lignes = [l for l in self._lignes if l.get(colonne) in valeurs]
        return self

    def gt(self, colonne, valeur):
        self._lignes = [l for l in self._lignes if float(l.get(colonne) or 0) > valeur]
        return self

    def order(self, colonne, desc=False):
        self._lignes.sort(key=lambda l: str(l.get(colonne) or ""), reverse=desc)
        return self

    def limit(self, n):
        self._lignes = self._lignes[:n]
        return self

    def execute(self):
        return type("R", (), {"data": self._lignes})()


class _Base:
    def __init__(self, tables: dict[str, list[dict[str, Any]]]):
        self._tables = tables

    def table(self, nom):
        return _Requete(self._tables.get(nom, []))


def _avance(id_: str, **champs) -> dict[str, Any]:
    return {
        "id": id_,
        "employee_id": "e1",
        "status": "paid",
        "remaining_amount": 300.0,
        "requested_date": "2026-10-01",
        "payment_date": None,
        **champs,
    }


@pytest.fixture
def base(monkeypatch):
    tables = {
        "salary_advances": [
            # Demandée fin septembre, versée le 6 octobre (preuve enregistrée).
            _avance("versee-en-octobre", requested_date="2026-09-28", status="approved"),
            # Sans versement enregistré : la date de versement de l'avance.
            _avance("datee-de-janvier", requested_date="2025-12-20", payment_date="2026-01-01"),
            # Ni l'un ni l'autre : la date de la demande.
            _avance("demandee-en-novembre", requested_date="2026-11-03"),
        ],
        "salary_advance_payments": [
            {"id": "p1", "advance_id": "versee-en-octobre", "payment_date": "2026-10-06"},
        ],
    }
    monkeypatch.setattr(queries, "supabase", _Base(tables))


def _retenues(annee: int, mois: int) -> set[str]:
    return {a["id"] for a in queries.get_advances_to_repay("e1", annee, mois)}


def test_pas_de_retenue_avant_le_mois_du_versement(base):
    assert _retenues(2026, 9) == {"datee-de-janvier"}


def test_retenue_le_mois_du_versement_et_apres(base):
    assert _retenues(2026, 10) == {"datee-de-janvier", "versee-en-octobre"}
    assert _retenues(2026, 11) == {
        "datee-de-janvier",
        "versee-en-octobre",
        "demandee-en-novembre",
    }


def test_une_reprise_de_l_annee_d_avant_ne_retient_rien(base):
    assert _retenues(2025, 12) == set()
