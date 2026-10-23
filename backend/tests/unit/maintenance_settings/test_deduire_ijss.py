"""Le réglage « sans subrogation : IJSS déduites ou non », de la ligne à l'écran.

Sans ligne de réglages, la règle légale (true). Une ligne existante garde le
calcul d'avant ce réglage : la migration la pose à false, et une ligne lue
avant la migration (sans la colonne) se lit false aussi.
"""

from __future__ import annotations

import pytest

from app.modules.maintenance_settings.application import commands, queries
from app.modules.maintenance_settings.schemas.requests import MaintenanceSettingsUpdate

pytestmark = pytest.mark.unit

SOCIETE = "aaaaaaaa-1111-1111-1111-111111111111"
CLE = "deduire_ijss_sans_subrogation"
LIGNE = {
    "id": "bbbbbbbb-2222-2222-2222-222222222222",
    "company_id": SOCIETE,
    "subrogation_mode": "never",
    "maintain_working_days": True,
}


def _lire(monkeypatch, ligne):
    monkeypatch.setattr(
        queries.maintenance_settings_repository, "get_by_company", lambda _cid: ligne
    )


def test_sans_ligne_la_regle_legale(monkeypatch):
    _lire(monkeypatch, None)
    assert queries.get_maintenance_settings(SOCIETE).deduire_ijss_sans_subrogation is True


def test_une_ligne_lue_avant_la_migration_garde_le_calcul_d_aujourd_hui(monkeypatch):
    _lire(monkeypatch, dict(LIGNE))
    reglages = queries.get_maintenance_settings(SOCIETE)
    assert reglages.deduire_ijss_sans_subrogation is False
    assert reglages.model_dump(mode="json")[CLE] is False


@pytest.mark.parametrize("valeur", [True, False])
def test_la_valeur_de_la_ligne_fait_foi(monkeypatch, valeur):
    _lire(monkeypatch, {**LIGNE, CLE: valeur})
    assert queries.get_maintenance_settings(SOCIETE).deduire_ijss_sans_subrogation is valeur


def _ecrire(monkeypatch, ligne):
    _lire(monkeypatch, ligne)
    ecrit: dict = {}

    def upsert(cid, data):
        ecrit.update(data)
        return {**data, "company_id": cid}

    monkeypatch.setattr(commands.maintenance_settings_repository, "upsert", upsert)
    return ecrit


def test_le_put_enregistre_le_choix(monkeypatch):
    ecrit = _ecrire(monkeypatch, {**LIGNE, CLE: False})
    sauve = commands.save_maintenance_settings(
        SOCIETE, MaintenanceSettingsUpdate(deduire_ijss_sans_subrogation=True)
    )
    assert ecrit[CLE] is True
    assert sauve.deduire_ijss_sans_subrogation is True


def test_un_autre_reglage_enregistre_ne_touche_pas_au_choix(monkeypatch):
    ecrit = _ecrire(monkeypatch, {**LIGNE, CLE: False})
    commands.save_maintenance_settings(SOCIETE, MaintenanceSettingsUpdate(employer_waiting_days=3))
    assert ecrit[CLE] is False


def test_une_premiere_ligne_prend_la_regle_legale(monkeypatch):
    ecrit = _ecrire(monkeypatch, None)
    commands.save_maintenance_settings(SOCIETE, MaintenanceSettingsUpdate(employer_waiting_days=3))
    assert ecrit[CLE] is True
