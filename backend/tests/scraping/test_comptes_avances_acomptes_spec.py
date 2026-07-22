from _spec_loader import load_spec

SPEC = load_spec("comptes_avances_acomptes")


def test_spec_identity():
    assert SPEC.config_key == "comptes_avances_acomptes"
    assert SPEC.source_key == "COMPTES_AVANCES_ACOMPTES"
    assert SPEC.tier == "critical"


def test_signature_and_validation():
    sig = SPEC.extract_signature(
        {"valeurs": {"avance": "425", "acompte": None, "banque": "512"}}
    )
    assert sig == {"avance": "425", "acompte": None, "banque": "512"}
    assert SPEC.validate_signature({"avance": "425", "banque": "512"}).ok
    assert not SPEC.validate_signature({"avance": "abc"}).ok


def test_build_merges_preserving_existing_keys():
    current = {"config_data": {"acompte": "425"}}
    sig = {"avance": "425", "banque": "512"}
    out = SPEC.build_config_data(sig, current)
    assert out["avance"] == "425"
    assert out["acompte"] == "425"
    assert out["banque"] == "512"


def test_build_raises_without_current():
    import pytest

    with pytest.raises(ValueError):
        SPEC.build_config_data({"avance": "425"}, None)
