"""Tests du manifeste orchestrateurs."""

from scraper_manifest import SCRAPER_MANIFEST, get_manifest


def test_manifest_has_27_entries():
    assert len(SCRAPER_MANIFEST) == 27


def test_manifest_unique_names():
    names = [e.name for e in SCRAPER_MANIFEST]
    assert len(names) == len(set(names))


def test_manifest_orchestrator_files_exist():
    from tests.unit.scraping.helpers import SCRAPING_ROOT

    for entry in SCRAPER_MANIFEST:
        orch = SCRAPING_ROOT / entry.dir / entry.orchestrator
        assert orch.is_file(), f"Orchestrateur manquant: {orch}"


def test_critical_scrapers_include_core_rates():
    critical = {e.name for e in SCRAPER_MANIFEST if e.tier == "critical"}
    assert {"SMIC", "PSS", "PAS", "CSG", "dialoguesocial", "AGS"}.issubset(critical)


def test_get_manifest_filter_tier():
    critical = get_manifest(tier="critical")
    assert all(e.tier == "critical" for e in critical)
    assert len(critical) >= 10
