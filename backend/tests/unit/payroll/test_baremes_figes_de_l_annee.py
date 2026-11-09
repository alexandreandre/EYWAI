"""Un mois d'une année terminée se recalcule à ses propres barèmes (R-229)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from app.modules.payroll.engine.baremes_loader import assembler_baremes, baremes_de_l_annee

pytestmark = pytest.mark.unit

_ACTIFS = {
    "smic": {"annee": 2027, "horaire": 12.5},
    "pss": {"mensuel": 4100},
    "pas": {"baremes": [{"taux": 1}]},
    "primes": [],
}
_FIGE = {"smic": {"annee": 2026, "horaire": 12.02}, "pss": {"mensuel": 4005}, "pas": {"baremes": [{"taux": 2}]}}


def test_sans_ligne_figee_le_calcul_ne_change_pas():
    baremes = assembler_baremes(_ACTIFS)
    assert "baremes_figes" not in baremes
    assert baremes_de_l_annee(baremes, 2026) is baremes


def test_un_bulletin_de_l_annee_figee_prend_ses_taux():
    baremes = assembler_baremes({**_ACTIFS, "baremes_figes_2026": _FIGE})
    vus = baremes_de_l_annee(baremes, 2026)
    assert vus["smic"]["horaire"] == 12.02
    assert vus["pss"]["mensuel"] == 4005
    assert vus["pas"] == [{"taux": 2}]


def test_un_bulletin_de_l_annee_en_cours_garde_les_taux_actifs():
    baremes = assembler_baremes({**_ACTIFS, "baremes_figes_2026": _FIGE})
    assert baremes_de_l_annee(baremes, 2027)["smic"]["horaire"] == 12.5


def _script():
    chemin = Path(__file__).resolve().parents[3] / "scripts" / "figer_baremes.py"
    spec = importlib.util.spec_from_file_location("figer_baremes", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_le_script_refuse_de_figer_une_autre_annee():
    lignes = [
        {"config_key": "smic", "config_data": {"annee": 2027}},
        {"config_key": "reduction_generale", "config_data": {"annee": 2027}},
    ]
    with pytest.raises(SystemExit):
        _script().contenu_a_figer(lignes, 2026)


def test_le_script_n_emporte_ni_le_versement_mobilite_ni_le_verrou():
    lignes = [
        {"config_key": "smic", "config_data": {"annee": 2026}},
        {"config_key": "reduction_generale", "config_data": {"annee": 2026}},
        {"config_key": "taux_vmrr", "config_data": {"gros": 1}},
        {"config_key": "payslip_edit_lock", "config_data": {"enabled": False}},
    ]
    assert set(_script().contenu_a_figer(lignes, 2026)) == {"smic", "reduction_generale"}
