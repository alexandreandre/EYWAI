"""Tests du harness test_scrapers (réseau flaky, manifeste)."""

from scraper_manifest import SCRAPER_MANIFEST
from test_scrapers import is_network_failure


def test_vm_marked_network_flaky():
    vm = next(e for e in SCRAPER_MANIFEST if e.name == "VM")
    assert vm.network_flaky is True


def test_is_network_failure_detects_timeout():
    assert is_network_failure({"stderr": "ConnectTimeout on urssaf.fr", "data": {}})


def test_is_network_failure_detects_empty_sources():
    assert is_network_failure(
        {"data": {"success": False, "sources_used": None}, "stderr": ""}
    )
