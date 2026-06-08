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

    with patch.object(vm, "_fichierdirect_reachable", return_value=True), patch.object(
        vm.requests, "get", return_value=mock_resp
    ), patch.object(vm, "download_file", return_value=str(xlsx_path)):
        data, links = vm.scrape_vmrr_from_urssaf(download_folder=str(tmp_path))

    assert data is not None
    assert len(data) > 100
    assert links


def test_scrape_vmrr_falls_back_to_open_data(tmp_path):
    vm = _load_vm()

    sample_csv = (
        "code_commune;nom_commune;region;date_debut;date_fin;taux_vm;taux_vma;taux_vmr\n"
        + "".join(
            f"{i:05d};COMM{i};Région;20260101;;1.0;;\n" for i in range(150)
        )
    )
    mock_resp = MagicMock()
    mock_resp.content = sample_csv.encode("utf-8")
    mock_resp.text = sample_csv
    mock_resp.raise_for_status = MagicMock()

    def fake_get(url, **kwargs):
        if "open.urssaf.fr" in url:
            return mock_resp
        raise vm.requests.exceptions.ConnectTimeout("timeout")

    with patch.object(vm, "_fichierdirect_reachable", return_value=False), patch.object(
        vm.requests, "get", side_effect=fake_get
    ), patch.object(vm, "download_file", return_value=None):
        data, links = vm.scrape_vmrr_from_urssaf(download_folder=str(tmp_path))

    assert data is not None
    assert len(data) >= 100
    assert any("open.urssaf.fr" in link for link in links)
