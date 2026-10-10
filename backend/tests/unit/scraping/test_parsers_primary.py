"""Tests parsers primaires sur fixtures HTML (sans réseau)."""

import importlib.util
from datetime import datetime
from unittest.mock import MagicMock, patch

from bs4 import BeautifulSoup

from tests.unit.scraping.helpers import SCRAPING_ROOT, load_scraping_fixture


def _load_module(folder: str, filename: str, mod_name: str):
    path = SCRAPING_ROOT / folder / filename
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_smic_extract_from_fixture():
    smic = _load_module("SMIC", "SMIC.py", "smic_parser")
    soup = BeautifulSoup(load_scraping_fixture("smic", "urssaf.html"), "html.parser")
    data = smic.extract_smic_data(soup, reference_date=datetime(2026, 6, 15).date())
    assert data["annee"] == 2026
    assert data["cas_general"] == 12.31
    assert data["smic_mensuel_brut"] == 1867.02
    assert data["jeune_17_ans"] <= data["cas_general"]
    assert data["jeune_moins_17_ans"] <= data["jeune_17_ans"]


def test_pss_extract_from_fixture():
    pss = _load_module("PSS", "PSS.py", "pss_parser")
    soup = BeautifulSoup(load_scraping_fixture("pss", "urssaf.html"), "html.parser")
    data = pss.extract_pss_data(soup)
    assert 40000 <= data["annuel"] <= 60000
    assert data["mensuel"] is not None
    assert data.get("horaire") is not None
    assert data["horaire"] == 30  # valeur officielle 2026, lue sur la ligne « Heure »
    assert data["journalier"] == 220


def test_pss_sans_ligne_heure_ne_calcule_pas_de_plafond_horaire():
    pss = _load_module("PSS", "PSS.py", "pss_parser_sans_heure")
    html = load_scraping_fixture("pss", "urssaf.html")
    sans_heure = "\n".join(l for l in html.splitlines() if "Heure" not in l)
    data = pss.extract_pss_data(BeautifulSoup(sans_heure, "html.parser"))
    assert data["mensuel"] == 4005
    assert data["horaire"] is None  # ni mensuel / 151,67, ni journalier / 7


def test_pss_ai_accepte_le_plafond_horaire_officiel_2026():
    pss_ai = _load_module("PSS", "PSS_AI.py", "pss_ai_parser")
    brut = {"annuel": 48060, "mensuel": 4005, "journalier": 220, "horaire": 30}
    assert pss_ai._complete_pss_plafonds(brut)["horaire"] == 30


def test_pss_ai_ne_devine_pas_un_horaire_absent_ou_invraisemblable():
    pss_ai = _load_module("PSS", "PSS_AI.py", "pss_ai_parser_2")
    base = {"annuel": 48060, "mensuel": 4005, "journalier": 220}
    assert "horaire" not in pss_ai._complete_pss_plafonds({**base, "horaire": None})
    assert "horaire" not in pss_ai._complete_pss_plafonds({**base, "horaire": 90})


@patch("requests.get")
def test_csg_extract_from_fixture(mock_get):
    csg = _load_module("CSG", "CSG.py", "csg_parser")
    mock_resp = MagicMock()
    mock_resp.text = load_scraping_fixture("csg", "urssaf.html")
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    rates = csg.get_taux_csg()
    assert rates is not None
    assert 0.04 <= rates["deductible"] <= 0.05
    assert 0.06 <= rates["non_deductible"] <= 0.08


@patch("requests.get")
def test_alloc_extract_from_fixture(mock_get):
    alloc = _load_module("alloc", "alloc.py", "alloc_parser")
    mock_resp = MagicMock()
    mock_resp.text = load_scraping_fixture("alloc", "urssaf.html")
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    plein, reduit = alloc.get_allocations_rates()
    assert plein is not None and reduit is not None
    assert plein > reduit
    assert 0.03 <= plein <= 0.06
    assert 0.02 <= reduit <= 0.05


def test_bareme_extract_from_fixture():
    bareme = _load_module(
        "bareme-indemnite-kilometrique",
        "bareme-indemnite-kilometrique.py",
        "bareme_km_parser",
    )
    soup = BeautifulSoup(
        load_scraping_fixture("bareme", "service_public.html"), "html.parser"
    )
    voitures = bareme.scrape_voitures(soup)
    motos = bareme.scrape_moto(soup)
    cyclos = bareme.scrape_cyclo(soup)
    payload = bareme.build_payload(voitures, motos, cyclos)
    assert payload["annee"] == datetime.now().year
    assert len(payload["vehicules"]["voitures"]["tranches_cv"]) >= 2
    assert len(payload["vehicules"]["motocyclettes"]["tranches_cv"]) >= 1
