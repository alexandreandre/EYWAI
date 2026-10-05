"""Les données de la DSN seule ne périment pas un bulletin.

`specificites_paie.affiliations_psc` et `specificites_paie.dsn_reprise` ne sont
lues que par l'export et l'import DSN : leur changement ne doit pas faire
apparaître « À recalculer ». Tout le reste de la fiche compte toujours, et une
fiche sans ces deux clés garde exactement l'empreinte d'avant — sinon tous les
bulletins déjà calculés passeraient « À recalculer » à tort.
"""

from __future__ import annotations

import copy

import pytest

from app.modules.payroll.application.empreinte_entrees_service import (
    empreinte_des_lectures,
    empreintes_des_parties,
    entrees_depuis_lectures,
)

pytestmark = pytest.mark.unit

EMPLOYEE = {
    "id": "e1",
    "salaire_de_base": {"valeur": 2100},
    "duree_hebdomadaire": 35,
    "statut": "Non-Cadre",
    "is_forfait_jour": False,
    "hire_date": "2025-03-03",
    "contract_type": "CDD",
    "contract_end_date": "2026-12-31",
    "classification_conventionnelle": {"pcs": "674a", "coefficient": 720},
    "specificites_paie": {
        "mutuelle": {"adhesion": True, "mutuelle_type_ids": ["m1"]},
        "prevoyance": {"adhesion": True},
        "prelevement_a_la_source": {"taux": 2.5},
    },
}
COMPANY = {"id": "c1", "idcc": "292", "settings": {}}
CALENDRIERS = {
    (2026, 4): {"planned_calendar": {"calendrier_prevu": []}, "actual_hours": {"calendrier_reel": []}},
    (2026, 5): {
        "planned_calendar": {"calendrier_prevu": [{"jour": 12, "type": "travail", "heures": 7}]},
        "actual_hours": {"calendrier_reel": [{"jour": 12, "type": "travail", "heures": 7}]},
    },
    (2026, 6): {"planned_calendar": {"calendrier_prevu": []}, "actual_hours": {"calendrier_reel": []}},
}

#: Calculées sur ce code AVANT l'exclusion des deux clés : une fiche qui ne les
#: porte pas doit les retrouver à l'identique.
EMPREINTE_GLOBALE_FIGEE = "f4c00e04bd1e65a9ac439ea3cd156234c8d26e74a89e981dab5675f61b665c76"
EMPREINTE_FICHE_FIGEE = "c830b93e0fa8cbacfd398c53b23a40e33f96e7dc909d9ace47a6fad8a340939a"

AFFILIATIONS = [
    {"id_affiliation": "1", "id_contrat": "1", "option": "OPT1", "population": "02"},
    {"id_affiliation": "2", "id_contrat": "2", "option": "ISO", "population": "00"},
]
REPRISE = {"motif_recours": "02", "pas_type": "01", "pas_identifiant": "123456789"}


def _avec_specificites(**cles) -> dict:
    salarie = copy.deepcopy(EMPLOYEE)
    salarie["specificites_paie"].update(cles)
    return salarie


def _kwargs(employee: dict) -> dict:
    return dict(
        year=2026,
        month=5,
        calendriers=CALENDRIERS,
        absences=[],
        saisies=[],
        employee=employee,
        company=COMPANY,
        notes_de_frais=[],
        fenetre_variables={"debut": "2026-05-01", "fin": "2026-05-31"},
    )


def _globale(employee: dict) -> str:
    return empreinte_des_lectures(**_kwargs(employee))


def _partie_fiche(employee: dict) -> str:
    return empreintes_des_parties(entrees_depuis_lectures(**_kwargs(employee)), None)["fiche"]


def test_une_fiche_sans_donnees_dsn_garde_l_empreinte_d_avant():
    assert _globale(EMPLOYEE) == EMPREINTE_GLOBALE_FIGEE
    assert _partie_fiche(EMPLOYEE) == EMPREINTE_FICHE_FIGEE


@pytest.mark.parametrize(
    "cles",
    [
        {"affiliations_psc": AFFILIATIONS},
        {"dsn_reprise": REPRISE},
        {"affiliations_psc": AFFILIATIONS, "dsn_reprise": REPRISE},
    ],
    ids=["affiliations", "reprise", "les-deux"],
)
def test_les_donnees_dsn_ne_changent_pas_l_empreinte(cles):
    salarie = _avec_specificites(**cles)
    assert _globale(salarie) == EMPREINTE_GLOBALE_FIGEE
    assert _partie_fiche(salarie) == EMPREINTE_FICHE_FIGEE


def test_changer_les_donnees_dsn_ne_change_pas_l_empreinte():
    avant = _avec_specificites(affiliations_psc=AFFILIATIONS, dsn_reprise=REPRISE)
    apres = _avec_specificites(
        affiliations_psc=AFFILIATIONS[:1], dsn_reprise={**REPRISE, "motif_recours": "01"}
    )
    assert _globale(avant) == _globale(apres)
    assert _partie_fiche(avant) == _partie_fiche(apres)


def test_la_mutuelle_change_toujours_l_empreinte():
    salarie = _avec_specificites(
        mutuelle={"adhesion": True, "mutuelle_type_ids": ["m2"]},
        affiliations_psc=AFFILIATIONS,
    )
    assert _globale(salarie) != EMPREINTE_GLOBALE_FIGEE
    assert _partie_fiche(salarie) != EMPREINTE_FICHE_FIGEE


def test_une_autre_cle_des_specificites_change_toujours_l_empreinte():
    salarie = _avec_specificites(prelevement_a_la_source={"taux": 3.1})
    assert _globale(salarie) != EMPREINTE_GLOBALE_FIGEE
    assert _partie_fiche(salarie) != EMPREINTE_FICHE_FIGEE


def test_la_fiche_lue_n_est_pas_modifiee():
    salarie = _avec_specificites(affiliations_psc=AFFILIATIONS, dsn_reprise=REPRISE)
    copie = copy.deepcopy(salarie)
    _globale(salarie)
    assert salarie == copie
