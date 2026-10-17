"""Point de départ de la réduction générale posé par une reprise.

Cas réel (Comitech, 2026) : l'ancien logiciel n'a appliqué aucune réduction en
janvier, et sa régularisation progressive part de février. Le solde d'ouverture
repris porte pourtant le brut et les heures imprimés depuis janvier. Sans point
de départ, le premier mois calculé par Martine régularise depuis janvier et
rattrape la réduction de janvier, sans reprendre les cotisations de janvier.

La reprise pose donc, dans les cumuls, le brut et les heures des mois que
l'ancien logiciel a laissés hors de la réduction. La réduction les retire de
sa base ; les cumuls imprimés (brut et heures de l'année) n'en sont pas
changés. Le point de départ vaut pour l'année de la reprise : janvier suivant
l'efface.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from app.modules.payroll.documents.payslip_run_common import mettre_a_jour_cumuls
from app.modules.payroll.engine.calcul_reduction_generale import (
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

#: Un salarié à 39 h, payé 2 100 € pour 169 h chaque mois.
BRUT = 2100.0
HEURES = 169.0

#: Ce que la reprise pose quand l'ancien logiciel a commencé en février.
POINT_DE_DEPART = {
    "reduction_generale_depuis_mois": 2,
    "brut_hors_reduction_generale": BRUT,
    "heures_hors_reduction_generale": HEURES,
}


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


def _reduction_cumulee(mois: int) -> float:
    coefficient, _ = calculer_coefficient_rgdu(
        mois * BRUT, 12.02 * mois * HEURES, tmin=0.02, tdelta=0.3781, p=1.75
    )
    return round(mois * BRUT * coefficient, 2)


def _ouverture_au_31_aout(point_de_depart: bool) -> dict:
    """Brut et heures imprimés de janvier à août ; réduction de février à août."""
    cumuls = {
        "brut_total": 8 * BRUT,
        "heures_remunerees": 8 * HEURES,
        "reduction_generale_patronale": -_reduction_cumulee(7),
    }
    if point_de_depart:
        cumuls.update(POINT_DE_DEPART)
    return cumuls


def _bulletin(cumuls_precedents: dict, year: int, month: int) -> tuple[float, dict]:
    """La ligne de réduction du mois et les cumuls écrits à la fin du mois."""
    contexte = _contexte(cumuls_precedents, year, month)
    ligne = calculer_reduction_generale(contexte, BRUT, HEURES)
    dossier = Path(tempfile.mkdtemp(prefix="rg_point_de_depart_"))
    mettre_a_jour_cumuls(
        contexte,
        BRUT,
        0.0,
        {"net_imposable": 1700.0},
        ligne,
        month,
        1823.0,
        4005.0,
        dossier,
        heures_remunerees_mois=HEURES,
    )
    ecrits = json.loads((dossier / "cumuls" / f"{month:02d}.json").read_text(encoding="utf-8"))
    return ligne["montant_patronal"], ecrits["cumuls"]


def test_la_lecture_retire_les_mois_hors_reduction():
    contexte = _contexte(_ouverture_au_31_aout(point_de_depart=True), 2026, 9)
    brut, heures, deja = _lire_cumuls_precedents(contexte)
    assert brut == pytest.approx(7 * BRUT)
    assert heures == pytest.approx(7 * HEURES)
    # La réduction déjà appliquée est celle de l'ancien logiciel, inchangée.
    assert deja == pytest.approx(_reduction_cumulee(7))


def test_sans_point_de_depart_la_lecture_est_inchangee():
    contexte = _contexte(_ouverture_au_31_aout(point_de_depart=False), 2026, 9)
    brut, heures, _ = _lire_cumuls_precedents(contexte)
    assert brut == pytest.approx(8 * BRUT)
    assert heures == pytest.approx(8 * HEURES)


def test_septembre_ne_rattrape_pas_janvier():
    """Même salaire chaque mois : la réduction de septembre est celle d'un mois,
    comme chez l'ancien logiciel, et non un mois plus la réduction de janvier."""
    septembre, _ = _bulletin(_ouverture_au_31_aout(point_de_depart=True), 2026, 9)
    un_mois = -(_reduction_cumulee(8) - _reduction_cumulee(7))
    assert septembre == pytest.approx(un_mois, abs=0.02)

    rattrapage, _ = _bulletin(_ouverture_au_31_aout(point_de_depart=False), 2026, 9)
    # Sans point de départ, janvier est rattrapé : presque deux mois d'un coup.
    assert rattrapage < septembre - 0.9 * abs(un_mois)


def test_les_cumuls_imprimes_gardent_janvier():
    _, septembre = _bulletin(_ouverture_au_31_aout(point_de_depart=True), 2026, 9)
    assert septembre["brut_total"] == pytest.approx(9 * BRUT)
    assert septembre["brut_annee_civile"] == pytest.approx(9 * BRUT)
    assert septembre["heures_remunerees"] == pytest.approx(9 * HEURES)
    # Réduction cumulée de février à septembre, comme l'ancien logiciel la compte.
    assert septembre["reduction_generale_patronale"] == pytest.approx(
        -_reduction_cumulee(8), abs=0.02
    )


def test_le_point_de_depart_suit_les_mois_de_l_annee():
    _, septembre = _bulletin(_ouverture_au_31_aout(point_de_depart=True), 2026, 9)
    for cle, valeur in POINT_DE_DEPART.items():
        assert septembre[cle] == valeur
    octobre, _ = _bulletin(septembre, 2026, 10)
    un_mois = -(_reduction_cumulee(9) - _reduction_cumulee(8))
    assert octobre == pytest.approx(un_mois, abs=0.02)


def test_janvier_suivant_efface_le_point_de_depart():
    cumuls = _ouverture_au_31_aout(point_de_depart=True)
    for mois in range(9, 13):
        _, cumuls = _bulletin(cumuls, 2026, mois)
    janvier, cumuls = _bulletin(cumuls, 2027, 1)
    for cle in POINT_DE_DEPART:
        assert cle not in cumuls
    fevrier, _ = _bulletin(cumuls, 2027, 2)
    # Février 2027 régularise sur janvier 2027 seul : rien n'est retiré.
    assert fevrier == pytest.approx(janvier, abs=0.02)


def test_sans_point_de_depart_aucune_cle_n_est_ajoutee():
    _, septembre = _bulletin(_ouverture_au_31_aout(point_de_depart=False), 2026, 9)
    for cle in POINT_DE_DEPART:
        assert cle not in septembre
    _, janvier = _bulletin(septembre, 2027, 1)
    for cle in POINT_DE_DEPART:
        assert cle not in janvier
