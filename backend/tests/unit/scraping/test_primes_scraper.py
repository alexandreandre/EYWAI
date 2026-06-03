"""Tests unitaires catalogue des primes (primary + Sonar)."""

import copy

from scraping.primes.primes import CATALOGUE, legal_context_text, make_payload
from scraping.primes.primes_AI import (
    _ai_signature,
    _reference_signature,
    extract_catalogue,
)
from scraping.primes.spec import SPEC, _extract

_ATTENDUES = {
    "prime_exceptionnelle",
    "prime_partage_valeur",
    "prime_anciennete",
    "prime_13eme_mois",
    "prime_vacances",
    "prime_objectifs",
    "indemnite_panier_repas",
}


def test_catalogue_couvre_primes_courantes():
    ids = {p["id"] for p in CATALOGUE["primes"]}
    assert _ATTENDUES <= ids
    assert len(ids) >= 10


def test_catalogue_booleens_valides():
    for prime in CATALOGUE["primes"]:
        assert isinstance(prime["soumise_a_impot"], bool)
        assert isinstance(prime["soumise_a_cotisations"], bool)
        assert prime["libelle"]


def test_ppv_et_panier_exoneres_par_defaut():
    by_id = {p["id"]: p for p in CATALOGUE["primes"]}
    assert by_id["prime_partage_valeur"]["soumise_a_cotisations"] is False
    assert by_id["indemnite_panier_repas"]["soumise_a_cotisations"] is False


def test_legal_context_liste_chaque_prime():
    text = legal_context_text()
    for prime in CATALOGUE["primes"]:
        assert prime["id"] in text


def test_reference_signature_coherente_avec_spec():
    assert _reference_signature() == _extract(make_payload())


def test_spec_dual_source_consensus_actif():
    assert SPEC.primary_label == "primes.py"
    assert SPEC.requires_scraper_sonar_consensus() is True
    labels = [s.label for s in SPEC.scripts]
    assert labels == ["primes.py", "primes_AI.py"]


def test_extract_catalogue_consensus_ok(monkeypatch):
    reference = _reference_signature()
    fake = {
        "primes": [
            {
                "id": pid,
                "soumise_a_impot": v["soumise_a_impot"],
                "soumise_a_cotisations": v["soumise_a_cotisations"],
            }
            for pid, v in reference.items()
        ]
    }
    monkeypatch.setattr(
        "scraping.primes.primes_AI.extract_structured_json",
        lambda **kw: copy.deepcopy(fake),
    )
    catalogue = extract_catalogue()
    assert catalogue is not None
    assert _extract({"config_data": catalogue}) == reference


def test_extract_catalogue_divergence_rejetee(monkeypatch):
    reference = _reference_signature()
    fake = {
        "primes": [
            {
                "id": pid,
                "soumise_a_impot": not v["soumise_a_impot"],
                "soumise_a_cotisations": v["soumise_a_cotisations"],
            }
            for pid, v in reference.items()
        ]
    }
    monkeypatch.setattr(
        "scraping.primes.primes_AI.extract_structured_json",
        lambda **kw: copy.deepcopy(fake),
    )
    assert extract_catalogue() is None


def test_ai_signature_ignore_entrees_invalides():
    data = {"primes": [{"soumise_a_impot": True}, None, "x"]}
    assert _ai_signature(data) == {}
