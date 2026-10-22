"""Une régularisation de cotisation se déclare avec sa ligne d'origine.

Le montant et l'assiette s'additionnent. Le taux reste celui de la cotisation.
"""

from __future__ import annotations

import pytest

from app.modules.dsn_export.domain.cotisation_mapping import build_bases_and_cotisations
from app.modules.payroll.engine.corrections_manuelles import RegularisationCotisation

pytestmark = pytest.mark.unit


def _maladie(base):
    return {
        "coti_id": "securite_sociale_maladie",
        "libelle": "Sécurité sociale - Maladie",
        "base": base,
        "taux_salarial": None,
        "taux_patronal": 0.07,
        "montant_salarial": 0.0,
        "montant_patronal": round(base * 0.07, 2),
    }


def _cotisations(lignes):
    _, cotisations, _ = build_bases_and_cotisations(
        lignes, brut=2000.0, period_start="2026-10-01", period_end="2026-10-31"
    )
    return cotisations


def _par_code(cotisations, code):
    trouvees = [c for c in cotisations if c.code == code]
    assert len(trouvees) == 1, trouvees
    return trouvees[0]


def test_la_regularisation_ajoute_son_montant_et_son_assiette_et_garde_le_taux():
    regul = RegularisationCotisation(
        coti_id="securite_sociale_maladie",
        libelle="Sécurité sociale - Maladie",
        motif="Base oubliée",
        base=100.0,
        taux_patronal=0.07,
    ).ligne_de_cotisation()
    sans = _par_code(_cotisations([_maladie(2000.0)]), "075")
    avec = _par_code(_cotisations([_maladie(2000.0), regul]), "075")
    assert avec.montant_patronal == pytest.approx(sans.montant_patronal + 7.0, abs=0.001)
    assert avec.montant_assiette == pytest.approx(sans.montant_assiette + 100.0, abs=0.001)
    assert avec.rubriques.get("S21.G00.81.007") == sans.rubriques.get("S21.G00.81.007")


def test_sans_regularisation_la_dsn_ne_change_pas():
    assert _cotisations([_maladie(2000.0)]) == _cotisations([_maladie(2000.0)])
