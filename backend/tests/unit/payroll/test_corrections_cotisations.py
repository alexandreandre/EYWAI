"""Une cotisation corrigée à la naissance de sa ligne : la ligne, le total salarial
et ce qui se calcule ensuite sur les lignes restent d'accord (spec § 5)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.modules.payroll.engine import calcul_net
from app.modules.payroll.engine.calcul_cotisations import calculer_cotisations
from app.modules.payroll.engine.codes_des_lignes import BLOC_COTISATIONS, Numerotation
from app.modules.payroll.engine.corrections_manuelles import CorrectionDeLigne, JournalDesCorrections

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit


def _cotisations(*corrections, brut=2500.0, hs=82.42, heures_hs=4.0, taux_reduction_hs=None):
    contexte = build_test_contexte()
    contexte.year, contexte.month = 2026, 4
    if taux_reduction_hs is not None:
        # Le barème de test porte une réduction salariale des heures sup nulle.
        contexte.baremes.setdefault("heures_supp", {})["reduction_salariale"] = {
            "taux_reduction": {"plafond_legal": taux_reduction_hs}
        }
    if corrections:
        contexte.corrections_du_mois = JournalDesCorrections(list(corrections))
    return calculer_cotisations(contexte, brut, hs, heures_hs)


def _par_code(lignes):
    numeros = Numerotation()
    return {numeros.code(BLOC_COTISATIONS, l): l for l in lignes}


def _c(code, libelle, saisie_id="s1", **champs):
    return CorrectionDeLigne(ligne=code, libelle=libelle, motif="Test", saisie_id=saisie_id, **champs)


def test_sans_correction_les_cotisations_sont_identiques():
    lignes, total = _cotisations()
    contexte = build_test_contexte()
    contexte.year, contexte.month = 2026, 4
    contexte.corrections_du_mois = JournalDesCorrections([])
    assert calculer_cotisations(contexte, 2500.0, 82.42, 4.0) == (lignes, total)
    assert type(lignes) is list


def test_une_cotisation_corrigee_par_sa_base_fait_suivre_le_total_salarial():
    reference, total0 = _cotisations()
    vp0 = _par_code(reference)["cotisation:vieillesse_plafonnee"]
    lignes, total = _cotisations(_c("cotisation:vieillesse_plafonnee", vp0["libelle"], base=2600.0))
    vp = _par_code(lignes)["cotisation:vieillesse_plafonnee"]
    assert vp["montant_salarial"] == round(2600.0 * vp0["taux_salarial"], 2)
    assert vp["montant_patronal"] == round(2600.0 * vp0["taux_patronal"], 2)
    assert vp["valeur_calculee"]["montant_salarial"] == vp0["montant_salarial"]
    assert total == pytest.approx(total0 + vp["montant_salarial"] - vp0["montant_salarial"], abs=0.005)
    assert total == pytest.approx(sum(l.get("montant_salarial") or 0.0 for l in lignes), abs=0.005)


def test_une_ligne_en_double_se_corrige_par_son_numero():
    reference, _ = _cotisations()
    codes = list(_par_code(reference))
    assert "cotisation:vieillesse_deplafonnee#2" in codes  # le barème de test la porte deux fois
    lignes, _ = _cotisations(_c("cotisation:vieillesse_deplafonnee#2", "Vieillesse déplafonnée", base=2600.0))
    doublons = [l for l in lignes if l.get("coti_id") == "vieillesse_deplafonnee"]
    assert [l["base"] for l in doublons] == [2500.0, 2600.0]


def test_le_plafond_de_la_reduction_des_heures_sup_lit_les_lignes_corrigees():
    """Le plafond (les cotisations salariales dues) se lit sur les lignes corrigées."""
    lignes, _ = _cotisations(
        _c("cotisation:csg_deductible:csg-deductible", "CSG déductible", base=0.0),
        _c("cotisation:vieillesse_plafonnee", "Vieillesse plafonnée", base=0.0, saisie_id="s2"),
        hs=2000.0,
        heures_hs=100.0,
        # Un taux fort : le plafond joue à coup sûr, et seulement s'il lit les lignes corrigées.
        taux_reduction_hs=0.5,
    )
    par_code = _par_code(lignes)
    assert par_code["cotisation:csg_deductible:csg-deductible"]["montant_salarial"] == 0.0
    dues = round(
        sum(l.get("montant_salarial") or 0.0 for l in lignes if l.get("coti_id") != "reduction_hs_salariale"), 2
    )
    assert dues < round(2000.0 * 0.5, 2)  # le plafond joue
    assert par_code["cotisation:reduction_hs_salariale"]["montant_salarial"] == pytest.approx(-dues, abs=0.005)


def _mutuelle(patronal, **extra):
    return {"coti_id": "mutuelle", "libelle": "Mutuelle", "montant_salarial": 20.0, "montant_patronal": patronal, **extra}


def test_sans_correction_la_mutuelle_reintegree_est_inchangee():
    with patch.object(calcul_net, "_get_part_patronale_mutuelle", return_value=30.0):
        assert calcul_net._part_patronale_mutuelle_du_bulletin(None, [_mutuelle(30.0)]) == 30.0


def test_une_mutuelle_corrigee_reintegre_son_ecart_au_net_imposable():
    corrigee = _mutuelle(36.0, valeur_calculee={"montant_patronal": 30.0}, correction={"saisie_id": "s1"})
    with patch.object(calcul_net, "_get_part_patronale_mutuelle", return_value=30.0):
        assert calcul_net._part_patronale_mutuelle_du_bulletin(None, [corrigee]) == 36.0
    baissee = _mutuelle(25.0, valeur_calculee={"montant_patronal": 30.0}, correction={"saisie_id": "s1"})
    with patch.object(calcul_net, "_get_part_patronale_mutuelle", return_value=30.0):
        assert calcul_net._part_patronale_mutuelle_du_bulletin(None, [baissee]) == 25.0
