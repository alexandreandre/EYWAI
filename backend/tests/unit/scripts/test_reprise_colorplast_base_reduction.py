"""Reprise Colorplast : l'ouverture repart de la base de réduction de Quadra (R1).

Le « Cumul heures » imprimé par Quadra n'est pas le SMIC qu'il a retenu pour la réduction
(arrêt payé en maintien, entrée en cours de mois). Sans la clé `heures_hors_reduction_generale`,
le premier mois de Martine régularise l'écart : au 30/09, L.C. reprenait 174,92 € et M.G.
234,76 €, M.B. en rendait 67,41 €. Même règle que la reprise Comitech (décision du 17/10/2026).
Salarié anonymisé ; montants construits.
"""

from __future__ import annotations

import pytest

from scripts.backtest.colorplast_lignes_quadra import Bulletin, Ligne
from scripts.verification_rgdu.oracle import Parametres, reduction_cumulee

pytestmark = pytest.mark.unit
P = Parametres()


def _mois(m: int, rg: float, heures_imprimees: float) -> Bulletin:
    b = Bulletin(matricule="ESSAI")
    b.lignes = [Ligne(None, "SALAIRE DE BASE", base=151.67, taux=17.1425, gain=2600.0),
                Ligne(None, "SALAIRE BRUT", gain=2600.0),
                Ligne(None, "EXO., ECRET. ET ALLEG. COTIS", base=rg, montant_pat=rg)]
    b.net = {"net_imposable_cumul": 2028.0 * m, "pas_cumul": 0.0, "net_hs_exo_cumul": 0.0}
    b.droite = {"cumul_bruts": 2600.0 * m, "cumul_heures": heures_imprimees, "plafond": 4005.0}
    b.infos = {"entree": "01/01/2020"}
    b.pages = [1]
    return b


def _lus(heures_smic_par_mois: float, heures_imprimees_par_mois: float) -> dict:
    lus, deja = {}, 0.0
    for m in range(1, 10):
        due = reduction_cumulee(2600.0 * m, round(heures_smic_par_mois * m * 12.02, 2), P)
        lus[m] = {"A": _mois(m, round(-(due - deja), 2), round(heures_imprimees_par_mois * m, 2))}
        deja = due
    return lus


def test_l_ouverture_redonne_la_reduction_de_quadra():
    from scripts.reprise_colorplast_solde_ouverture import construire_le_solde

    # Quadra a retenu 169 h de SMIC par mois de janvier à septembre, mais n'en imprime que 151,67.
    cumuls = construire_le_solde(_lus(169.0, 151.67), 9)["A"]["cumuls"]
    hors = cumuls["heures_hors_reduction_generale"]
    assert hors == pytest.approx(9 * (151.67 - 169.0), abs=0.2)
    base = round((cumuls["heures_remunerees"] - hors) * 12.02, 2)
    assert abs(reduction_cumulee(cumuls["brut_total"], base, P) - abs(cumuls["reduction_generale_patronale"])) < 1.0


def test_des_heures_imprimees_justes_ne_posent_aucune_cle():
    from scripts.reprise_colorplast_solde_ouverture import construire_le_solde

    cumuls = construire_le_solde(_lus(151.67, 151.67), 9)["A"]["cumuls"]
    assert "heures_hors_reduction_generale" not in cumuls


def test_une_reduction_plafonnee_ne_dit_rien_des_heures():
    from scripts.reprise_colorplast_solde_ouverture import construire_le_solde

    lus = _lus(151.67, 151.67)
    for m in range(1, 10):
        lus[m]["A"].lignes[2] = Ligne(None, "EXO., ECRET. ET ALLEG. COTIS", base=-1035.06, montant_pat=-1035.06)
    assert "heures_hors_reduction_generale" not in construire_le_solde(lus, 9)["A"]["cumuls"]
