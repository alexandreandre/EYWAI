"""Périmètre validé par Elsa (11/11/2026), « appliquer la loi ».

R87 — chômage, AGS, APEC et abattement de 1,75 % de la CSG/CRDS : limite de 4
plafonds de la Sécurité sociale (Unédic ; service-public F31409 et F2302 ;
Agirc-Arrco, paramètres 2026), appréciée comme les tranches, sur le cumul de
l'année (régularisation progressive).

R93 — apprentis d'un employeur de moins de 11 salariés : ni formation
professionnelle (Code du travail L6331-1) ni taxe d'apprentissage (L6241-1-1) ;
CDD saisonnier : pas de contribution CPF-CDD (L6331-6).
"""

from __future__ import annotations

import copy

import pytest

from app.modules.payroll.engine.calcul_cotisations import _calculer_assiettes, calculer_cotisations

from .fixtures.baremes_snapshot import baremes_snapshot
from .helpers import build_test_contexte

pytestmark = pytest.mark.unit


def _cumuls(brut: float, pss: float) -> dict:
    return {
        "cumul_brut_agirc_arrco": brut,
        "cumul_pss_agirc_arrco": pss,
        "cumul_tranche_1_appliquee": min(brut, pss),
        "cumul_tranche_2_appliquee": max(0.0, min(brut, 8 * pss) - pss),
    }


def _pss():
    return build_test_contexte().baremes["pss"]["mensuel"]


def test_sous_la_limite_l_assiette_est_le_brut_au_centime():
    ctx = build_test_contexte(cumuls=_cumuls(4 * 3123.45, 4 * _pss()))
    ctx.month = 5
    assiettes = _calculer_assiettes(ctx, 3123.45, 0.0)
    assert assiettes["brut_4_plafonds"] == 3123.45
    assert assiettes["brut_cadre_4_plafonds"] == 3123.45


def test_janvier_au_dela_de_4_plafonds_est_limite():
    pss = _pss()
    ctx = build_test_contexte()
    ctx.month = 1
    assiettes = _calculer_assiettes(ctx, 5 * pss, 0.0)
    assert assiettes["brut_4_plafonds"] == pytest.approx(4 * pss, abs=0.01)


def test_un_gros_mois_reprend_le_plafond_inutilise_de_l_annee():
    # Sortie en mai avec 20 000 € après quatre mois à 3 000 € : le plafond
    # cumulé (5 × 4 PSS) n'est pas atteint, tout le brut est soumis.
    pss = _pss()
    ctx = build_test_contexte(cumuls=_cumuls(4 * 3000.0, 4 * pss))
    ctx.month = 5
    assiettes = _calculer_assiettes(ctx, 20000.0, 0.0)
    assert assiettes["brut_4_plafonds"] == pytest.approx(20000.0, abs=0.01)


def test_cumul_d_avant_negatif_l_assiette_reste_le_brut():
    # Filet du 11/11 (Mont Blanc, mai) : cumul brut de −108,12 € après un mois de
    # retenue ; le mois à 302,78 € doit être soumis en entier, CSG sans excédent.
    ctx = build_test_contexte(cumuls=_cumuls(-108.12, 4 * _pss()))
    ctx.month = 5
    assiettes = _calculer_assiettes(ctx, 302.78, 0.0)
    assert assiettes["brut_4_plafonds"] == 302.78
    assert assiettes["csg_crds_base_normale"] == pytest.approx(302.78 * 0.9825, abs=0.01)


def test_au_dela_du_cumul_seul_le_plafond_restant_est_soumis():
    pss = _pss()
    ctx = build_test_contexte(cumuls=_cumuls(4 * 3000.0, 4 * pss))
    ctx.month = 5
    assiettes = _calculer_assiettes(ctx, 100000.0, 0.0)
    attendu = 5 * 4 * pss - 4 * 3000.0
    assert assiettes["brut_4_plafonds"] == pytest.approx(attendu, abs=0.01)
    # CSG : l'excédent perd l'abattement de 1,75 % (CSS L136-2, I).
    excedent = 100000.0 - attendu
    sans_limite = 100000.0 * 0.9825
    assert assiettes["csg_crds_base_normale"] == pytest.approx(
        sans_limite + excedent * 0.0175, abs=0.02
    )


