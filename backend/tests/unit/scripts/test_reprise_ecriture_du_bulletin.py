"""Reprise : un bulletin copié de Quadra s'écrit avec la clé des bulletins de l'application (D3).

Depuis D3 la clé unique est (société, salarié, année, mois, contrat) : une écriture qui vise
l'ancienne clé à quatre colonnes est refusée par la base (« no unique or exclusion constraint
matching the ON CONFLICT specification »), comme à la reprise MAJI/Zone 404 du 03/11.
"""

from __future__ import annotations

import pytest

from app.shared.cle_du_bulletin import CONFLIT_BULLETIN
from scripts.reprise_colorplast_import_litteral import ecrire_bulletin_importe

pytestmark = pytest.mark.unit


class _Table:
    def __init__(self, appels: list, nom: str) -> None:
        self.appels, self.nom = appels, nom

    def upsert(self, ligne, on_conflict=None):
        self.appels.append((self.nom, ligne, on_conflict))
        return self

    def execute(self):
        return self


class _Client:
    def __init__(self) -> None:
        self.appels: list = []

    def table(self, nom: str) -> _Table:
        return _Table(self.appels, nom)


def test_le_bulletin_repris_vise_la_cle_des_bulletins_de_l_application():
    client = _Client()
    ecrire_bulletin_importe(client, {"employee_id": "e", "company_id": "c", "year": 2026, "month": 9,
                                     "origine": "importe"})
    [(table, ligne, cle)] = client.appels
    assert table == "payslips"
    assert cle == CONFLIT_BULLETIN


def test_le_bulletin_repris_est_celui_du_contrat_de_la_fiche():
    client = _Client()
    ecrire_bulletin_importe(client, {"employee_id": "e", "company_id": "c", "year": 2026, "month": 9})
    [(_, ligne, _)] = client.appels
    assert "contract_period_id" in ligne and ligne["contract_period_id"] is None
