"""Tests unitaires — baremes_loader."""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.baremes_loader import (
    _libelle_commune_vmrr,
    _normaliser_taux_vm_decimal,
    assembler_baremes,
    baremes_lookup,
    comparer_taux_vm_entreprise,
    controler_integrite_baremes,
    ensure_config_data,
    ensure_dict,
    resoudre_taux_vm_officiel,
    resoudre_taux_vm_pour_paie,
)
from app.modules.payroll.application.simulation_queries import load_baremes
from tests.unit.payroll.fixtures.baremes_snapshot import baremes_snapshot


def test_ensure_config_data_preserve_liste_taux_vmrr():
    """taux_vmrr est stocké comme liste de communes — ne pas la réduire à {}."""
    rows = [
        {"commune": "CHAMBERY", "taux": 0.02},
        {"commune": "CERIZAY", "taux": 0.0025},
    ]
    assert ensure_config_data(rows) is rows
    assert ensure_config_data({"rows": rows}) == {"rows": rows}
    assert ensure_config_data(None) == {}
    assert ensure_dict(rows) == {}  # historique : ne garde que les dicts


def test_load_baremes_preserve_taux_vmrr_liste(monkeypatch):
    from app.modules.payroll.infrastructure import simulation_repository

    vm_rows = [{"commune": "CHAMBERY", "taux": 0.02, "nom_commune": "CHAMBERY"}]
    snap = baremes_snapshot()
    db_rows = [
        {"config_key": "smic", "config_data": snap["smic"]},
        {"config_key": "pss", "config_data": snap["pss"]},
        {"config_key": "cotisations", "config_data": snap["cotisations"]},
        {"config_key": "pas", "config_data": {"baremes": snap["pas"]}},
        {"config_key": "primes", "config_data": {"primes": snap["primes"]}},
        {"config_key": "ij_plafonds", "config_data": snap["ij_plafonds"]},
        {"config_key": "taux_vmrr", "config_data": vm_rows},
    ]
    monkeypatch.setattr(
        simulation_repository,
        "fetch_active_payroll_config_rows",
        lambda: db_rows,
    )
    monkeypatch.setattr(
        simulation_repository,
        "fetch_convention_collective_rules",
        lambda: {},
    )
    loaded = load_baremes()
    assert isinstance(loaded["taux_vmrr"], list)
    assert len(loaded["taux_vmrr"]) == 1

    entreprise = {
        "identification": {"adresse": {"ville": "CHAMBERY"}},
        "parametres_paie": {"taux_specifiques": {}},
    }
    alertes: list = []
    assert resoudre_taux_vm_pour_paie(loaded, entreprise, alertes=alertes) == 0.02
    assert alertes == []


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


def test_resoudre_taux_vm_ne_matche_pas_sous_commune_courte():
    """Régression : 'EU' ne doit pas matcher 'MAGNIEU', 'RI' ne doit pas matcher 'CERIZAY'."""
    rows = [
        {"commune": "EU", "taux": 0.003},
        {"commune": "RI", "taux": 0.0045},
        {"commune": "CERIZAY", "taux": 0.0025},
        {"commune": "CHAMBERY", "taux": 0.02},
        {"commune": "MAGNIEU", "taux": 0.0},
    ]
    assert resoudre_taux_vm_officiel(rows, "MAGNIEU") == 0.0
    assert resoudre_taux_vm_officiel(rows, "CERIZAY") == 0.0025
    assert resoudre_taux_vm_officiel(rows, "CHAMBERY") == 0.02
    # Contenance ville → libellé plus long (OK) : « Aix » dans « Aix en Provence »
    rows_aix = [{"commune": "AIX EN PROVENCE", "taux": 0.0208}]
    assert resoudre_taux_vm_officiel(rows_aix, "Aix en Provence") == 0.0208


def test_resoudre_taux_vm_officiel_schema_fichierdirect():
    """Régression : barème scrapé fichierdirect URSSAF (schéma XLSX brut).

    Colonnes réelles : « Communes concernées », « Taux\\nVMRR », « Code commune
    INSEE ». La clé « Code commune INSEE » contient le mot « commune » : le
    résolveur ne doit PAS la prendre pour le libellé, sinon aucune commune ne
    matche jamais (cas CERIZAY → « Taux VM introuvable »).
    """
    rows = [
        {
            "Taux\nVMRR": 0.0015,
            "code partenaire": 9333301,
            "Code commune INSEE": 79062,
            "Communes concernées": "CERIZAY",
            "Date de fin d’effet": None,
            "Date de début d’effet": "2026-01-01",
        },
        {
            "Taux\nVMRR": "0,15%",
            "code partenaire": 9332501,
            "Code commune INSEE": 25001,
            "Communes concernées": "ABBANS-DESSOUS",
            "Date de fin d’effet": None,
            "Date de début d’effet": "2026-01-01",
        },
    ]
    alertes: list = []
    assert resoudre_taux_vm_officiel(rows, "CERIZAY", alertes=alertes) == 0.0015
    assert alertes == []
    # Taux en chaîne « 0,15% » → 0.0015 (et non 0.15).
    assert resoudre_taux_vm_officiel(rows, "ABBANS-DESSOUS") == 0.0015


