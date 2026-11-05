"""Attestation de salaire : les mois repris des bulletins remis (décision du 05/11/2026).

Les n mois les plus récents (3 par défaut), du plus ancien au plus récent ; deux
bulletins le même mois (un par contrat) font une seule ligne. Le net est celui
de la ligne « Net à payer avant impôt sur le revenu » du bulletin
(synthese_net.net_social_avant_impot).
"""
from __future__ import annotations

import pytest

from app.modules.documents.domain.attestation_salaire import (
    NOMBRE_DE_MOIS_PAR_DEFAUT,
    mois_a_attester,
    total,
)

pytestmark = pytest.mark.unit


def _bulletin(year: int, month: int, brut: float, net: float | None) -> dict:
    donnees: dict = {"salaire_brut": brut}
    if net is not None:
        donnees["synthese_net"] = {"net_social_avant_impot": net}
    return {"year": year, "month": month, "payslip_data": donnees}


def test_trois_mois_par_defaut():
    assert NOMBRE_DE_MOIS_PAR_DEFAUT == 3


def test_les_n_plus_recents_dans_l_ordre_du_calendrier():
    bulletins = [_bulletin(2026, m, 2000.0 + m, 1500.0 + m) for m in (6, 9, 7, 10, 8)]
    lignes = mois_a_attester(bulletins, 3)
    assert [(ligne["year"], ligne["month"]) for ligne in lignes] == [
        (2026, 8),
        (2026, 9),
        (2026, 10),
    ]
    assert lignes[-1] == {"year": 2026, "month": 10, "brut": 2010.0, "net_avant_impot": 1510.0}


def test_le_changement_d_annee_est_respecte():
    bulletins = [_bulletin(2025, 12, 1.0, 1.0), _bulletin(2026, 1, 2.0, 2.0)]
    assert [ligne["month"] for ligne in mois_a_attester(bulletins, 2)] == [12, 1]


def test_deux_bulletins_le_meme_mois_font_une_ligne():
    bulletins = [_bulletin(2026, 9, 1000.10, 800.05), _bulletin(2026, 9, 500.20, 400.10)]
    assert mois_a_attester(bulletins, 3) == [
        {"year": 2026, "month": 9, "brut": 1500.3, "net_avant_impot": 1200.15}
    ]


def test_moins_de_mois_que_demande():
    assert len(mois_a_attester([_bulletin(2026, 9, 1.0, 1.0)], 3)) == 1


def test_un_net_absent_n_est_pas_invente():
    lignes = mois_a_attester([_bulletin(2026, 8, 100.0, 80.0), _bulletin(2026, 9, 100.0, None)], 3)
    assert lignes[1]["net_avant_impot"] is None
    assert total(lignes, "net_avant_impot") is None
    assert total(lignes, "brut") == 200.0


def test_aucun_bulletin():
    assert mois_a_attester([], 3) == []
    assert total([], "brut") is None
