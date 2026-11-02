"""Le lien d'une fiche à sa formule de prévoyance ne périme aucun bulletin.

`specificites_paie.prevoyance.formule_id` dit seulement de quelle formule de la
société les lignes ont été copiées (conception du 02/11/2026) : le moteur ne
lit que `lignes_specifiques`. Relier une fiche à sa formule, ou changer de
formule sans changer les lignes, ne doit faire passer aucun bulletin
« À recalculer » ; une ligne qui change compte toujours.
"""

from __future__ import annotations

import copy

import pytest

from tests.unit.payroll.test_empreinte_donnees_dsn import (
    EMPLOYEE,
    EMPREINTE_FICHE_FIGEE,
    EMPREINTE_GLOBALE_FIGEE,
    _globale,
    _partie_fiche,
)

pytestmark = pytest.mark.unit


def _avec_prevoyance(**cles) -> dict:
    salarie = copy.deepcopy(EMPLOYEE)
    salarie["specificites_paie"]["prevoyance"].update(cles)
    return salarie


def test_le_lien_a_une_formule_ne_change_pas_l_empreinte():
    salarie = _avec_prevoyance(formule_id="f1")
    assert _globale(salarie) == EMPREINTE_GLOBALE_FIGEE
    assert _partie_fiche(salarie) == EMPREINTE_FICHE_FIGEE


def test_changer_de_formule_sans_changer_les_lignes_ne_change_rien():
    assert _globale(_avec_prevoyance(formule_id="f1")) == _globale(_avec_prevoyance(formule_id="f2"))


def test_une_ligne_de_prevoyance_change_toujours_l_empreinte():
    ligne = {"id": "p1", "libelle": "Prévoyance", "salarial": 0.005, "patronal": 0.005, "forfait_social": 0.08}
    salarie = _avec_prevoyance(formule_id="f1", lignes_specifiques=[ligne])
    assert _globale(salarie) != EMPREINTE_GLOBALE_FIGEE
    assert _partie_fiche(salarie) != EMPREINTE_FICHE_FIGEE


def test_la_fiche_lue_n_est_pas_modifiee():
    salarie = _avec_prevoyance(formule_id="f1")
    copie = copy.deepcopy(salarie)
    _globale(salarie)
    assert salarie == copie
