from _spec_loader import load_spec

SPEC = load_spec("mandataire")


def test_spec_identity():
    assert SPEC.config_key == "mandataire"
    assert SPEC.source_key == "MANDATAIRE"
    assert SPEC.tier == "critical"


def test_signature_and_validation():
    sig = SPEC.extract_signature(
        {"valeurs": {"cotisations_exclues": ["assurance_chomage", "ags"]}}
    )
    assert sig == {"cotisations_exclues": ["assurance_chomage", "ags"]}
    assert SPEC.validate_signature(
        {"cotisations_exclues": ["assurance_chomage", "ags"]}
    ).ok
    assert not SPEC.validate_signature({"cotisations_exclues": ["inconnue"]}).ok


def test_build_replaces_list_preserving_existing_keys():
    current = {
        "config_data": {
            "cotisations_exclues": ["assurance_chomage"],
            "autre_cle": "conservee",
        }
    }
    sig = {"cotisations_exclues": ["assurance_chomage", "ags", "apec"]}
    out = SPEC.build_config_data(sig, current)
    assert out["cotisations_exclues"] == ["assurance_chomage", "ags", "apec"]
    assert out["autre_cle"] == "conservee"


def test_build_raises_without_current():
    import pytest

    with pytest.raises(ValueError):
        SPEC.build_config_data({"cotisations_exclues": ["ags"]}, None)
