"""Plafond transport : une fonction, les deux générateurs (audit du 17/11).

Le contrôle ne vivait que dans le générateur des heures ; le test de parité
vérifie que les deux l'appellent, celui-ci ce qu'il dit.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.documents.plafond_transport import alertes_plafond_transport
from app.modules.payroll.engine import baremes_loader

pytestmark = pytest.mark.unit

FRAIS_PRO = {
    "FRAIS_PRO": [
        {"sections": {"mobilite_durable": {"employeurs_prives": {"limite_base": 600.0}}}}
    ]
}


class _Requete:
    def __init__(self, lignes):
        self._lignes = lignes

    def select(self, *_a):
        return self

    def eq(self, *_a):
        return self

    def execute(self):
        return type("R", (), {"data": self._lignes})()


class _Base:
    def __init__(self, lignes):
        self._lignes = lignes

    def table(self, _nom):
        return _Requete(self._lignes)


@pytest.fixture(autouse=True)
def _baremes(monkeypatch):
    monkeypatch.setattr(baremes_loader, "charger_db_baremes", lambda _c: {})
    monkeypatch.setattr(baremes_loader, "assembler_baremes", lambda _b: {"frais_pro": FRAIS_PRO})


def _transport(mois, montant):
    return {"name": "Forfait transport", "amount": montant, "month": mois}


def test_le_mois_du_franchissement_porte_l_alerte():
    base = _Base([_transport(m, 100.0) for m in range(1, 8)])
    assert len(alertes_plafond_transport(base, "e1", {}, 2026, 7)) == 1


def test_un_mois_saisi_d_avance_ne_compte_pas():
    base = _Base([_transport(m, 100.0) for m in range(1, 7)] + [_transport(8, 500.0)])
    assert alertes_plafond_transport(base, "e1", {}, 2026, 6) == []


def test_une_lecture_ratee_ne_fait_pas_tomber_le_bulletin():
    class _Panne:
        def table(self, _nom):
            raise RuntimeError("base indisponible")

    assert alertes_plafond_transport(_Panne(), "e1", {}, 2026, 7) == []
