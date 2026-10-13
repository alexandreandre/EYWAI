"""Mention « dont évolution de la rémunération liée à la suppression des
cotisations salariales chômage et maladie » : sur l'assiette réellement
cotisable pour un apprenti.

La mention vaut 3,15 % du brut (maladie 0,75 % et chômage 2,40 % supprimés en
2018) moins 1,70 % de la base de CSG. Un apprenti ne cotise que sur la part de
son salaire au-delà du plafond d'exonération : la mention calculée sur tout le
brut la surestimait (31,57 € pour 1 100 € de brut). Décision du 12/10/2026 :
corriger la mention, sans changer aucun montant du bulletin.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.documents.bulletin_view import _evolution_remuneration, construire_pied

pytestmark = pytest.mark.unit


def _apprenti(brut: float, base_exoneree: float, base_csg: float | None) -> dict:
    bulletin = {
        "salaire_brut": brut,
        "net_a_payer": brut,
        "structure_cotisations": {
            "bloc_allegements": [
                {
                    "coti_id": "exoneration_apprenti_salariale",
                    "libelle": "Exonération cotisations salariales apprenti",
                    "base": base_exoneree,
                    "montant_salarial": -105.58,
                }
            ]
        },
        "cotisations_officielles": [],
    }
    if base_csg is not None:
        bulletin["cotisations_officielles"] = [
            {"code": "csg_deductible", "lignes": [{"base": base_csg, "montant_salarial": 11.12}]}
        ]
    return bulletin


def test_l_apprenti_au_dela_du_plafond_ne_compte_que_la_part_cotisable():
    # (1 100 − 933,51) × 3,15 % − 163,58 × 1,70 % = 5,24 − 2,78.
    assert _evolution_remuneration(_apprenti(1100.0, 933.51, 163.58)) == 2.46


def test_l_apprenti_sous_le_plafond_n_a_rien_a_mentionner():
    # Tout le salaire est exonéré, aucune CSG : la mention ne retombe pas sur le brut.
    assert _evolution_remuneration(_apprenti(900.0, 900.0, None)) == 0.0


def test_un_salarie_ordinaire_ne_change_pas():
    bulletin = {
        "salaire_brut": 2000.0,
        "cotisations_officielles": [{"code": "csg_deductible", "lignes": [{"base": 2000.0}]}],
    }
    assert _evolution_remuneration(bulletin) == 29.0


def test_le_pied_du_bulletin_imprime_la_mention_corrigee_sans_toucher_au_net():
    pied = construire_pied(_apprenti(1100.0, 933.51, 163.58))
    assert pied["evolution_remuneration"] == 2.46
    assert pied["net_a_payer"] == 1100.0
