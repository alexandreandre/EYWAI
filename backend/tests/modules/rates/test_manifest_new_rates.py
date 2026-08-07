from app.modules.rates.domain.rate_source_mapping import (
    RATE_KEY_TO_SOURCE_KEYS,
    all_page_source_keys,
)

NEW = {
    "taux_interet_legal": "TAUX_INTERET_LEGAL",
    "cdd": "CDD",
    "interim": "INTERIM",
    "stage": "STAGE",
    "maladie": "MALADIE",
    "jei": "JEI",
    "oeth": "OETH",
    "reduction_generale": "REDUCTION_GENERALE",
    "mandataire": "MANDATAIRE",
    "comptes_avances_acomptes": "COMPTES_AVANCES_ACOMPTES",
}


def test_all_new_rate_keys_mapped():
    for rate_key, source_key in NEW.items():
        assert RATE_KEY_TO_SOURCE_KEYS.get(rate_key) == [source_key]


def test_new_sources_in_full_page_update():
    page = set(all_page_source_keys())
    for source_key in NEW.values():
        assert source_key in page


def test_existing_mappings_untouched():
    # garde-fou anti-régression : les clés historiques restent inchangées
    assert RATE_KEY_TO_SOURCE_KEYS["smic"] == ["SMIC"]
    assert RATE_KEY_TO_SOURCE_KEYS["pss"] == ["PSS"]