#: Lignes du barème de la base de test (payroll_config « cotisations », 11/11/2026),
#: absentes de l'instantané des tests.
_EN_PLUS = [
    {"id": "ags", "libelle": "Cotisation AGS", "base": "brut", "salarial": None, "patronal": 0.0025},
    {"id": "assurance_chomage", "libelle": "Assurance Chômage", "base": "brut", "salarial": None,
     "patronal": 0.04},
    {"id": "CFP", "libelle": "Contribution Formation Professionnelle", "base": "brut", "salarial": None,
     "patronal": {"taux_moins_11": 0.0055, "taux_11_et_plus": 0.01}},
    {"id": "taxe_apprentissage", "libelle": "Taxe d'Apprentissage (part principale)", "base": "brut",
     "salarial": None, "patronal": {"taux_metropole": 0.0059, "taux_alsace_moselle": 0.0044}},
    {"id": "taxe_apprentissage_solde", "libelle": "Taxe d'Apprentissage (solde)", "base": "brut",
     "salarial": None, "patronal": {"taux_metropole": 0.0009, "taux_alsace_moselle": 0}},
]


def _baremes():
    b = copy.deepcopy(baremes_snapshot())
    liste = b["cotisations"]["cotisations"]
    deja = {c.get("id") for c in liste}
    liste.extend(c for c in copy.deepcopy(_EN_PLUS) if c["id"] not in deja)
    return b


def _ligne(lignes, coti_id):
    return next((l for l in lignes if l.get("coti_id") == coti_id), None)


def test_chomage_et_ags_portent_sur_l_assiette_limitee():
    pss = _pss()
    ctx = build_test_contexte(baremes=_baremes())
    ctx.month = 1
    lignes, _ = calculer_cotisations(ctx, 5 * pss, 0.0, 0.0)
    for coti_id in ("assurance_chomage", "ags"):
        ligne = _ligne(lignes, coti_id)
        assert ligne is not None, coti_id
        assert ligne["base"] == pytest.approx(4 * pss, abs=0.01), coti_id


def test_apprenti_moins_de_11_ni_formation_ni_taxe_d_apprentissage():
    ctx = build_test_contexte(type_contrat="Apprentissage", effectif=6, date_naissance="2006-03-01", baremes=_baremes())
    lignes, _ = calculer_cotisations(ctx, 1100.0, 0.0, 0.0)
    for coti_id in ("CFP", "taxe_apprentissage", "taxe_apprentissage_solde"):
        assert _ligne(lignes, coti_id) is None, coti_id


def test_apprenti_11_et_plus_paie_la_formation():
    ctx = build_test_contexte(type_contrat="Apprentissage", effectif=30, date_naissance="2006-03-01", baremes=_baremes())
    lignes, _ = calculer_cotisations(ctx, 1100.0, 0.0, 0.0)
    assert _ligne(lignes, "CFP") is not None


def test_non_apprenti_moins_de_11_paie_la_formation():
    ctx = build_test_contexte(effectif=6, baremes=_baremes())
    lignes, _ = calculer_cotisations(ctx, 2500.0, 0.0, 0.0)
    assert _ligne(lignes, "CFP") is not None


_CPF_CDD = {"id": "cpf_cdd", "libelle": "Contribution CPF des titulaires de CDD", "base": "brut",
            "salarial": None, "patronal": 0.01}


def _baremes_cpf():
    b = _baremes()
    liste = b["cotisations"]["cotisations"]
    if not any(c.get("id") == "cpf_cdd" for c in liste):
        liste.append(_CPF_CDD)
    return b


@pytest.mark.parametrize("motif, due", [("03", False), ("04", False), ("01", True), ("", True)])
def test_cpf_cdd_selon_le_motif_de_recours(motif, due):
    ctx = build_test_contexte(type_contrat="CDD", baremes=_baremes_cpf(),
                              specificites_extra={"dsn_reprise": {"motif_recours": motif}})
    lignes, _ = calculer_cotisations(ctx, 2000.0, 0.0, 0.0)
    ligne = _ligne(lignes, "cpf_cdd")
    if due:
        assert ligne is not None and ligne["montant_patronal"] == pytest.approx(20.0, abs=0.01)
    else:
        assert ligne is None
