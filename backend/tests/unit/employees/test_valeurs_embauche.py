"""La création d'un salarié propose les valeurs de sa société, pas des valeurs génériques."""

from __future__ import annotations

import pytest

from app.modules.employees.domain.valeurs_embauche import valeurs_d_embauche

pytestmark = pytest.mark.unit

ISOLE_NC = {"id": "iso-nc", "statut_categoriel": "non_cadre", "part_salariale_obligatoire": True, "is_active": True}
ISOLE_C = {"id": "iso-c", "statut_categoriel": "cadre", "part_salariale_obligatoire": True, "is_active": True}
FAMILLE = {"id": "famille", "statut_categoriel": "tous", "part_salariale_obligatoire": False, "is_active": True}
GENERIQUE = {"id": "generique", "statut_categoriel": "tous", "part_salariale_obligatoire": True, "is_active": True}
MUTUELLES = [ISOLE_NC, ISOLE_C, FAMILLE, GENERIQUE]


def _salarie(statut="Non-Cadre", coefficient=710, mutuelles=("iso-nc",), status="actif", **extra):
    return {
        "employment_status": status,
        "statut": statut,
        "duree_hebdomadaire": "39.00",
        "collective_agreement_id": "plasturgie",
        "classification_conventionnelle": {"coefficient": coefficient, "classe_emploi": str(coefficient), "groupe_emploi": "C"},
        "specificites_paie": {
            "mutuelle": {"mutuelle_type_ids": list(mutuelles)},
            "prevoyance": {"adhesion": True},
            "titres_restaurant": {"beneficie": True, "nombre_par_mois": 0},
        },
        **extra,
    }


COLORPLAST = [
    _salarie(mutuelles=("iso-nc", "famille")),
    _salarie(mutuelles=("iso-nc", "famille")),
    _salarie(coefficient=750, mutuelles=("iso-nc",)),
    _salarie(coefficient=720, mutuelles=()),
    _salarie(statut="Cadre", coefficient=830, mutuelles=("iso-c", "famille")),
    _salarie(coefficient=999, mutuelles=("generique",), status="parti"),
]


def test_les_valeurs_courantes_de_la_societe():
    v = valeurs_d_embauche(COLORPLAST, MUTUELLES)
    assert v["statut"] == "Non-Cadre" and v["contract_type"] == "CDI"
    assert v["duree_hebdomadaire"] == 39.0
    assert v["collective_agreement_id"] == "plasturgie"
    assert v["classification_conventionnelle"] == {"groupe_emploi": "C", "classe_emploi": 710, "coefficient": 710}
    assert v["prevoyance_adhesion"] is True


def test_la_mutuelle_obligatoire_de_la_categorie_jamais_l_option_famille():
    v = valeurs_d_embauche(COLORPLAST, MUTUELLES)
    assert v["mutuelle_type_ids_par_statut"] == {"Non-Cadre": ["iso-nc"], "Cadre": ["iso-c"]}


def test_des_titres_restaurant_a_zero_ne_valent_pas_un_avantage():
    assert valeurs_d_embauche(COLORPLAST, MUTUELLES)["titres_restaurant_beneficie"] is False


def test_les_salaries_partis_ne_comptent_pas():
    v = valeurs_d_embauche(COLORPLAST, MUTUELLES)
    assert v["classification_conventionnelle"]["coefficient"] != 999


def test_une_societe_vide_ne_propose_rien_d_invente():
    v = valeurs_d_embauche([], [ISOLE_NC, FAMILLE])
    assert v["classification_conventionnelle"] is None
    assert v["duree_hebdomadaire"] is None
    assert v["collective_agreement_id"] is None
    # Une seule mutuelle obligatoire propre à la catégorie : c'est elle.
    assert v["mutuelle_type_ids_par_statut"]["Non-Cadre"] == ["iso-nc"]
    assert v["mutuelle_type_ids_par_statut"]["Cadre"] == []
