"""Modifier un congé après création (retour du 10/11 : RTT posé au mauvais jour).

La modification remplace l'ancienne demande par une nouvelle passée par la
création (mêmes contrôles) ; si la nouvelle est refusée, l'ancienne est
rétablie telle quelle.
"""

from __future__ import annotations

import pytest

from app.modules.absences.application.modification import (
    refus_modification,
    remplacer_absence,
)

pytestmark = pytest.mark.unit


def test_un_conge_valide_se_modifie():
    assert refus_modification({"type": "rtt", "status": "validated"}) is None
    assert refus_modification({"type": "conge_paye", "status": "validated"}) is None


def test_un_arret_ne_se_modifie_pas_ici():
    refus = refus_modification({"type": "arret_maladie", "status": "validated"})
    assert refus and "arrêt" in refus


def test_une_demande_annulee_ou_en_attente_ne_se_modifie_pas():
    assert refus_modification({"type": "rtt", "status": "cancelled"})
    assert refus_modification({"type": "rtt", "status": "pending"})


def test_remplacement_annule_puis_cree():
    ordre: list[str] = []
    nouvelle = remplacer_absence(
        annuler=lambda: ordre.append("annuler"),
        creer=lambda: ordre.append("creer") or {"id": "nouvelle"},
        retablir=lambda: ordre.append("retablir"),
    )
    assert nouvelle == {"id": "nouvelle"}
    assert ordre == ["annuler", "creer"]


def test_creation_refusee_l_ancienne_est_retablie_et_le_refus_remonte():
    ordre: list[str] = []

    def creer():
        ordre.append("creer")
        raise ValueError("Le 01/11 est férié.")

    with pytest.raises(ValueError, match="férié"):
        remplacer_absence(
            annuler=lambda: ordre.append("annuler"),
            creer=creer,
            retablir=lambda: ordre.append("retablir"),
        )
    assert ordre == ["annuler", "creer", "retablir"]


def test_retablissement_impossible_le_dit():
    def creer():
        raise ValueError("refus")

    def retablir():
        raise RuntimeError("base indisponible")

    with pytest.raises(RuntimeError, match="n'a pas pu être rétabli"):
        remplacer_absence(annuler=lambda: None, creer=creer, retablir=retablir)
