"""Un événement va sur le bulletin du mois ou sur celui des variables."""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.calcul_brut import (
    TYPES_RATTACHES_AUX_VARIABLES,
    evenements_de_la_periode,
)

pytestmark = pytest.mark.unit

MOIS = (date(2026, 7, 1), date(2026, 7, 31))
VARIABLES = (date(2026, 6, 22), date(2026, 7, 26))


def _ev(jour: str, type_ev: str, heures: float = 7.0) -> dict:
    return {"date_complete": jour, "type": type_ev, "heures": heures}


def test_les_heures_sup_suivent_la_fenetre_des_variables():
    """Une HS du 24/06 est hors du mois de juillet mais dans la fenêtre."""
    evenements = [_ev("2026-06-24", "travail_hs25", 2.0)]
    assert evenements_de_la_periode(evenements, MOIS, VARIABLES) == evenements


def test_un_conge_du_30_juillet_reste_sur_juillet():
    """Hors fenêtre (qui s'arrête au 26) mais dans le mois : il compte."""
    evenements = [_ev("2026-07-30", "conges_payes")]
    assert evenements_de_la_periode(evenements, MOIS, VARIABLES) == evenements


def test_un_conge_du_24_juin_ne_compte_pas_en_juillet():
    """Dans la fenêtre mais dans le mois de juin : il a été payé en juin."""
    evenements = [_ev("2026-06-24", "conges_payes")]
    assert evenements_de_la_periode(evenements, MOIS, VARIABLES) == []


def test_une_heure_sup_du_30_juillet_bascule_sur_aout():
    """Hors fenêtre : elle sera comptée sur la fenêtre du mois suivant."""
    evenements = [_ev("2026-07-30", "travail_hs25", 3.0)]
    assert evenements_de_la_periode(evenements, MOIS, VARIABLES) == []


def test_sans_fenetre_variables_le_comportement_est_inchange():
    """Repli : une seule fenêtre, celle passée en premier argument."""
    evenements = [_ev("2026-07-30", "travail_hs25"), _ev("2026-06-24", "conges_payes")]
    assert evenements_de_la_periode(evenements, MOIS, None) == [evenements[0]]


def test_une_regularisation_anterieure_passe_toujours():
    evenement = _ev("2026-05-12", "absence_non_remuneree")
    evenement["is_regularisation_anterieure"] = True
    assert evenements_de_la_periode([evenement], MOIS, VARIABLES) == [evenement]


def test_le_catalogue_des_types_variables():
    assert TYPES_RATTACHES_AUX_VARIABLES == frozenset({"travail_hs25", "travail_hs50"})
