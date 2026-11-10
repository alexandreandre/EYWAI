"""Salaire de base sous le SMIC horaire, et prime soumise réglée non imposable :
le bulletin le signale (contrôle de la paie d'octobre, 10/11/2026)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.payroll.engine.controles_convention import (
    alerte_prime_soumise_imposee,
    controle_taux_sous_smic,
)

pytestmark = pytest.mark.unit


def _contexte(**kw):
    return SimpleNamespace(smic_horaire=12.31, is_alternant=False, is_apprenti=False, **kw)


def _ligne(taux):
    return [{"libelle": "Salaire de base", "quantite": 151.67, "taux": taux, "gain": 1700.0}]


def test_un_taux_sous_le_smic_est_signale():
    alertes = controle_taux_sous_smic(_contexte(), _ligne(11.2085))
    assert [a["code"] for a in alertes] == ["salaire_sous_smic"]
    assert alertes[0]["critique"] is True
    assert "11.21" in alertes[0]["message"] and "12.31" in alertes[0]["message"]


def test_au_smic_rien_n_est_signale():
    assert controle_taux_sous_smic(_contexte(), _ligne(12.31)) == []
    assert controle_taux_sous_smic(_contexte(), _ligne(12.306)) == []


def test_un_alternant_n_est_pas_concerne():
    contexte = SimpleNamespace(smic_horaire=12.31, is_alternant=True, is_apprenti=True)
    assert controle_taux_sous_smic(contexte, _ligne(6.0)) == []


def test_sans_taux_ni_smic_rien_n_est_signale():
    assert controle_taux_sous_smic(_contexte(), [{"libelle": "Salaire de base", "taux": None}]) == []
    assert controle_taux_sous_smic(SimpleNamespace(smic_horaire=0), _ligne(5.0)) == []
    assert controle_taux_sous_smic(_contexte(), [{"libelle": "Prime", "taux": 2.0}]) == []


def test_prime_soumise_reglee_non_imposable():
    alerte = alerte_prime_soumise_imposee("Prime X")
    assert alerte["code"] == "prime_soumise_comptee_imposable"
    assert "Prime X" in alerte["message"]
