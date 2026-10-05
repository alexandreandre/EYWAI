"""La réduction générale passe le 1ᵉʳ janvier sans rembourser ni s'éteindre.

La régularisation progressive se calcule sur l'année civile (CSS L241-13, III ;
D241-7). Janvier remet à zéro les heures et la réduction cumulées ; le brut
lu par la réduction doit repartir avec elles. `brut_total`, lui, continue
d'additionner : la prime de précarité (fenêtre du contrat) et la base du
dixième des congés (1ᵉʳ juin au 31 mai) s'en servent. La réduction lit donc
un compteur à part, `brut_annee_civile`.

Les cumuls écrits avant ce compteur (reprise de l'ancien logiciel, septembre
2026) ne l'ont pas : leur `brut_total` est le cumul de l'année civile 2026,
il le remplace.
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

#: Paramètres RGDU 2026 lus sur la base de test le 05/10/2026.
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


def _contexte(cumuls: dict, year: int, month: int):
    contexte = build_test_contexte(cumuls=cumuls, effectif=19)
    contexte.baremes["reduction_generale"] = dict(RGDU_2026)
    contexte.year = year
    contexte.month = month
    return contexte


def _cumuls_de_novembre_2026() -> dict:
    """Onze mois repris de l'ancien logiciel, sans le compteur d'année civile."""
    coefficient, _ = calculer_coefficient_rgdu(
        11 * BRUT, 12.02 * 11 * HEURES, tmin=0.02, tdelta=0.3781, p=1.75
    )
    return {
        "brut_total": 11 * BRUT,
        "heures_remunerees": 11 * HEURES,
        "reduction_generale_patronale": -round(11 * BRUT * coefficient, 2),
    }


def _bulletin(cumuls_precedents: dict, year: int, month: int) -> tuple[float, dict]:
    """La ligne de réduction du mois et les cumuls écrits à la fin du mois."""
    contexte = _contexte(cumuls_precedents, year, month)
    ligne = calculer_reduction_generale(contexte, BRUT, HEURES)
    dossier = Path(tempfile.mkdtemp(prefix="rg_annee_civile_"))
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


def test_decembre_2026_a_mars_2027_la_reduction_reste_stable():
    decembre, cumuls = _bulletin(_cumuls_de_novembre_2026(), 2026, 12)
    janvier, cumuls = _bulletin(cumuls, 2027, 1)
    fevrier, cumuls = _bulletin(cumuls, 2027, 2)
    mars, _ = _bulletin(cumuls, 2027, 3)

    assert decembre < 0
    # Même salaire, mêmes heures : même réduction chaque mois, au centime près
    # (arrondi de la réduction cumulée). Février ne rembourse pas janvier, et
    # mars n'est pas nul.
    for montant in (janvier, fevrier, mars):
        assert montant == pytest.approx(decembre, abs=0.02)


def test_le_brut_de_l_annee_civile_repart_en_janvier_et_brut_total_continue():
    _, decembre = _bulletin(_cumuls_de_novembre_2026(), 2026, 12)
    _, janvier = _bulletin(decembre, 2027, 1)
    _, fevrier = _bulletin(janvier, 2027, 2)

    # Décembre part du brut repris (cumul de l'année 2026).
    assert decembre["brut_annee_civile"] == pytest.approx(12 * BRUT)
    assert janvier["brut_annee_civile"] == pytest.approx(BRUT)
    assert fevrier["brut_annee_civile"] == pytest.approx(2 * BRUT)
    # Précarité et dixième des congés : le brut sans remise à zéro.
    assert fevrier["brut_total"] == pytest.approx(14 * BRUT)


def test_fevrier_lit_le_brut_de_l_annee_civile():
    contexte = _contexte(
        {
            "brut_total": 13 * BRUT,
            "brut_annee_civile": BRUT,
            "heures_remunerees": HEURES,
            "reduction_generale_patronale": -770.0,
        },
        2027,
        2,
    )
    brut, heures, deja = _lire_cumuls_precedents(contexte)
    assert (brut, heures, deja) == pytest.approx((BRUT, HEURES, 770.0))


def test_sans_le_compteur_les_cumuls_repris_en_2026_valent_pour_l_annee_civile():
    contexte = _contexte(_cumuls_de_novembre_2026(), 2026, 12)
    brut, _, _ = _lire_cumuls_precedents(contexte)
    assert brut == pytest.approx(11 * BRUT)
