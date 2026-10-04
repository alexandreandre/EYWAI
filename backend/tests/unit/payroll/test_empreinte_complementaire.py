"""Empreinte complémentaire : un hash par partie, posé à la génération.

Elle voit ce que l'empreinte d'entrée ne voit pas (mutuelle de la société,
congés, départ, historique de salaire, réglages société hors des champs
suivis) et dit QUELLE partie a changé. Un bulletin d'avant elle n'en a pas :
rien n'est comparé, le déploiement ne périme aucun bulletin.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.domain.empreinte_entrees import (
    CLE_EMPREINTE_COMPLEMENTAIRE,
    MESSAGE_A_RECALCULER,
    empreinte_complementaire_stockee,
    empreinte_partie,
    message_a_recalculer,
    parties_changees,
    poser_empreinte_complementaire,
)

pytestmark = pytest.mark.unit


def test_une_partie_se_hache_sans_dependre_de_l_ordre_des_cles():
    assert empreinte_partie({"a": 1, "b": [1, 2]}) == empreinte_partie({"b": [1, 2], "a": 1})
    assert empreinte_partie({"a": 1}) != empreinte_partie({"a": 2})
    assert len(empreinte_partie(None)) == 64


def test_poser_et_lire_l_empreinte_complementaire_sans_muter_le_bulletin():
    data = {"salaire_brut": 1.0, "parametres": {"empreinte_entrees": "e" * 64}}
    parties = {"mutuelle": "a" * 64, "fiche": "b" * 64}
    pose = poser_empreinte_complementaire(data, parties)
    assert pose["parametres"][CLE_EMPREINTE_COMPLEMENTAIRE] == parties
    assert pose["parametres"]["empreinte_entrees"] == "e" * 64
    assert empreinte_complementaire_stockee(pose) == parties
    assert CLE_EMPREINTE_COMPLEMENTAIRE not in data["parametres"]


def test_un_bulletin_d_avant_n_a_pas_d_empreinte_complementaire():
    assert empreinte_complementaire_stockee({"parametres": {"empreinte_entrees": "e" * 64}}) is None
    assert empreinte_complementaire_stockee({"parametres": {CLE_EMPREINTE_COMPLEMENTAIRE: {}}}) is None
    assert empreinte_complementaire_stockee(None) is None


def test_seules_les_parties_connues_des_deux_cotes_se_comparent():
    stockees = {"mutuelle": "a" * 64, "fiche": "b" * 64, "salaire": "c" * 64}
    actuelles = {"mutuelle": "z" * 64, "fiche": "b" * 64, "depart": "d" * 64}
    assert parties_changees(stockees, actuelles) == ("mutuelle",)
    assert parties_changees(stockees, {**stockees}) == ()


@pytest.mark.parametrize(
    ("partie", "phrase"),
    [
        ("mutuelle", "La mutuelle a changé"),
        ("conges_ajustements", "Un compteur de congés a été ajusté"),
        ("conges_reglages", "Les réglages de congés ont changé"),
        ("depart", "Le départ du salarié a changé"),
        ("salaire", "L'historique de salaire a changé"),
        ("fiche", "La fiche du salarié a changé"),
        ("calendriers", "Le planning a changé"),
        ("absences", "Une absence a changé"),
        ("saisies", "Les variables du mois ont changé"),
        ("reglages_societe", "Un réglage de paie de la société a changé"),
        ("parametres_societe", "Un réglage de paie de la société a changé"),
    ],
)
def test_une_seule_partie_changee_se_dit_simplement(partie, phrase):
    assert message_a_recalculer((partie,)) == (
        f"{phrase} depuis le calcul : recalculez avant de valider."
    )


def test_plusieurs_parties_changees_sont_nommees():
    assert message_a_recalculer(("fiche", "mutuelle")) == (
        "Ont changé depuis le calcul : la fiche du salarié et la mutuelle. "
        "Recalculez avant de valider."
    )
    assert message_a_recalculer(("calendriers", "absences", "saisies")) == (
        "Ont changé depuis le calcul : le planning, les absences et les variables "
        "du mois. Recalculez avant de valider."
    )


def test_deux_reglages_de_la_societe_ne_font_qu_un():
    assert message_a_recalculer(("parametres_societe", "reglages_societe")) == (
        "Un réglage de paie de la société a changé depuis le calcul : "
        "recalculez avant de valider."
    )


def test_sans_partie_connue_le_message_reste_juste():
    """Un bulletin d'avant l'empreinte complémentaire : on ne sait pas quoi."""
    assert message_a_recalculer(None) == MESSAGE_A_RECALCULER
    assert message_a_recalculer(()) == MESSAGE_A_RECALCULER
    assert not MESSAGE_A_RECALCULER.startswith("Le calendrier ou les absences")
    assert "fiche" in MESSAGE_A_RECALCULER
