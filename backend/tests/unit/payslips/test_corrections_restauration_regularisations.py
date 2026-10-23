"""Restaurer une version revient aussi à ses régularisations."""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.codes_des_lignes import BLOC_BRUT
from app.modules.payroll.engine.corrections_manuelles import CorrectionDeLigne, JournalDesCorrections, RegularisationCotisation
from app.modules.payslips.domain.corrections import CorrectionsBulletin, corrections_pour_revenir, resume_des_corrections

pytestmark = pytest.mark.unit


def _bulletin(*regs):
    return {"cotisations_officielles": [{"code": "sante", "lignes": [r.ligne_de_cotisation() for r in regs]}]}


A = RegularisationCotisation(
    coti_id="mutuelle", libelle="Mutuelle", motif="Tarif", montant_patronal=8.3, saisie_id="s1"
)
B = RegularisationCotisation(
    coti_id="mutuelle", libelle="Mutuelle", motif="Autre", montant_patronal=2.0, saisie_id="s2"
)


def test_une_regularisation_ajoutee_depuis_la_version_est_retiree():
    c = corrections_pour_revenir(_bulletin(A, B), _bulletin(A))
    assert c.regularisations_retirees == ("s2",)
    assert c.regularisations_ajoutees == ()


def test_une_regularisation_disparue_depuis_la_version_est_recreee():
    c = corrections_pour_revenir(_bulletin(), _bulletin(A))
    assert [r.motif for r in c.regularisations_ajoutees] == ["Tarif"]
    assert c.regularisations_ajoutees[0].saisie_id is None


def test_le_resume_nomme_la_regularisation():
    texte = resume_des_corrections(
        CorrectionsBulletin(regularisations_ajoutees=(A,), regularisations_retirees=("s2",))
    )
    assert "régularisation « mutuelle » : tarif" in texte.lower()
    assert "1 régularisation retirée" in texte


def _avec_correction(saisie_id, base):
    ligne = {"libelle": "Salaire de base", "quantite": 151.67, "taux": 16.4832, "gain": 2500.0, "perte": None}
    correction = CorrectionDeLigne(ligne="brut:salaire_base", libelle="Salaire de base", motif="Avenant", base=base, saisie_id=saisie_id)
    JournalDesCorrections([correction]).corriger(ligne, BLOC_BRUT, "brut:salaire_base")
    return {"calcul_du_brut": [ligne]}


def test_une_correction_de_ligne_ajoutee_depuis_la_version_est_retiree():
    c = corrections_pour_revenir(_avec_correction("c2", 170.0), {"calcul_du_brut": []})
    assert c.corrections_retirees == ("c2",) and c.corrections_ajoutees == ()


def test_une_correction_de_ligne_disparue_depuis_la_version_est_recreee():
    c = corrections_pour_revenir({"calcul_du_brut": []}, _avec_correction("c1", 160.0))
    assert [x.base for x in c.corrections_ajoutees] == [160.0]
    assert c.corrections_ajoutees[0].saisie_id is None


def test_une_correction_en_attente_de_la_version_revient_aussi():
    cible = {"corrections_en_attente": [{"type": "correction", "ligne": "brut:precarite", "libelle": "Prime de précarité (CDD)",
                                         "motif": "CDD prolongé", "montant": 0.0, "saisie_id": "c3", "raison": "…"}]}
    c = corrections_pour_revenir({}, cible)
    assert [x.ligne for x in c.corrections_ajoutees] == ["brut:precarite"]