def test_libelle_commune_vmrr_ne_renvoie_pas_le_code_insee():
    """« Code commune INSEE » ne doit jamais être pris pour le nom de commune."""
    row = {"Code commune INSEE": 79062, "Communes concernées": "CERIZAY"}
    assert _libelle_commune_vmrr(row) == "CERIZAY"


def test_normaliser_taux_vm_decimal_pourcentage_chaine():
    """« 0,15% » = 0,15 % = 0.0015 (le signe % pilote la division par 100)."""
    assert _normaliser_taux_vm_decimal("0,15%") == 0.0015
    assert _normaliser_taux_vm_decimal("1,5%") == 0.015
    assert _normaliser_taux_vm_decimal(0.0015) == 0.0015
    assert _normaliser_taux_vm_decimal(1.5) == 0.015  # pourcentage numérique


def test_resoudre_taux_vm_officiel_insensible_aux_accents():
    """Ville « Cérizay » (accentuée) matche le barème « CERIZAY »."""
    rows = [{"commune": "CERIZAY", "taux": 0.0015}]
    assert resoudre_taux_vm_officiel(rows, "Cérizay") == 0.0015


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


# --- Cumul VM + VMA + VMRR (schéma Open Data URSSAF) -----------------------


def _ligne_open_data(**kwargs):
    """Ligne brute du dataset URSSAF Table_Taux_VM_VMA_VMRR (taux en %)."""
    base = {
        "code_commune": "79062",
        "nom_commune": "CERIZAY",
        "date_debut": "20260101",
        "date_fin": None,
        "taux_vm": 0.1,
        "taux_vma": None,
        "taux_vmr": 0.15,
    }
    base.update(kwargs)
    return base


def test_taux_vm_cumule_aom_additionnel_et_regional():
    """Cerizay : 0,10 % (agglomération) + 0,15 % (région) = 0,25 %."""
    taux = resoudre_taux_vm_officiel([_ligne_open_data()], "CERIZAY")
    assert taux == pytest.approx(0.0025)


def test_taux_vm_regional_seul_ne_masque_pas_le_taux_agglomeration():
    """Le fichier VMRR seul donnait 0,15 % là où 0,25 % est dû."""
    lignes = [_ligne_open_data(taux_vm=2.0, taux_vmr=0.08, nom_commune="AIX EN PROVENCE")]
    assert resoudre_taux_vm_officiel(lignes, "Aix en Provence") == pytest.approx(0.0208)


def test_ligne_periodee_close_est_ignoree():
    """La ligne close au 31/12/2025 ne doit pas primer sur celle en vigueur."""
    lignes = [
        _ligne_open_data(date_debut="20240701", date_fin="20251231", taux_vmr=None),
        _ligne_open_data(),
    ]
    assert resoudre_taux_vm_officiel(lignes, "CERIZAY") == pytest.approx(0.0025)


def test_schema_normalise_par_le_scraper_reste_lu_tel_quel():
    """Le scraper pousse un total déjà en décimal : ne pas le rediviser par 100."""
    lignes = [
        {
            "code_commune": "79062",
            "nom_commune": "CERIZAY",
            "commune": "CERIZAY",
            "taux_vm": 0.0025,
            "taux": 0.0025,
        }
    ]
    assert resoudre_taux_vm_officiel(lignes, "CERIZAY") == pytest.approx(0.0025)


def test_ville_ne_matche_pas_une_commune_qui_la_prefixe():
    """« Paris » ne doit pas prendre le taux de « PARISOT » (Tarn)."""
    rows = [
        {"commune": "PARISOT", "taux": 0.0075},
        {"commune": "PARIS 03", "taux": 0.032, "date_debut": "20240201", "date_fin": None},
    ]
    assert resoudre_taux_vm_officiel(rows, "Paris") == pytest.approx(0.032)


def test_ville_sans_correspondance_reste_none():
    rows = [{"commune": "PARISOT", "taux": 0.0075}]
    assert resoudre_taux_vm_officiel(rows, "Paris") is None


def test_arrondissements_priment_sur_la_ligne_de_commune_entiere():
    """Marseille 13055 ne porte que le VMR (0,08 %) ; les arrondissements le VM complet."""
    rows = [
        {"commune": "MARSEILLE", "taux": 0.0008, "date_debut": "20260101"},
        {"commune": "MARSEILLE 01", "taux": 0.0208, "date_debut": "20260101"},
        {"commune": "MARSEILLE 02", "taux": 0.0208, "date_debut": "20260101"},
        {"commune": "MARSEILLE EN BEAUVAISIS", "taux": 0.0015},
    ]
    assert resoudre_taux_vm_officiel(rows, "Marseille") == pytest.approx(0.0208)


def test_arrondissements_de_taux_divergents_ne_sont_pas_devines():
    rows = [
        {"commune": "VILLETEST 01", "taux": 0.01},
        {"commune": "VILLETEST 02", "taux": 0.02},
    ]
    alertes: list = []
    assert resoudre_taux_vm_officiel(rows, "VILLETEST", alertes=alertes) is None
    assert alertes[0]["code"] == "vm_taux_ambigu"
