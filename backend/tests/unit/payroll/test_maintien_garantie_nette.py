"""Le maintien de la plasturgie garantit le net (conception du 03/11/2026).

Art. 13 e (non-cadres) et accord Cadres, art. 5 : « l'indemnisation est
déterminée en fonction de la rémunération nette qu'aurait perçue
l'intéressé ». Les IJ déduites sont comptées nettes de CSG et CRDS, puis
ramenées au brut avec la part salariale du salarié : le net reçu est le net
garanti. Le maintien légal reste sur le brut. Initiales seulement.
"""

from __future__ import annotations

import copy

import pytest

from app.modules.payroll.domain.baremes_maintien import (
    GARANTIE_BRUTE,
    GARANTIE_NETTE,
    PLASTURGIE,
    description_lisible,
)
from app.modules.payroll.engine.calcul_cotisations import calculer_cotisations
from app.modules.payroll.engine.garantie_nette import (
    ijss_ramenees_au_brut,
    taux_csg_crds_ijss,
    taux_salarial_marginal,
)

from .test_maintien_paliers_bareme import BAREME, JUILLET, JUIN, MAI, _mois_sg, _sg

pytestmark = pytest.mark.unit


def _net_recu(maintien):
    garantie = maintien["garantie_nette"]
    t, s = garantie["taux_salarial"], garantie["taux_ijss"]
    return maintien["maintien_verse"] * (1 - t) + garantie["ijss_deduites"] * (1 - s)


def _net_garanti(maintien):
    return maintien["maintien_cible"] * (1 - maintien["garantie_nette"]["taux_salarial"])


# --- Le barème et ses outils -------------------------------------------------


def test_la_plasturgie_garantit_le_net_et_le_bareme_lisible_le_dit():
    assert PLASTURGIE.garantie == GARANTIE_NETTE
    assert GARANTIE_BRUTE != GARANTIE_NETTE
    regles = description_lisible(PLASTURGIE)["regles"]
    assert any("garantit le net" in r for r in regles)


def test_les_ijss_nettes_ramenees_au_brut():
    # 100 € d'IJ : 93,30 € nets ; à 22 % de cotisations, 119,62 € de salaire brut.
    assert ijss_ramenees_au_brut(100.0, 0.067, 0.22) == 119.62
    assert ijss_ramenees_au_brut(0.0, 0.067, 0.22) == 0.0


def test_le_taux_des_ijss_est_celui_des_lignes_du_bulletin():
    assert taux_csg_crds_ijss({"csg_ijss": {"taux_deductible": 0.038, "taux_non_deductible": 0.029}}) == pytest.approx(0.067)
    assert taux_csg_crds_ijss({"csg_ijss": {"taux_deductible": 0.04, "taux_non_deductible": 0.03}}) == pytest.approx(0.07)
    assert taux_csg_crds_ijss(None) == pytest.approx(0.067)


def test_le_taux_salarial_est_mesure_par_le_moteur_de_cotisations_sans_toucher_le_contexte():
    contexte = _sg()
    avant = copy.deepcopy(vars(contexte))
    taux = taux_salarial_marginal(contexte, 2231.48, 2059.84)
    _, haut = calculer_cotisations(copy.copy(contexte), 2231.48)
    _, bas = calculer_cotisations(copy.copy(contexte), 2231.48 - 2059.84)
    assert taux == pytest.approx((haut - bas) / 2059.84)
    assert 0.0 < taux < 0.6
    assert vars(contexte) == avant


def test_sans_jours_maintenus_aucun_taux():
    assert taux_salarial_marginal(_sg(), 2231.48, 0.0) is None


# --- Le moteur ---------------------------------------------------------------


def test_s_g_mai_le_net_recu_est_le_net_garanti():
    m = _mois_sg(5, MAI, 1029.75)["maintien"]
    assert m["regle_retenue"] == "convention"
    assert (m["maintien_cible"], m["ijss_deduites"]) == (2059.84, 1029.75)
    garantie = m["garantie_nette"]
    assert garantie["ijss_deduites"] == 1029.75
    assert garantie["taux_ijss"] == pytest.approx(0.067)
    assert _net_recu(m) == pytest.approx(_net_garanti(m), abs=0.01)
    # La lecture brute (celle de Quadra) versait 1 030,09.
    assert garantie["reduction"] == round(1030.09 - m["maintien_verse"], 2) > 0
    assert m["paliers"][0]["ijss_deduites"] == 1029.75


def test_avec_subrogation_meme_deduction_nette():
    reglages = {**BAREME, "subrogation_mode": "when_maintien"}
    m = _mois_sg(6, JUIN, 1235.70, reglages=reglages, subrogation_active=True)["maintien"]
    assert m["maintien_cible"] == 2231.48
    assert m["garantie_nette"]["ijss_deduites"] == 1235.70
    assert _net_recu(m) == pytest.approx(_net_garanti(m), abs=0.01)
    assert m["maintien_verse"] < 995.78  # 995,78 : la lecture brute


def test_sans_deduction_des_ijss_le_garanti_est_verse_en_entier():
    m = _mois_sg(6, JUIN, 1235.70, reglages={**BAREME, "deduire_ijss_sans_subrogation": False})["maintien"]
    assert m["maintien_verse"] == m["maintien_cible"] == 2231.48
    assert "garantie_nette" not in m


def test_le_legal_reste_sur_le_brut():
    """Juillet, 22 ans d'ancienneté : le légal l'emporte, lecture brute inchangée."""
    m = _mois_sg(7, JUILLET, 1276.89)["maintien"]
    assert m["regle_retenue"] == "legal"
    assert (m["maintien_cible"], m["maintien_verse"]) == (1781.95, 505.06)
    assert "garantie_nette" not in m


def test_une_mesure_impossible_garde_la_lecture_brute_et_le_dit(monkeypatch):
    from app.modules.payroll.engine import maintien_salaire_service

    monkeypatch.setattr(maintien_salaire_service, "taux_salarial_marginal", lambda *a, **k: None)
    r = _mois_sg(5, MAI, 1029.75)
    m = r["maintien"]
    assert m["maintien_verse"] == 1030.09
    assert "garantie_nette" not in m
    assert (
        "Garantie du net non calculée (taux de cotisations salariales non mesuré) : "
        "les IJSS brutes sont déduites, plus favorable au salarié."
    ) in r["alertes"]


def test_deux_arrets_du_mois_la_garantie_nette_s_additionne():
    from datetime import date

    from app.modules.payroll.engine.maintien_salaire_service import calculer_maintien

    from .test_maintien_paliers_bareme import _arret

    connus = [("2026-08-03", "2026-08-14"), ("2026-08-17", "2026-08-31")]
    arrets = [_arret(d, f, connus) for d, f in connus]
    seuls = [
        calculer_maintien(a, _sg(), dict(BAREME), date(2026, 8, 1), date(2026, 8, 31))["maintien"]
        for a in arrets
    ]
    mois = calculer_maintien(
        {**arrets[0], "arrets_du_mois": arrets}, _sg(), dict(BAREME), date(2026, 8, 1), date(2026, 8, 31)
    )["maintien"]
    assert mois["garantie_nette"]["reduction"] == round(
        sum(m["garantie_nette"]["reduction"] for m in seuls), 2
    ) > 0
    assert mois["garantie_nette"]["ijss_deduites"] == mois["ijss_deduites"]
