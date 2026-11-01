"""La prime de partage de la valeur entre dans la rémunération de la réduction.

« La rémunération prise en compte pour la détermination du coefficient est celle
définie à l'article L. 242-1, majorée le cas échéant du montant de la prime de
partage de la valeur » (CSS L241-13, III ; BOSS, réduction générale, § 170). Elle
compte au mois de son versement (§ 200), exonérée ou non (règle R-B1,
docs/reference/reduction-generale-2026/regles.md). La part au-delà du plafond
est déjà dans le brut soumis : seule la part exonérée s'y ajoute.

Elle suit au cumul de l'année civile (`ppv_annee_civile`) : sans lui, le mois
suivant recalculerait la réduction sans elle et en reprendrait l'effet.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from app.modules.payroll.documents.payslip_run_common import mettre_a_jour_cumuls
from app.modules.payroll.engine.calcul_reduction_generale import (
    CLE_PPV_ANNEE,
    _lire_cumuls_precedents,
    calculer_coefficient_rgdu,
    calculer_reduction_generale,
)
from tests.unit.payroll.helpers import build_test_contexte

pytestmark = pytest.mark.unit

RGDU_2026 = {
    "p": 1.75,
    "tmin": 0.02,
    "type": "RGDU",
    "actif": True,
    "annee": 2026,
    "tdelta": {"fnal_moins_50": 0.3781, "fnal_50_et_plus": 0.3821},
    "point_sortie_smic": 3.0,
    "smic_reference_horaire": 12.02,
}

BRUT = 1900.0
HEURES = 151.67
PPV = 500.0


def _contexte(cumuls: dict, year: int, month: int):
    contexte = build_test_contexte(cumuls=cumuls, effectif=17)
    contexte.baremes["reduction_generale"] = dict(RGDU_2026)
    contexte.baremes["smic"] = {
        **contexte.baremes["smic"],
        "historique": [
            {"date_debut": "2026-01-01", "cas_general": 12.02},
            {"date_debut": "2027-01-01", "cas_general": 12.02},
        ],
    }
    contexte.year = year
    contexte.month = month
    return contexte


def _due(brut: float, mois: int) -> float:
    """Réduction due sur `mois` mois de SMIC et une rémunération cumulée `brut`."""
    coefficient, _ = calculer_coefficient_rgdu(
        brut, 12.02 * mois * HEURES, tmin=0.02, tdelta=0.3781, p=1.75
    )
    return round(brut * coefficient, 2)


def _six_mois() -> dict:
    return {
        "brut_total": 6 * BRUT,
        "heures_remunerees": 6 * HEURES,
        "reduction_generale_patronale": -_due(6 * BRUT, 6),
    }


def _bulletin(cumuls: dict, year: int, month: int, ppv: float = 0.0) -> tuple[dict, dict]:
    contexte = _contexte(cumuls, year, month)
    ligne = calculer_reduction_generale(contexte, BRUT, HEURES, ppv_mois=ppv)
    dossier = Path(tempfile.mkdtemp(prefix="rg_ppv_"))
    mettre_a_jour_cumuls(
        contexte, BRUT, 0.0, {"net_imposable": 1500.0}, ligne, month, 1823.0, 4005.0,
        dossier, heures_remunerees_mois=HEURES,
    )
    ecrits = json.loads((dossier / "cumuls" / f"{month:02d}.json").read_text(encoding="utf-8"))
    return ligne, ecrits["cumuls"]


def test_la_ppv_du_mois_entre_dans_la_remuneration():
    ligne, _ = _bulletin(_six_mois(), 2026, 7, ppv=PPV)
    du = _due(7 * BRUT + PPV, 7)
    assert ligne["valeur_cumulative_a_enregistrer"] == du
    assert ligne["montant_patronal"] == pytest.approx(-(du - _due(6 * BRUT, 6)), abs=0.01)


def test_la_ppv_suit_au_cumul_et_le_mois_suivant_ne_la_reprend_pas():
    _, juillet = _bulletin(_six_mois(), 2026, 7, ppv=PPV)
    assert juillet[CLE_PPV_ANNEE] == PPV
    # Le brut imprimé reste le brut soumis.
    assert juillet["brut_annee_civile"] == pytest.approx(7 * BRUT)

    aout, cumuls_aout = _bulletin(juillet, 2026, 8)
    assert aout["valeur_cumulative_a_enregistrer"] == _due(8 * BRUT + PPV, 8)
    assert cumuls_aout[CLE_PPV_ANNEE] == PPV


def test_janvier_remet_la_ppv_a_zero():
    _, cumuls = _bulletin(_six_mois(), 2026, 7, ppv=PPV)
    for mois in range(8, 13):
        _, cumuls = _bulletin(cumuls, 2026, mois)
    janvier, cumuls_janvier = _bulletin(cumuls, 2027, 1)
    assert CLE_PPV_ANNEE not in cumuls_janvier
    assert janvier["valeur_cumulative_a_enregistrer"] == _due(BRUT, 1)


def test_sans_ppv_les_cumuls_n_ont_pas_la_cle():
    ligne, cumuls = _bulletin(_six_mois(), 2026, 7)
    assert CLE_PPV_ANNEE not in cumuls
    assert ligne["valeur_cumulative_a_enregistrer"] == _due(7 * BRUT, 7)


def test_la_trace_de_la_reprise_n_est_pas_comptee_une_seconde_fois():
    """La reprise du 01/11 a posé la PPV de Quadra par `brut_hors_reduction_generale`
    négatif, avec sa trace `ppv_reduction_generale` : la lecture ne la relit pas."""
    cumuls = {**_six_mois(), "brut_hors_reduction_generale": -200.0, "ppv_reduction_generale": 200.0}
    brut, _, _ = _lire_cumuls_precedents(_contexte(cumuls, 2026, 7))
    assert brut == pytest.approx(6 * BRUT + 200.0)
