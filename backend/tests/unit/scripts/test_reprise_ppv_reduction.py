"""La PPV de 2026 s'ajoute une seule fois au brut de la réduction repris de Quadra."""

import pytest

from scripts.reprise_ppv_reduction import (
    CLE_BRUT_HORS,
    CLE_TRACE,
    cumuls_ajustes,
    ppv_par_nir,
)

DSN = "\n".join([
    "S21.G00.30.001,'190017512345678'",
    "S21.G00.52.001,'904'",
    "S21.G00.52.002,'100.00'",
    "S21.G00.52.001,'011'",
    "S21.G00.52.002,'1070.80'",
    "S21.G00.30.001,'290017512345678'",
    "S21.G00.52.001,'906'",
    "S21.G00.52.002,'50.00'",
])


def test_seules_les_primes_de_partage_comptent():
    assert ppv_par_nir(DSN) == {"1900175123456": 100.0, "2900175123456": 50.0}


def test_la_ppv_s_ajoute_au_brut_de_la_reduction():
    nouveaux = cumuls_ajustes({"cumuls": {"brut_total": 26680.44}}, 200.0)
    assert nouveaux["cumuls"][CLE_BRUT_HORS] == -200.0 and nouveaux["cumuls"][CLE_TRACE] == 200.0


def test_la_base_d_une_reprise_existante_est_gardee():
    nouveaux = cumuls_ajustes({"cumuls": {CLE_BRUT_HORS: 2320.85}}, 200.0)
    assert nouveaux["cumuls"][CLE_BRUT_HORS] == 2120.85


def test_la_ppv_ne_s_ajoute_pas_deux_fois():
    deja = cumuls_ajustes({"cumuls": {}}, 200.0)
    with pytest.raises(SystemExit, match="déjà"):
        cumuls_ajustes(deja, 200.0)
