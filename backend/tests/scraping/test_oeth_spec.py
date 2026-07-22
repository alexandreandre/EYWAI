from _spec_loader import load_spec

SPEC = load_spec("oeth")


def test_spec_identity():
    assert SPEC.config_key == "oeth"
    assert SPEC.source_key == "OETH"
    assert SPEC.tier == "critical"


def test_signature_and_validation():
    sig = SPEC.extract_signature({"valeurs": {"taux_obligation": 0.06}})
    assert sig == {"taux_obligation": 0.06}
    assert SPEC.validate_signature({"taux_obligation": 0.06}).ok
    assert not SPEC.validate_signature({"taux_obligation": 0.50}).ok  # aberrant


def test_build_merges_preserving_existing_keys():
    current = {
        "config_data": {
            "coefficients": {
                "moins_de_20_salaries": 400,
                "de_20_a_199_salaries": 500,
                "200_salaries_et_plus": 600,
            },
            "taux_obligation": 0.05,
        }
    }
    sig = {"taux_obligation": 0.06}
    out = SPEC.build_config_data(sig, current)
    assert out["taux_obligation"] == 0.06
    assert out["coefficients"] == {
        "moins_de_20_salaries": 400,
        "de_20_a_199_salaries": 500,
        "200_salaries_et_plus": 600,
    }
