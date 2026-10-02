"""Tests parsers secondaires (sources complémentaires) sur fixtures HTML."""

import importlib.util
from unittest.mock import MagicMock, patch

from tests.unit.scraping.helpers import SCRAPING_ROOT


def _load_module(folder: str, filename: str, mod_name: str):
    path = SCRAPING_ROOT / folder / filename
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_dialogue_urssaf_parse_taux():
    dialogue = _load_module("dialoguesocial", "dialoguesocial.py", "dialogue_primary")
    assert dialogue.parse_taux("0,016 %") == 0.00016


@patch("requests.get")
def test_dialogue_urssaf_scrape_from_fixture(mock_get):
    dialogue = _load_module("dialoguesocial", "dialoguesocial.py", "dialogue_primary2")
    mock_resp = MagicMock()
    mock_resp.text = """
    <html><body><table>
    <tr><th>Contribution au dialogue social</th><td>0,016 %</td></tr>
    </table></body></html>
    """
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    rate = dialogue.scrape_dialogue_social_rate()
    assert rate is not None
    assert 0.0 < rate < 0.001


@patch("requests.get")
def test_ij_service_public_from_fixture(mock_get):
    ij = _load_module("IJmaladie", "IJmaladie.py", "ij_sp")
    mock_resp = MagicMock()
    mock_resp.text = """
    <html><body>
    <h5>Plafonds des indemnités journalières en 2026</h5>
    <ul>
    <li>en cas de maladie, à 41,95 €/jour ; pour les congés de maternité et de paternité, à 104,02 €/jour.</li>
    </ul>
    <ul>
    <li>240,49 €/jour pendant les 28 premiers jours d'absence ;
    320,66 €/jour à partir du 29e jour d'arrêt.</li>
    </ul>
    </body></html>
    """
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    with patch.object(ij, "fetch_html", return_value=mock_resp.text):
        plafonds, url = ij.get_plafonds_ij_service_public()
    assert url == ij.URL_SERVICE_PUBLIC
    assert plafonds["maladie"] == 41.95
    assert plafonds["maternite_paternite"] == 104.02
    assert plafonds["at_mp"] == 240.49
    assert plafonds["at_mp_majoree"] == 320.66


def test_cfp_page_also_yields_cpf_cdd_rate():
    cfp = _load_module("CFP", "CFP.py", "cfp_primary_cpf_cdd")
    text = (
        "Le taux de la contribution au CPF-CDD est égal à 1 % "
        "du revenu d'activité retenu pour le calcul des cotisations."
    )
    assert cfp.parse_cpf_cdd_rate(text) == 0.01
    assert cfp.parse_cpf_cdd_rate("pas de taux ici") is None


def test_cfp_build_stamps_cpf_cdd_when_the_page_has_it():
    from core.migrated_specs import _cfp_build

    current = {
        "config_data": {
            "cotisations": [
                {"id": "CFP", "patronal": {"taux_moins_11": 0.0055, "taux_11_et_plus": 0.01}},
                {"id": "cpf_cdd", "libelle": "Contribution CPF des titulaires de CDD", "patronal": 0.01, "salarial": None},
            ]
        }
    }
    built = _cfp_build(
        {"moins_11": 0.0055, "plus_11": 0.01, "cpf_cdd": 0.01},
        current,
    )
    line = next(item for item in built["cotisations"] if item["id"] == "cpf_cdd")
    assert line["patronal"] == 0.01
    assert line["last_checked_at"]
