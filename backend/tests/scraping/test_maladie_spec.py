from _spec_loader import load_spec

SPEC = load_spec("maladie")


def test_spec_identity():
    assert SPEC.config_key == "maladie"
    assert SPEC.source_key == "MALADIE"
    assert SPEC.tier == "critical"


def test_signature_and_validation():
    sig = SPEC.extract_signature(
        {
            "valeurs": {
                "csg_ijss_taux_deductible": 0.038,
                "csg_ijss_taux_non_deductible": 0.029,
            }
        }
    )
    assert sig == {
        "csg_ijss_taux_deductible": 0.038,
        "csg_ijss_taux_non_deductible": 0.029,
    }
    assert SPEC.validate_signature(
        {
            "csg_ijss_taux_deductible": 0.038,
            "csg_ijss_taux_non_deductible": 0.029,
        }
    ).ok
    assert not SPEC.validate_signature(
        {
            "csg_ijss_taux_deductible": 0.90,
            "csg_ijss_taux_non_deductible": 0.029,
        }
    ).ok  # 90 % = aberrant


def test_build_merges_preserving_existing_keys():
    current = {
        "config_data": {
            "csg_ijss": {"taux_deductible": 0.02, "taux_non_deductible": 0.02},
            "ijss_plafond_journalier": 60.0,  # clé sœur non liée, doit survivre
        }
    }
    sig = {
        "csg_ijss_taux_deductible": 0.038,
        "csg_ijss_taux_non_deductible": 0.029,
    }
    out = SPEC.build_config_data(sig, current)
    assert out["csg_ijss"]["taux_deductible"] == 0.038
    assert out["csg_ijss"]["taux_non_deductible"] == 0.029
    assert out["ijss_plafond_journalier"] == 60.0
