"""Tests unitaires — baremes_loader."""

from __future__ import annotations

from app.modules.payroll.engine.baremes_loader import (
    assembler_baremes,
    baremes_lookup,
    comparer_taux_vm_entreprise,
    controler_integrite_baremes,
    resoudre_taux_vm_officiel,
    resoudre_taux_vm_pour_paie,
)
from app.modules.payroll.application.simulation_queries import load_baremes
from tests.unit.payroll.fixtures.baremes_snapshot import baremes_snapshot


def test_assembler_baremes_inclut_ij_km_vm():
    db = {
        "smic": {"cas_general": 12.31},
        "pss": {"mensuel": 4005.0},
        "ij_plafonds": {"maladie": 51.0},
        "baremes_km": {"annee": 2026},
        "taux_vmrr": [{"commune": "Paris", "taux": 0.025}],
        "pas": {"baremes": []},
        "primes": {"primes": []},
    }
    out = assembler_baremes(db, {"idcc_1486": {}})
    assert out["ij_plafonds"]["maladie"] == 51.0
    assert out["baremes_km"]["annee"] == 2026
    assert out["conventions_collectives"]["idcc_1486"] == {}


def test_baremes_lookup_absent_retourne_none_et_alerte():
    alertes = []
    val = baremes_lookup({}, "smic", "cas_general", alertes=alertes)
    assert val is None
    assert len(alertes) == 1
    assert alertes[0]["code"] == "bareme_cle_absente"


def test_baremes_lookup_present():
    baremes = baremes_snapshot()
    alertes = []
    val = baremes_lookup(baremes, "smic", "cas_general", alertes=alertes)
    assert val == 12.31
    assert alertes == []


def test_baremes_lookup_liste_heures_supp():
    baremes = baremes_snapshot()
    alertes = []
    val = baremes_lookup(
        baremes,
        "heures_supp",
        "regles_calcul_communes",
        "taux_majoration_par_defaut",
        "heures_supplementaires",
        0,
        "taux",
        alertes=alertes,
    )
    assert val == 0.25
    assert alertes == []


def test_controler_integrite_ok():
    alertes = controler_integrite_baremes(baremes_snapshot())
    assert isinstance(alertes, list)


def test_resoudre_taux_vm_officiel_depuis_bareme():
    baremes = baremes_snapshot()
    taux = resoudre_taux_vm_officiel(baremes["taux_vmrr"], "Paris")
    assert taux == 0.025


def test_resoudre_taux_vm_absent_sans_defaut():
    alertes = []
    assert resoudre_taux_vm_officiel([], "Paris", alertes=alertes) is None
    assert alertes[0]["code"] == "vm_bareme_absent"


def test_resoudre_taux_vm_pour_paie_repli_entreprise():
    entreprise = {
        "identification": {"adresse": {"ville": "Magnieu"}},
        "parametres_paie": {
            "taux_specifiques": {"taux_versement_mobilite": 0.0},
        },
    }
    alertes = []
    taux = resoudre_taux_vm_pour_paie({}, entreprise, alertes=alertes)
    assert taux == 0.0
    assert alertes == []


def test_resoudre_taux_vm_pour_paie_alerte_si_aucune_source():
    entreprise = {
        "identification": {"adresse": {"ville": "Magnieu"}},
        "parametres_paie": {"taux_specifiques": {}},
    }
    alertes = []
    assert resoudre_taux_vm_pour_paie({}, entreprise, alertes=alertes) is None
    assert alertes[0]["code"] == "vm_bareme_absent"


def test_comparer_taux_vm_ignore_surcharge_nulle():
    assert comparer_taux_vm_entreprise(0.0, [{"commune": "Paris", "taux": 0.025}]) is None
    assert comparer_taux_vm_entreprise(None, [{"commune": "Paris", "taux": 0.025}]) is None


def test_comparer_taux_vm_ecart():
    alerte = comparer_taux_vm_entreprise(
        0.03, [{"commune": "Paris", "taux": 0.025}], commune="Paris"
    )
    assert alerte is not None
    assert alerte["code"] == "vm_ecart_taux"


def test_load_baremes_utilise_assembler(monkeypatch):
    from app.modules.payroll.infrastructure import simulation_repository

    snap = baremes_snapshot()
    db_rows = [
        {"config_key": "smic", "config_data": snap["smic"]},
        {"config_key": "pss", "config_data": snap["pss"]},
        {"config_key": "cotisations", "config_data": snap["cotisations"]},
        {"config_key": "pas", "config_data": {"baremes": snap["pas"]}},
        {"config_key": "primes", "config_data": {"primes": snap["primes"]}},
        {"config_key": "ij_plafonds", "config_data": snap["ij_plafonds"]},
    ]

    monkeypatch.setattr(
        simulation_repository,
        "fetch_active_payroll_config_rows",
        lambda: db_rows,
    )
    monkeypatch.setattr(
        simulation_repository,
        "fetch_convention_collective_rules",
        lambda: {"idcc_1486": {}},
    )
    loaded = load_baremes()
    assert loaded["ij_plafonds"]["maladie"] == 51.0
    assert "idcc_1486" in loaded["conventions_collectives"]
