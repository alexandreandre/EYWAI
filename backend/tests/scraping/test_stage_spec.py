from _spec_loader import load_spec

SPEC = load_spec("stage")


def test_spec_identity():
    assert SPEC.config_key == "stage"
    assert SPEC.source_key == "STAGE"
    assert SPEC.tier == "critical"


def test_signature_and_validation():
    sig = SPEC.extract_signature({"valeurs": {"pct_plafond_horaire_ss": 0.15}})
    assert sig == {"pct_plafond_horaire_ss": 0.15}
    assert SPEC.validate_signature({"pct_plafond_horaire_ss": 0.15}).ok
    assert not SPEC.validate_signature({"pct_plafond_horaire_ss": 0.90}).ok  # aberrant


def test_build_creates_flat_config():
    out = SPEC.build_config_data({"pct_plafond_horaire_ss": 0.15}, None)
    assert out == {"pct_plafond_horaire_ss": 0.15}
