"""Tests hermétiques du scraper versement mobilité (VM.py)."""

from unittest.mock import MagicMock, patch

import pandas as pd

from tests.unit.scraping.helpers import SCRAPING_ROOT, load_scraping_fixture


def _load_vm():
    import importlib.util

    path = SCRAPING_ROOT / "VM.py"
    spec = importlib.util.spec_from_file_location("vm_module", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_scrape_vmrr_from_fixture(tmp_path):
    vm = _load_vm()
    mock_resp = MagicMock()
    mock_resp.text = load_scraping_fixture("vm", "urssaf_page.html")
    mock_resp.raise_for_status = MagicMock()

    xlsx_path = tmp_path / "vmrr_test.xlsx"
    pd.DataFrame(
        [{"commune": f"C{i:03d}", "taux": 0.012} for i in range(120)]
    ).to_excel(xlsx_path, index=False)

    with patch.object(vm.requests, "get", return_value=mock_resp), patch.object(
        vm, "download_file", return_value=str(xlsx_path)
    ):
        data, links = vm.scrape_vmrr_from_urssaf(download_folder=str(tmp_path))

    assert data is not None
    assert len(data) > 100
    assert links
