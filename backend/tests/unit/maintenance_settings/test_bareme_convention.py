"""Le réglage « barème de la convention », de la ligne à l'écran.

Sans ligne, ou sur une ligne lue avant la migration, aucun barème : le calcul
d'avant. Le PUT choisit le barème, puis revient à « Aucun » (null).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.modules.maintenance_settings.api.router import baremes_lisibles
from app.modules.maintenance_settings.application import commands, queries
from app.modules.maintenance_settings.schemas.requests import MaintenanceSettingsUpdate

pytestmark = pytest.mark.unit

MIGRATION = (
    Path(__file__).resolve().parents[4]
    / "supabase" / "migrations" / "20261024120000_bareme_convention_maintien.sql"
)

SOCIETE = "aaaaaaaa-1111-1111-1111-111111111111"
CLE = "bareme_convention"
LIGNE = {
    "id": "bbbbbbbb-2222-2222-2222-222222222222",
    "company_id": SOCIETE,
    "subrogation_mode": "never",
    "maintain_working_days": True,
    "deduire_ijss_sans_subrogation": False,
}


def _lire(monkeypatch, ligne):
    monkeypatch.setattr(
        queries.maintenance_settings_repository, "get_by_company", lambda _cid: ligne
    )


def _ecrire(monkeypatch, ligne):
    _lire(monkeypatch, ligne)
    ecrit: dict = {}

    def upsert(cid, data):
        ecrit.clear()
        ecrit.update(data)
        return {**data, "company_id": cid}

    monkeypatch.setattr(commands.maintenance_settings_repository, "upsert", upsert)
    return ecrit


@pytest.mark.parametrize("ligne", [None, dict(LIGNE), {**LIGNE, CLE: None}])
def test_sans_ligne_avant_la_migration_ou_a_null_aucun_bareme(monkeypatch, ligne):
    _lire(monkeypatch, ligne)
    reglages = queries.get_maintenance_settings(SOCIETE)
    assert reglages.bareme_convention is None
    assert reglages.model_dump(mode="json")[CLE] is None


def test_la_ligne_porte_le_bareme(monkeypatch):
    _lire(monkeypatch, {**LIGNE, CLE: "plasturgie_0292"})
    assert queries.get_maintenance_settings(SOCIETE).bareme_convention == "plasturgie_0292"


def test_le_put_choisit_le_bareme_puis_revient_a_aucun(monkeypatch):
    ecrit = _ecrire(monkeypatch, dict(LIGNE))
    sauve = commands.save_maintenance_settings(
        SOCIETE, MaintenanceSettingsUpdate(bareme_convention="plasturgie_0292")
    )
    assert ecrit[CLE] == "plasturgie_0292"
    assert sauve.bareme_convention == "plasturgie_0292"
    ecrit = _ecrire(monkeypatch, {**LIGNE, CLE: "plasturgie_0292"})
    commands.save_maintenance_settings(SOCIETE, MaintenanceSettingsUpdate(bareme_convention=None))
    assert ecrit[CLE] is None


def test_un_autre_reglage_enregistre_garde_le_bareme(monkeypatch):
    ecrit = _ecrire(monkeypatch, {**LIGNE, CLE: "plasturgie_0292"})
    commands.save_maintenance_settings(SOCIETE, MaintenanceSettingsUpdate(employer_waiting_days=3))
    assert ecrit[CLE] == "plasturgie_0292"


def test_un_bareme_inconnu_est_refuse():
    with pytest.raises(ValidationError):
        MaintenanceSettingsUpdate(bareme_convention="metallurgie")


def test_la_route_rend_le_tableau_du_bareme():
    (plasturgie,) = baremes_lisibles()
    assert plasturgie["code"] == "plasturgie_0292"
    assert plasturgie["libelle"] == "Plasturgie (IDCC 0292)"
    assert plasturgie["categories"][0]["lignes"][1]["paliers"] == (
        "60 jours à 100 %, puis 75 jours à 75 %"
    )


def test_la_migration_ajoute_la_colonne_sans_toucher_aux_lignes():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "add column if not exists bareme_convention text" in sql
    assert "check (bareme_convention is null or bareme_convention in ('plasturgie_0292'))" in sql
    assert "update public" not in sql
