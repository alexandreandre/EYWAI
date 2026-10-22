"""Restaurer une version revient aussi à ses régularisations."""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.corrections_manuelles import RegularisationCotisation
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
