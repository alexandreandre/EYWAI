from _spec_loader import load_spec

SPEC = load_spec("cdd")


def test_spec_identity():
    assert SPEC.config_key == "cdd"
    assert SPEC.source_key == "CDD"
    assert SPEC.tier == "critical"


def test_signature_and_validation():
    sig = SPEC.extract_signature(
        {"valeurs": {"precarite_taux": 0.10, "indemnite_conges_taux": 0.10}}
    )
    assert sig == {"precarite_taux": 0.10, "indemnite_conges_taux": 0.10}
    assert SPEC.validate_signature(
        {"precarite_taux": 0.10, "indemnite_conges_taux": 0.10}
    ).ok
    assert not SPEC.validate_signature(
        {"precarite_taux": 0.90, "indemnite_conges_taux": 0.10}
    ).ok  # 90 % = aberrant


def test_build_merges_preserving_existing_keys():
    current = {
        "config_data": {
            "precarite": {"taux": 0.06, "actif": True},
            "indemnite_conges": {"taux": 0.10},
        }
    }
    sig = {"precarite_taux": 0.10, "indemnite_conges_taux": 0.10}
    out = SPEC.build_config_data(sig, current)
    assert out["precarite"]["taux"] == 0.10
    assert out["precarite"]["actif"] is True
