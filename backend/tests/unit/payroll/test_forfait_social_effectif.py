"""Forfait social sur la protection sociale complémentaire : la loi, pas la fiche.

CSS L137-15 (Légifrance, lu le 03/11/2026) : « ne sont pas assujettis à cette
contribution les employeurs de moins de onze salariés au titre des contributions
[…] pour le financement de prestations complémentaires de prévoyance ».
CSS L137-16 : taux de 8 % pour ces contributions. L'assiette (parts patronales
santé et prévoyance) est celle déjà vérifiée sur Quadra et Cegid.

Le taux porté par une ligne de la fiche ne décide plus : Quadra le payait sous
11 salariés (MAJI, Zone 404, Colorplast), et des fiches de Mont Blanc ne le
portaient pas alors qu'il est dû.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.calcul_cotisations import calculer_cotisations

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

MUTUELLE = {"adhesion": True, "montant_salarial": 20.0, "montant_patronal": 30.0}
TA = {"id": "ta", "libelle": "Prévoyance TA", "salarial": 0.0, "patronal": 0.01, "base": "brut_plafonne"}
TB = {"id": "tb", "libelle": "Prévoyance TB", "salarial": 0.01, "patronal": 0.01, "base": "tranche_2"}


def _forfaits(statut, effectif, salaire, specificites):
    ctx = build_test_contexte(
        statut=statut, salaire_base=salaire, effectif=effectif, specificites_extra=specificites
    )
    lignes, _ = calculer_cotisations(ctx, salaire, 0.0, 0.0)
    patronal_complementaire = round(
        sum(
            float(l.get("montant_patronal") or 0.0)
            for l in lignes
            if l.get("coti_id") in {"mutuelle", "prevoyance_cadre", "prevoyance_non_cadre"}
        ),
        2,
    )
    return [l for l in lignes if l.get("coti_id") == "forfait_social"], patronal_complementaire


def test_moins_de_11_salaries_aucun_forfait_meme_si_la_ligne_en_porte():
    forfaits, _ = _forfaits(
        "Non-Cadre", 10, 2500.0,
        {"mutuelle": MUTUELLE, "prevoyance": {"adhesion": True, "lignes_specifiques": [{**TA, "forfait_social": 0.08}]}},
    )
    assert forfaits == []


def test_11_salaries_forfait_de_8_pour_cent_meme_si_la_ligne_n_en_porte_pas():
    forfaits, assiette = _forfaits(
        "Non-Cadre", 11, 2500.0,
        {"mutuelle": MUTUELLE, "prevoyance": {"adhesion": True, "lignes_specifiques": [TA]}},
    )
    assert len(forfaits) == 1
    assert forfaits[0]["base"] == assiette == 55.0
    assert forfaits[0]["taux_patronal"] == 0.08
    assert forfaits[0]["montant_patronal"] == 4.4
    assert forfaits[0]["libelle"] == "Forfait social 8% sur prévoyance"


def test_mutuelle_patronale_sans_prevoyance_reste_soumise():
    forfaits, assiette = _forfaits(
        "Non-Cadre", 30, 2500.0, {"mutuelle": MUTUELLE, "prevoyance": {"adhesion": False}}
    )
    assert assiette == 30.0
    assert [f["montant_patronal"] for f in forfaits] == [2.4]


def test_cadre_deux_tranches_un_seul_forfait_au_taux_legal():
    forfaits, assiette = _forfaits(
        "Cadre", 70, 5000.0,
        {"prevoyance": {"adhesion": True, "lignes_specifiques": [{**TA, "forfait_social": 0.2}, TB]}},
    )
    assert len(forfaits) == 1
    assert forfaits[0]["base"] == assiette
    assert forfaits[0]["taux_patronal"] == 0.08


def test_sans_part_patronale_aucun_forfait():
    forfaits, _ = _forfaits("Non-Cadre", 30, 2500.0, {"prevoyance": {"adhesion": False}})
    assert forfaits == []
