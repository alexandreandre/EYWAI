"""Reprise Quadra : la base du dixième d'ouverture est la somme des bruts de la période de congés.

Le moteur lit `brut_reference_n_1` comme la somme des bruts depuis le 1er juin et
l'augmente chaque mois. Avec une bascule au 31/08, l'ouverture doit donc porter
juin + juillet + août, pas le seul brut d'août.
"""

from __future__ import annotations

from datetime import date

import pytest

from scripts.backtest.colorplast_lignes_quadra import Bulletin, Ligne
from scripts.reprise_colorplast_import_litteral import _brut_du_mois
from scripts.reprise_colorplast_solde_ouverture import base_du_dixieme

pytestmark = pytest.mark.unit


def _b(brut: float | None) -> Bulletin:
    b = Bulletin(matricule="ESSAI")
    b.lignes = [] if brut is None else [Ligne(None, "SALAIRE BRUT", gain=brut)]
    return b


def test_la_base_additionne_juin_juillet_aout():
    lus = {m: {"A": _b(1000.0 + m)} for m in range(1, 9)}
    base, debut, fin = base_du_dixieme(lus, 2026, 8, "A", _brut_du_mois)
    assert base == 1006.0 + 1007.0 + 1008.0
    assert (debut, fin) == (date(2026, 6, 1), date(2027, 5, 31))


def test_un_mois_d_arret_sans_brut_et_un_brut_negatif_sont_comptes_tels_quels():
    """Brut de juin, régularisation négative en juillet, arrêt complet en août (aucune
    ligne « SALAIRE BRUT ») : l'ancienne ouverture valait 0."""
    lus = {6: {"A": _b(1934.45)}, 7: {"A": _b(-488.36)}, 8: {"A": _b(None)}}
    assert base_du_dixieme(lus, 2026, 8, "A", _brut_du_mois)[0] == 1446.09


def test_un_contrat_ouvert_en_aout_ne_prend_que_ses_propres_bulletins():
    """Deux matricules pour une fiche : la base est celle du contrat qui continue."""
    lus = {
        6: {"CDD": _b(1500.0)},
        7: {"CDD": _b(1600.0)},
        8: {"CDD": _b(1130.51), "APPRENTI": _b(53.18)},
    }
    assert base_du_dixieme(lus, 2026, 8, "APPRENTI", _brut_du_mois)[0] == 53.18


def test_une_bascule_au_30_juin_redonne_le_brut_de_juin():
    lus = {5: {"A": _b(900.0)}, 6: {"A": _b(1200.0)}}
    assert base_du_dixieme(lus, 2026, 6, "A", _brut_du_mois)[0] == 1200.0


def test_une_periode_ouverte_l_annee_precedente_est_refusee():
    """Bascule au 31/03 : la période a commencé le 01/06/2025, sans bulletins 2025."""
    with pytest.raises(SystemExit):
        base_du_dixieme({3: {"A": _b(1000.0)}}, 2026, 3, "A", _brut_du_mois)
