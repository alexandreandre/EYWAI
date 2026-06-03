"""Tests consensus partiel (sync ciblée cotisation_ids)."""

import importlib.util
from pathlib import Path

from core.partial_consensus import (
    find_divergent_dict_keys,
    make_bundle_item_equal,
    partial_targets_diverge,
    wrap_signatures_equal_for_targets,
)

_AGIRC_LOGIC = (
    Path(__file__).resolve().parents[3] / "scraping" / "AGIRC-ARRCO" / "_logic.py"
)


def _load_agirc_logic():
    spec = importlib.util.spec_from_file_location("agirc_arrco_logic_test", _AGIRC_LOGIC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _bundle_equal(a: dict, b: dict) -> bool:
    if set(a) != set(b):
        return False
    for k in a:
        if a[k] != b[k]:
            return False
    return True


def test_wrap_limits_comparison_to_targets():
    full_a = {"cet": {"id": "cet", "v": 1}, "ceg_t2": {"id": "ceg_t2", "v": 2}}
    full_b = {"cet": {"id": "cet", "v": 1}, "ceg_t2": {"id": "ceg_t2", "v": 99}}
    wrapped = wrap_signatures_equal_for_targets(_bundle_equal, {"cet"})
    assert wrapped(full_a, full_b) is True


def test_partial_single_signature_valeurs():
    """Cotisations simples (dialogue social) : pas de clé dialogue_social dans la sig."""
    a = {"valeurs": {"salarial": None, "patronal": 0.00016}}
    b = {"valeurs": {"salarial": None, "patronal": 0.00016}}
    c = {"valeurs": {"salarial": None, "patronal": 0.0002}}

    def eq(x, y):
        return x == y

    wrapped = wrap_signatures_equal_for_targets(eq, {"dialogue_social"})
    assert wrapped(a, b) is True
    assert wrapped(a, c) is False
    assert partial_targets_diverge(a, c, {"dialogue_social"}, signatures_equal=eq) == [
        "dialogue_social"
    ]
    assert partial_targets_diverge(a, b, {"dialogue_social"}, signatures_equal=eq) == []


def test_partial_single_key_bundle_item_equal():
    """Regression : consensus partiel ceg_t1 via make_bundle_item_equal."""
    mod = _load_agirc_logic()
    item_equal = make_bundle_item_equal(mod.bundles_pair_equal)
    item = {
        "id": "ceg_t1",
        "type": "cotisation",
        "libelle": "Contribution d'Équilibre Général (CEG) T1",
        "base": "brut_plafonne",
        "valeurs": {"salarial": 0.0086, "patronal": 0.0129},
    }
    assert item_equal(item, dict(item)) is True
    assert (
        partial_targets_diverge(
            {"ceg_t1": item},
            {"ceg_t1": dict(item)},
            {"ceg_t1"},
            signatures_equal=mod.bundles_pair_equal,
        )
        == []
    )


def test_find_divergent_keys():
    a = {"cet": {"id": "cet", "v": 1}, "ceg_t2": {"id": "ceg_t2", "v": 2}}
    b = {"cet": {"id": "cet", "v": 1}, "ceg_t2": {"id": "ceg_t2", "v": 9}}
    item_equal = make_bundle_item_equal(_bundle_equal)
    assert find_divergent_dict_keys(a, b, ["cet"], item_equal=item_equal) == []
    assert find_divergent_dict_keys(a, b, ["ceg_t2"], item_equal=item_equal) == ["ceg_t2"]
