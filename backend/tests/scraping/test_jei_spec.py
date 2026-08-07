from _spec_loader import load_spec

SPEC = load_spec("jei")


def test_spec_identity():
    assert SPEC.config_key == "jei"
    assert SPEC.source_key == "JEI"
    assert SPEC.tier == "critical"


def test_signature_and_validation():
    sig = SPEC.extract_signature({"valeurs": {"facteur_smic_plafond": 4.5}})
    assert sig == {"facteur_smic_plafond": 4.5}
    assert SPEC.validate_signature({"facteur_smic_plafond": 4.5}).ok
    assert not SPEC.validate_signature({"facteur_smic_plafond": 20.0}).ok  # aberrant


def test_build_merges_preserving_existing_keys():
    current = {
        "config_data": {
            "actif": True,
            "cotisations_exonerees_patronales": [
                "maladie",
                "vieillesse",
                "allocations_familiales",
            ],
            "facteur_smic_plafond": 4.0,
        }
    }
    sig = {"facteur_smic_plafond": 4.5}
    out = SPEC.build_config_data(sig, current)
    assert out["facteur_smic_plafond"] == 4.5
    assert out["actif"] is True
    assert out["cotisations_exonerees_patronales"] == [
        "maladie",
        "vieillesse",
        "allocations_familiales",
    ]
