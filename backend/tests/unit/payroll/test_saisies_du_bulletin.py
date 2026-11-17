"""Les saisies du mois rangées pour le moteur, une seule fonction (audit du 17/11)."""

from __future__ import annotations

import pytest

from app.modules.payroll.documents.saisies_du_bulletin import entree_de_prime, ranger_les_saisies

pytestmark = pytest.mark.unit


def test_une_prime_garde_son_lien_au_catalogue_et_son_code_d_export():
    entree = entree_de_prime(
        {"id": 7, "name": "Prime objectif", "amount": 300.0, "catalog_prime_id": "prime_objectif", "export_code": "P12"}
    )
    assert entree["prime_id"] == "prime_objectif"
    assert entree["libelle"] == "Prime objectif (P12)"
    assert entree["export_code"] == "P12"
    assert entree["saisie_id"] == "7"


def test_un_panier_du_catalogue_porte_ce_que_lit_son_plafond():
    entree = entree_de_prime(
        {
            "name": "Panier", "amount": 90.0, "catalog_prime_id": "indemnite_panier_repas",
            "payroll_quantity": 12, "quantity_kind": "count", "situation_repas": "sur_lieu_travail",
        }
    )
    assert entree["type"] == "panier"
    assert (entree["quantity"], entree["quantity_kind"], entree["situation_repas"]) == (
        12.0, "count", "sur_lieu_travail",
    )


def test_une_prime_libre_prend_son_nom_en_identifiant():
    assert entree_de_prime({"name": "Prime Exceptionnelle", "amount": 50})["prime_id"] == "prime_exceptionnelle"


def test_une_prime_retiree_n_est_pas_une_ligne():
    saisies = {"primes": []}
    ranger_les_saisies(
        [{"name": "Prime retirée", "amount": 0, "manual_override": True, "description": "Auto: PRIME_X"}],
        saisies,
        {},
    )
    assert saisies["primes"] == []
