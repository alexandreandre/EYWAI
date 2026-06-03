"""Tests offline — cohérence CEG AGIRC-ARRCO IA."""

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRAPING = Path(__file__).resolve().parents[3] / "scraping"
_AI_PATH = _SCRAPING / "AGIRC-ARRCO" / "AGIRC-ARRCO_AI.py"
_LOGIC_PATH = _SCRAPING / "AGIRC-ARRCO" / "_logic.py"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_ai_module():
    return _load_module(_AI_PATH, "agirc_arrco_ai")


@pytest.fixture(scope="module")
def agirc_ai():
    return _load_ai_module()


def test_ceg_coherent_official_rates(agirc_ai):
    bundle = {
        "ceg_t1_salarial": 0.0086,
        "ceg_t1_patronal": 0.0129,
        "ceg_t2_salarial": 0.0108,
        "ceg_t2_patronal": 0.0162,
    }
    assert agirc_ai._ceg_rates_coherent(bundle) is True


def test_bundles_pair_equal_subset_only():
    mod = _load_module(_LOGIC_PATH, "agirc_arrco_logic_subset")
    a = {
        "cet": {"id": "cet", "type": "cotisation", "libelle": "CET", "base": "assiette_cet", "valeurs": {"salarial": 0.0014, "patronal": 0.0021}},
        "ceg_t2": {"id": "ceg_t2", "type": "cotisation", "libelle": "CEG T2", "base": "tranche_2", "valeurs": {"salarial": 0.0108, "patronal": 0.0162}},
    }
    b = {
        "cet": {"id": "cet", "type": "cotisation", "libelle": "CET", "base": "assiette_cet", "valeurs": {"salarial": 0.0014, "patronal": 0.0021}},
        "ceg_t2": {"id": "ceg_t2", "type": "cotisation", "libelle": "CEG T2", "base": "tranche_2", "valeurs": {"salarial": 0.0129, "patronal": 0.0194}},
    }
    assert mod.bundles_pair_equal(a, b, item_ids=["cet"]) is True
    assert mod.bundles_pair_equal(a, b, item_ids=["ceg_t2"]) is False


def test_bundles_pair_equal_single_key_dict():
    """make_bundle_item_equal passe {ceg_t1: item} — ne doit pas exiger les 6 lignes."""
    mod = _load_module(_LOGIC_PATH, "agirc_arrco_logic_single")
    item_a = {
        "id": "ceg_t1",
        "type": "cotisation",
        "libelle": "Contribution d'Équilibre Général (CEG) T1",
        "base": "brut_plafonne",
        "valeurs": {"salarial": 0.0086, "patronal": 0.0129},
    }
    item_b = {**item_a}
    assert mod.bundles_pair_equal({"ceg_t1": item_a}, {"ceg_t1": item_b}) is True


def test_ceg_rejects_t1_patronal_as_t2_salarial(agirc_ai):
    """Erreur observée en prod : 1,29 % patronal T1 mis en T2 salarial."""
    bundle = {
        "ceg_t1_salarial": 0.0086,
        "ceg_t1_patronal": 0.0129,
        "ceg_t2_salarial": 0.0129,
        "ceg_t2_patronal": 0.0194,
    }
    assert agirc_ai._ceg_rates_coherent(bundle) is False
