"""Apprenti : part retraite complémentaire de la réduction (106) et exonération
salariale de retraite complémentaire (109). Déjà fait ; ce test le garde.

Audit du 03/11/2026 (lot A, verdicts 1a et 1b) : dans deux sociétés de la
métallurgie, l'ancien logiciel ne déclarait jamais le code 106 pour les
apprentis et retenait la retraite complémentaire salariale (4,01 %) sur tout le
brut. Agirc-Arrco, FAQ « Apprentis » (mai 2025) : la réduction « est déclarée via
le code 106 » ; l'exonération salariale, au taux obligatoire et à la CEG, « en
code 109 » ; code du travail, L6243-2 et D6243-5 : exonération jusqu'à 50 % du
SMIC pour un contrat conclu depuis le 01/03/2025.

Martine : la réduction générale d'un apprenti se ventile en 018 et 106 comme
pour tout salarié ; l'exonération salariale de l'apprenti couvre la retraite
complémentaire (la configuration `alternance` n'en exclut que la mutuelle, la
prévoyance et l'APEC), déclarée en 109 avec le 131 net.
"""

from __future__ import annotations

import pytest

from tests.unit.dsn_export.test_apprenti_exoneration import BRUT, EXONERE, LIGNES_APPRENTI
from app.modules.dsn_export.domain.cotisation_mapping import build_bases_and_cotisations

pytestmark = pytest.mark.unit


def _codes():
    lignes = LIGNES_APPRENTI + [
        {"coti_id": "fnal", "base": BRUT, "taux_patronal": 0.001, "montant_patronal": 1.15},
        {"coti_id": "reduction_generale", "base": BRUT, "montant_patronal": -458.38},
    ]
    _bases, cotisations, _ = build_bases_and_cotisations(
        lignes, brut=BRUT, period_start="01102026", period_end="31102026",
        default_ops="OPS-URSSAF", code_exoneration_apprenti="002",
    )
    return [c.rubriques for c in cotisations]


def test_la_reduction_d_un_apprenti_porte_sa_part_retraite_en_106():
    rubriques = _codes()
    part_106 = [r for r in rubriques if r["S21.G00.81.001"] == "106"]
    part_018 = [r for r in rubriques if r["S21.G00.81.001"] == "018"]
    assert part_106 and part_018
    attendu = round(-458.38 * 0.0601 / 0.3981, 2)
    assert float(part_106[0]["S21.G00.81.004"]) == attendu
    assert round(float(part_018[0]["S21.G00.81.004"]) + attendu, 2) == -458.38


def test_l_exoneration_salariale_de_retraite_complementaire_est_en_109():
    rubriques = _codes()
    (exoneration,) = [r for r in rubriques if r["S21.G00.81.001"] == "109"]
    assert float(exoneration["S21.G00.81.003"]) == EXONERE



def test_au_bulletin_la_retraite_complementaire_salariale_de_l_apprenti_est_exoneree():
    """Le moteur exonère sur la part sous le plafond toute cotisation salariale
    non exclue, retraite complémentaire et CEG comprises."""
    from app.modules.payroll.engine.calcul_cotisations import calculer_cotisations
    from app.modules.payroll.engine.exoneration_alternance import contexte_exoneration_apprenti
    from tests.unit.payroll.fixtures.baremes_snapshot import baremes_snapshot_csg_unifie
    from tests.unit.payroll.helpers import build_test_contexte

    baremes = baremes_snapshot_csg_unifie()
    # Les deux cotisations Agirc-Arrco de la tranche 1, aux taux de 2026.
    baremes["cotisations"]["cotisations"] += [
        {"id": "retraite_comp_t1", "libelle": "Retraite complémentaire T1", "base": "brut_plafonne",
         "salarial": 0.0315, "patronal": 0.0472},
        {"id": "ceg_t1", "libelle": "CEG T1", "base": "brut_plafonne", "salarial": 0.0086, "patronal": 0.0129},
    ]
    ctx = build_test_contexte(
        salaire_base=1200.0,
        type_contrat="Apprentissage",
        date_debut_execution="2025-09-01",
        baremes=baremes,
    )
    exo = contexte_exoneration_apprenti(ctx)
    lignes, _ = calculer_cotisations(ctx, 1200.0)
    par_id = {l.get("coti_id"): l for l in lignes}
    retraite = [par_id[c] for c in ("retraite_comp_t1", "ceg_t1") if c in par_id]
    assert len(retraite) == 2
    part_retraite = sum(
        round(l["taux_salarial"] * min(l["base"], exo["plafond"]), 2) for l in retraite
    )
    exoneration = -par_id["exoneration_apprenti_salariale"]["montant_salarial"]
    sans_retraite = sum(
        round(l["taux_salarial"] * min(l["base"], exo["plafond"]), 2)
        for l in lignes
        for cid in [l.get("coti_id")]
        if cid not in ("retraite_comp_t1", "ceg_t1", "exoneration_apprenti_salariale")
        and isinstance(l.get("taux_salarial"), (int, float))
        and l.get("taux_salarial")
        and cid not in exo["cotisations_exclues"]
        and cid not in ("csg", "csg_deductible", "csg_non_deductible", "crds")
    )
    assert part_retraite > 0
    assert exoneration == pytest.approx(sans_retraite + part_retraite, abs=0.05)
