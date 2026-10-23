"""Quels bulletins ont leur ligne attendue au suivi IJSS.

Sans subrogation, le moteur reprend les IJSS estimées dans `ijss_subrogees`
(engine/bulletin.py) : un arrêt indemnisé a donc déjà sa ligne. Une déduction
d'IJSS du maintien suffit aussi : le vrai montant peut y être saisi, puis
appliqué au bulletin.
"""

from __future__ import annotations

import pytest

from app.modules.ijss_tracking.application.service import bulletin_attend_des_ijss

pytestmark = pytest.mark.unit


def test_un_bulletin_subroge_a_sa_ligne():
    assert bulletin_attend_des_ijss({"synthese_net": {"subrogation_active": True}})


def test_un_bulletin_non_subroge_avec_ijss_deduites_a_sa_ligne():
    # Forme posée par le moteur : ijss_subrogees reprend les IJSS estimées.
    pdata = {
        "synthese_net": {"subrogation_active": False, "ijss_subrogees": 534.25},
        "bloc_maintien": {"maintien": {"ijss_deduites": 369.86, "ijss_deduites_source": "estimees"}},
    }
    assert bulletin_attend_des_ijss(pdata)
    pdata["synthese_net"].pop("ijss_subrogees")
    assert bulletin_attend_des_ijss(pdata)


def test_un_bulletin_sans_ijss_n_a_pas_de_ligne():
    assert not bulletin_attend_des_ijss({"synthese_net": {"subrogation_active": False}})
    assert not bulletin_attend_des_ijss({})
