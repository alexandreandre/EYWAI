from _spec_loader import load_spec

SPEC = load_spec("reduction_generale")


def test_spec_identity():
    assert SPEC.config_key == "reduction_generale"
    assert SPEC.source_key == "REDUCTION_GENERALE"
    assert SPEC.tier == "critical"


def test_signature_and_validation():
    sig = SPEC.extract_signature(
        {
            "valeurs": {
                "tmin": 0.02,
                "p": 1.0,
                "point_sortie_smic": 3.0,
                "tdelta_fnal_moins_50": 0.3781,
                "tdelta_fnal_50_et_plus": 0.3821,
            }
        }
    )
    assert sig == {
        "tmin": 0.02,
        "p": 1.0,
        "point_sortie_smic": 3.0,
        "tdelta_fnal_moins_50": 0.3781,
        "tdelta_fnal_50_et_plus": 0.3821,
    }
    assert SPEC.validate_signature(sig).ok
    aberrant = dict(sig)
    aberrant["p"] = 10.0  # hors bornes (1.0, 3.0)
    assert not SPEC.validate_signature(aberrant).ok


def test_tmax_ne_passe_pas_pour_tdelta():
    """R-265 : la collecte qui rend Tmax (0,3981 / 0,4021) au lieu de Tdelta est refusée."""
    valides = {
        "tmin": 0.02,
        "p": 1.75,
        "point_sortie_smic": 3.0,
        "tdelta_fnal_moins_50": 0.3781,
        "tdelta_fnal_50_et_plus": 0.3821,
    }
    assert SPEC.validate_signature(valides).ok
    assert not SPEC.validate_signature({**valides, "tdelta_fnal_moins_50": 0.3981}).ok
    assert not SPEC.validate_signature({**valides, "tdelta_fnal_50_et_plus": 0.4021}).ok
    assert not SPEC.validate_signature({**valides, "tmin": 0.2331}).ok


def test_build_merges_preserving_existing_keys():
    current = {
        "config_data": {
            "actif": True,
            "tdelta": {
                "fnal_moins_50": 0.3133,
                "fnal_50_et_plus": 0.3173,
                "autre_placeholder": True,
            },
        }
    }
    sig = {
        "tmin": 0.02,
        "p": 1.0,
        "point_sortie_smic": 3.0,
        "tdelta_fnal_moins_50": 0.3781,
        "tdelta_fnal_50_et_plus": 0.3821,
    }
    out = SPEC.build_config_data(sig, current)
    assert out["tdelta"]["fnal_moins_50"] == 0.3781
    assert out["tdelta"]["fnal_50_et_plus"] == 0.3821
    assert out["tdelta"]["autre_placeholder"] is True  # clé sœur imbriquée survit
    assert out["actif"] is True  # clé sœur top-level survit
    assert out["tmin"] == 0.02
    assert out["p"] == 1.0
    assert out["point_sortie_smic"] == 3.0
