"""Panier saisi au mois : l'excédent par panier au-delà du plafond Urssaf est réintégré."""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.frais_professionnels import (
    reintegration_panier_plafonne,
)

pytestmark = pytest.mark.unit

FRAIS = {"repas": {"sur_lieu_travail": 7.5, "hors_locaux_sans_restaurant": 10.4, "hors_locaux_avec_restaurant": 21.4}}


def _ligne(**k):
    base = {"prime_id": "indemnite_panier_repas", "libelle": "Panier repas", "montant": 200.0}
    base.update(k)
    return base


def test_vingt_paniers_de_dix_euros_sur_le_lieu_de_travail():
    ligne = _ligne(quantity=20, quantity_kind="count", situation_repas="sur_lieu_travail")
    assert reintegration_panier_plafonne(ligne, {"frais_pro": FRAIS}.get("frais_pro")) == 50.0


def test_sous_le_plafond_rien_a_reintegrer():
    ligne = _ligne(montant=100.0, quantity=20, quantity_kind="count", situation_repas="sur_lieu_travail")
    assert reintegration_panier_plafonne(ligne, FRAIS) == 0.0


def test_sans_situation_declaree_rien_ne_change():
    assert reintegration_panier_plafonne(_ligne(quantity=20, quantity_kind="count"), FRAIS) == 0.0


def test_une_autre_ligne_que_le_panier_n_est_pas_touchee():
    ligne = {"prime_id": "remb_km", "libelle": "Note de frais : km", "montant": 80.0, "situation_repas": "sur_lieu_travail"}
    assert reintegration_panier_plafonne(ligne, FRAIS) == 0.0
