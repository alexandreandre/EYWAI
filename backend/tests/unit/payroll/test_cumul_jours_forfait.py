"""Cumul des jours travaillés d'un forfait jours (retour du 10/11/2026).

Année civile, remis à zéro en janvier. Quand les cumuls du mois d'avant ne le
portent pas (reprise de l'ancien logiciel, premier mois calculé), le décompte
part du mois calculé et le dit (`jours_travailles_forfait_depuis`) : le bulletin
n'affiche jamais un total de l'année qu'il ne connaît pas.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from app.modules.payroll.documents.payslip_run_common import mettre_a_jour_cumuls
from tests.unit.payroll.helpers import build_test_contexte

pytestmark = pytest.mark.unit


def _ecrire(mois, cumuls_avant, jours=None):
    contexte = build_test_contexte(cumuls=json.loads(json.dumps(cumuls_avant)))
    contexte.month = mois
    contexte.year = 2026
    dossier = Path(tempfile.mkdtemp(prefix="cumuls_forfait_"))
    kwargs = {} if jours is None else {"jours_travailles_forfait_mois": jours}
    mettre_a_jour_cumuls(
        contexte,
        salaire_brut_mois=4000.0,
        remuneration_hs_mois=0.0,
        resultats_nets_mois={"net_imposable": 3100.0, "montant_impot_pas": 0.0},
        reduction_generale_mois={},
        mois=mois,
        smic_mois=1800.0,
        pss_mois=4005.0,
        chemin_employe=dossier,
        heures_remunerees_mois=150.28,
        **kwargs,
    )
    return json.loads((dossier / "cumuls" / f"{mois:02d}.json").read_text(encoding="utf-8"))["cumuls"]


def test_le_mois_s_ajoute_au_cumul_d_avant():
    cumuls = _ecrire(10, {"jours_travailles_forfait": 160.0}, jours=21.0)
    assert cumuls["jours_travailles_forfait"] == pytest.approx(181.0)
    assert "jours_travailles_forfait_depuis" not in cumuls


def test_le_mois_de_depart_suit_tant_que_l_annee_court():
    cumuls = _ecrire(
        11,
        {"jours_travailles_forfait": 21.0, "jours_travailles_forfait_depuis": 10},
        jours=20.0,
    )
    assert cumuls["jours_travailles_forfait"] == pytest.approx(41.0)
    assert cumuls["jours_travailles_forfait_depuis"] == 10


def test_sans_cumul_d_avant_le_decompte_part_du_mois():
    cumuls = _ecrire(10, {"heures_remunerees": 1038.29}, jours=21.0)
    assert cumuls["jours_travailles_forfait"] == pytest.approx(21.0)
    assert cumuls["jours_travailles_forfait_depuis"] == 10


def test_janvier_repart_de_zero_sans_mois_de_depart():
    cumuls = _ecrire(
        1,
        {"jours_travailles_forfait": 214.0, "jours_travailles_forfait_depuis": 10},
        jours=19.0,
    )
    assert cumuls["jours_travailles_forfait"] == pytest.approx(19.0)
    assert "jours_travailles_forfait_depuis" not in cumuls


def test_salarie_aux_heures_n_a_pas_ce_cumul():
    cumuls = _ecrire(10, {"heures_remunerees": 1000.0})
    assert "jours_travailles_forfait" not in cumuls
