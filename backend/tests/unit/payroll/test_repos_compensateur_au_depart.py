"""Contrepartie obligatoire en repos non prise au départ (C. trav. D3121-23).

Elle est due en argent. Martine ne la paie pas seule : le bulletin de sortie
l'alerte, le reçu ne peut plus écrire « Néant » (registre R-246).
"""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.bulletin import alertes_des_compteurs_de_conges
from app.modules.payroll.solde_de_tout_compte.common.bulletin_de_sortie import (
    alertes_du_recu,
    section_autres_regularisations,
)

pytestmark = pytest.mark.unit

CODE = "repos_compensateur_du_au_depart"


def _soldes(solde: float) -> dict:
    return {"repos_compensateur": {"acquis": solde + 7.0, "pris": 7.0, "solde": solde}}


def test_au_depart_le_solde_appelle_une_alerte():
    (alerte,) = [
        a for a in alertes_des_compteurs_de_conges(_soldes(12.5), bulletin_de_sortie=True)
        if a["code"] == CODE
    ]
    assert "12,5 h" in alerte["message"]
    assert "D3121-23" in alerte["message"]
    assert "page Primes" in alerte["message"]
    assert alerte["heures"] == 12.5
    assert alerte["critique"] is False


@pytest.mark.parametrize(
    "soldes,sortie",
    [(_soldes(12.5), False), (_soldes(0.0), True), (_soldes(-3.0), True), ({}, True)],
)
def test_pas_d_alerte(soldes, sortie):
    assert not [
        a for a in alertes_des_compteurs_de_conges(soldes, bulletin_de_sortie=sortie)
        if a["code"] == CODE
    ]


def _bulletin(*codes: str) -> dict:
    return {
        "alertes_baremes": [
            {"code": code, "message": f"message {code}", **({"heures": 12.5} if code == CODE else {})}
            for code in codes
        ]
    }


def test_le_recu_reprend_l_alerte():
    assert alertes_du_recu(_bulletin(CODE)) == [f"message {CODE}"]


def test_le_recu_n_ecrit_plus_neant_quand_un_solde_reste():
    section = section_autres_regularisations(_bulletin(CODE, "rtt_jtc_non_payes_au_depart"))
    lignes = {r["label"]: r for r in section["rows"]}
    assert "RTT / repos compensateurs" not in lignes
    assert lignes["RTT"]["detail"] == "Néant"
    ligne = lignes["Repos compensateur obligatoire non pris"]
    assert "12,5 h" in ligne["detail"]
    assert "Néant" not in ligne["detail"]
    assert ligne["montant"] is None


def test_le_recu_sans_solde_de_repos_ne_change_pas():
    section = section_autres_regularisations(_bulletin("rtt_jtc_non_payes_au_depart"))
    assert [(r["label"], r["detail"]) for r in section["rows"]] == [
        ("RTT / repos compensateurs", "Néant")
    ]


def test_le_recu_sans_alerte_n_a_pas_de_section():
    assert section_autres_regularisations(_bulletin()) is None
