"""Mapping cotisation / source pour le Suivi des taux."""

from app.modules.rates.domain.rate_source_mapping import resolve_source_keys


def test_primes_rate_key_resolves_to_primes_source():
    assert resolve_source_keys(rate_keys=["primes"]) == ["PRIMES"]


def test_heures_supp_rate_key_resolves_to_heures_supp_source():
    assert resolve_source_keys(rate_keys=["heures_supp"]) == ["HEURES_SUPP"]


def test_prevoyance_cotisation_ids_resolve_to_distinct_sources():
    assert resolve_source_keys(cotisation_ids=["prevoyance_cadre"]) == ["PREVOYANCE_CADRE"]
    assert resolve_source_keys(cotisation_ids=["prevoyance_non_cadre"]) == [
        "PREVOYANCE_NON_CADRE"
    ]
    keys = resolve_source_keys(
        cotisation_ids=["prevoyance_cadre", "prevoyance_non_cadre"],
    )
    assert keys == ["PREVOYANCE_CADRE", "PREVOYANCE_NON_CADRE"]


def test_all_page_source_keys_covers_all_rate_categories():
    from app.modules.rates.domain.rate_source_mapping import (
        RATE_KEY_TO_SOURCE_KEYS,
        all_page_source_keys,
        normalize_source_key,
    )

    page_keys = {normalize_source_key(k) for k in all_page_source_keys()}
    for rate_key, source_keys in RATE_KEY_TO_SOURCE_KEYS.items():
        for sk in source_keys:
            assert normalize_source_key(sk) in page_keys, f"{rate_key} -> {sk} absent de la sync complète"
