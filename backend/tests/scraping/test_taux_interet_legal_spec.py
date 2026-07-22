from _spec_loader import load_spec

SPEC = load_spec("taux_interet_legal")


def test_spec_identity():
    assert SPEC.config_key == "taux_interet_legal"
    assert SPEC.source_key == "TAUX_INTERET_LEGAL"
    assert SPEC.tier == "critical"


def test_signature_and_validation():
    sig = SPEC.extract_signature({"valeurs": {"taux_annuel": 0.0526}})
    assert sig == {"taux_annuel": 0.0526}
    assert SPEC.validate_signature({"taux_annuel": 0.0526}).ok
    assert not SPEC.validate_signature({"taux_annuel": 0.5}).ok  # 50 % = aberrant


def test_build_creates_flat_config():
    out = SPEC.build_config_data({"taux_annuel": 0.0526}, None)
    assert out == {"taux_annuel": 0.0526}
