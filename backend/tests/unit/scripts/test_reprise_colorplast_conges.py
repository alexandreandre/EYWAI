"""Reprise des congés Colorplast au 30/06 : la simulation rejoue le nettoyage en mémoire.

Avant d'écrire quoi que ce soit, le script doit pouvoir dire ce que donneront les
compteurs d'août une fois les doublons annulés et `jours_payes` réaligné sur ce
que le bulletin a payé. Cette partie est pure : elle transforme la liste des
demandes validées sans toucher à la base.
"""

from __future__ import annotations

import pytest

from scripts.reprise_colorplast_conges import appliquer_nettoyage

pytestmark = pytest.mark.unit

DEMANDES = [
    {"id": "aaa", "type": "conge_paye", "selected_days": ["2026-08-03"], "jours_payes": 10.0},
    {"id": "bbb", "type": "conge_paye", "selected_days": ["2026-08-03"], "jours_payes": 12.0},
    {"id": "ccc", "type": "conge_paye", "selected_days": ["2026-07-13"], "jours_payes": 0.5},
]


def test_les_doublons_annules_disparaissent_de_la_liste():
    restantes = appliquer_nettoyage(DEMANDES, doublons={"aaa"}, jours_payes={})

    assert [d["id"] for d in restantes] == ["bbb", "ccc"]


def test_les_jours_payes_sont_realignes_sur_le_bulletin():
    restantes = appliquer_nettoyage(DEMANDES, doublons=set(), jours_payes={"ccc": 1.0})

    assert {d["id"]: d["jours_payes"] for d in restantes} == {
        "aaa": 10.0, "bbb": 12.0, "ccc": 1.0,
    }


def test_la_liste_lue_en_base_n_est_pas_modifiee_en_place():
    appliquer_nettoyage(DEMANDES, doublons={"aaa"}, jours_payes={"ccc": 1.0})

    assert len(DEMANDES) == 3
    assert DEMANDES[2]["jours_payes"] == 0.5
