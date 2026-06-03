"""Tests validateurs métier étendus."""

import importlib.util
from datetime import datetime

from core.validation import (
    ValidationResult,
    validate_csg_valeurs,
    validate_ij_plafonds,
    validate_smic_sections,
)

from tests.unit.scraping.helpers import SCRAPING_ROOT


def _load_logic(folder: str, module: str = "_logic"):
    path = SCRAPING_ROOT / folder / f"{module}.py"
    spec = importlib.util.spec_from_file_location(f"{folder}_logic", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_validate_csg_ok():
    r = validate_csg_valeurs(
        {
            "salarial": {"deductible": 0.068, "non_deductible": 0.029},
        }
    )
    assert r.ok


def test_validate_ij_plafonds_ok():
    r = validate_ij_plafonds(
        {
            "maladie": 50.58,
            "maternite_paternite": 89.70,
            "at_mp": 205.40,
            "at_mp_majoree": 274.00,
        }
    )
    assert r.ok


def test_validate_agirc_bundle_complete():
    agirc = _load_logic("AGIRC-ARRCO")
    sig = {
        cid: {
            "id": cid,
            "valeurs": {"salarial": 0.0315, "patronal": 0.0472},
        }
        for cid in agirc.ITEMS_ID_TO_PATCH
    }
    assert agirc.validate_signature(sig).ok


def test_validate_agirc_missing_item():
    agirc = _load_logic("AGIRC-ARRCO")
    sig = {
        "retraite_comp_t1": {
            "id": "retraite_comp_t1",
            "valeurs": {"salarial": 0.03, "patronal": 0.04},
        }
    }
    assert not agirc.validate_signature(sig).ok


def test_validate_fraispro_repas():
    fraispro = _load_logic("fraispro")
    sig = {
        "id": "frais_pro",
        "sections": {
            "repas": {
                "sur_lieu_travail": 4.72,
                "hors_locaux_avec_restaurant": 9.44,
                "hors_locaux_sans_restaurant": 18.88,
            }
        },
    }
    assert fraispro.validate_signature(sig).ok


def test_validate_bareme_year():
    bareme = _load_logic("bareme-indemnite-kilometrique")
    cy = datetime.now().year
    r = bareme.validate_signature({"annee": cy, "vehicules": {"voitures": {}}})
    assert isinstance(r, ValidationResult)
    assert r.ok


def test_validate_smic_young_leq_general():
    assert not validate_smic_sections(
        {
            "annee": 2026,
            "cas_general": 11.0,
            "smic_horaire_brut": 11.0,
            "jeune_17_ans": 12.0,
            "jeune_moins_17_ans": 9.0,
        }
    ).ok
