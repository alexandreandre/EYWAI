"""Le plafond JEI consommé ne s'enregistre pas pendant un calcul en lecture seule.

Le bac à sable (audit, octobre à blanc, contrôles) calcule un bulletin sans rien écrire ; depuis
que le barème JEI arrive au moteur (03/11), l'exonération enregistrait son montant au passage et
le calcul échouait en lecture seule. Hors lecture seule, l'enregistrement part comme avant.
"""

from __future__ import annotations

import pytest

from app.core.lecture_seule import lecture_seule
from app.modules.jei_settings.infrastructure import exonerations_repository as module

pytestmark = pytest.mark.unit


class _Client:
    def __init__(self) -> None:
        self.ecritures: list = []

    def table(self, nom):
        self.nom = nom
        return self

    def upsert(self, ligne, on_conflict=None):
        self.ecritures.append((self.nom, ligne))
        return self

    def execute(self):
        return self


def _enregistrer(client, monkeypatch):
    monkeypatch.setattr(module, "supabase", client)
    module.SupabaseJeiExonerationsRepository().upsert_monthly("c", 2026, 10, "e", 123.45)


def test_rien_n_est_enregistre_en_lecture_seule(monkeypatch):
    client = _Client()
    with lecture_seule():
        _enregistrer(client, monkeypatch)
    assert client.ecritures == []


def test_le_montant_s_enregistre_hors_lecture_seule(monkeypatch):
    client = _Client()
    _enregistrer(client, monkeypatch)
    assert client.ecritures == [("company_jei_exonerations", {
        "company_id": "c", "year": 2026, "month": 10, "employee_id": "e", "montant_exonere": 123.45,
    })]
