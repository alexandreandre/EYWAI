from _spec_loader import load_spec

SPEC = load_spec("interim")


def test_spec_identity():
    assert SPEC.config_key == "interim"
    assert SPEC.source_key == "INTERIM"
    assert SPEC.tier == "critical"


def test_signature_and_validation():
    sig = SPEC.extract_signature(
        {"valeurs": {"ifm_taux": 0.10, "indemnite_conges_taux": 0.10}}
    )
    assert sig == {"ifm_taux": 0.10, "indemnite_conges_taux": 0.10}
    assert SPEC.validate_signature(
        {"ifm_taux": 0.10, "indemnite_conges_taux": 0.10}
    ).ok
    assert not SPEC.validate_signature(
        {"ifm_taux": 0.90, "indemnite_conges_taux": 0.10}
    ).ok  # 90 % = aberrant


def test_build_merges_preserving_existing_keys():
    current = {
        "config_data": {
            "ifm": {"taux": 0.06, "actif": True},
            "indemnite_conges": {"taux": 0.10},
        }
    }
    sig = {"ifm_taux": 0.10, "indemnite_conges_taux": 0.10}
    out = SPEC.build_config_data(sig, current)
    assert out["ifm"]["taux"] == 0.10
    assert out["ifm"]["actif"] is True
