"""Corriger une ligne depuis le bulletin : la requête, la vérification, l'écriture, la lecture."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from app.modules.payroll.engine.corrections_manuelles import CorrectionDeLigne
from app.modules.payslips.application import corrections as mod
from app.modules.payslips.application import lignes_corrigeables as lecture
from app.modules.payslips.application.dto import CorrigerBulletinInput, PayslipBadRequestError
from app.modules.payslips.domain.corrections import CorrectionsBulletin, refus_des_corrections, resume_des_corrections
from app.modules.payslips.schemas.requests import PayslipEditRequest
from app.modules.payslips.schemas.responses import LignesCorrigeablesResponse
from tests.unit.payslips.test_corrections import BULLETIN, FauxClient

pytestmark = pytest.mark.unit

SALAIRE = {"libelle": "Salaire de base", "quantite": 151.67, "taux": 16.4832, "gain": 2500.0, "perte": None}
DONNEES = {
    "salaire_brut": 2500.0,
    "calcul_du_brut": [SALAIRE],
    "cotisations_officielles": [{"code": "sante", "lignes": [
        {"coti_id": "allocations_familiales", "libelle": "Allocations familiales", "base": 2500.0,
         "taux_salarial": None, "taux_patronal": 0.0525, "montant_salarial": 0.0, "montant_patronal": 131.25},
    ]}],
}
AJOUT = {"ligne": "brut:salaire_base", "libelle": "Salaire de base", "motif": "Avenant", "base": 160.0}


def _c(**champs):
    return CorrectionDeLigne(**{**AJOUT, **champs})


def test_la_requete_refuse_une_correction_sans_motif_ou_ambigue():
    with pytest.raises(ValidationError):
        PayslipEditRequest(corrections={"corrections_ajoutees": [{**AJOUT, "motif": ""}]})
    with pytest.raises(ValidationError):
        PayslipEditRequest(corrections={"corrections_ajoutees": [{**AJOUT, "montant": 2600.0}]})


def test_la_requete_donne_les_corrections_au_domaine():
    requete = PayslipEditRequest(corrections={"corrections_ajoutees": [AJOUT], "corrections_retirees": ["c9", "c9"]})
    domaine = requete.corrections.vers_domaine()
    assert domaine.corrections_ajoutees == (_c(),)
    assert domaine.corrections_retirees == ("c9",)
    assert domaine.change_des_variables


@pytest.mark.parametrize(
    "correction, retirees, donnees, morceau",
    [
        (_c(ligne="brut:precarite", libelle="Prime de précarité (CDD)", base=None, montant=1.0), (), DONNEES, "n'est plus sur le bulletin"),
        (_c(base=None, montant=2600.0), (), DONNEES, "se corrige par sa base ou son taux"),
        (_c(ligne="cotisation:allocations_familiales", libelle="Allocations familiales", base=None, taux_salarial=0.01), (), DONNEES, "n'a pas de taux salarial"),
        (_c(), (), {**DONNEES, "calcul_du_brut": [{**SALAIRE, "correction": {"saisie_id": "c1"}}]}, "déjà corrigée"),
    ],
)
def test_une_correction_qui_ne_tient_pas_sur_le_bulletin_est_refusee(correction, retirees, donnees, morceau):
    refus = refus_des_corrections(CorrectionsBulletin(corrections_ajoutees=(correction,), corrections_retirees=retirees), donnees)
    assert refus is not None and morceau in refus


def test_corriger_a_nouveau_une_ligne_retire_l_ancienne_correction_dans_le_meme_enregistrement():
    donnees = {**DONNEES, "calcul_du_brut": [{**SALAIRE, "correction": {"saisie_id": "c1"}}]}
    corrections = CorrectionsBulletin(corrections_ajoutees=(_c(),), corrections_retirees=("c1",))
    assert refus_des_corrections(corrections, donnees) is None
    assert refus_des_corrections(CorrectionsBulletin(corrections_ajoutees=(_c(), _c(base=170.0))), DONNEES) is not None


def test_le_resume_nomme_la_ligne_corrigee():
    texte = resume_des_corrections(CorrectionsBulletin(corrections_ajoutees=(_c(),), corrections_retirees=("c9",)))
    assert "ligne « salaire de base » corrigée : avenant" in texte.lower()
    assert "1 correction retirée" in texte


@pytest.fixture
def base():
    client = FauxClient()
    etat = {"bulletin": {**BULLETIN, "payslip_data": DONNEES}}
    with (
        patch.object(mod, "supabase", client),
        patch.object(mod, "_lire_bulletin", side_effect=lambda _id: dict(etat["bulletin"])),
        patch.object(mod, "_relire_en_entier", side_effect=lambda _id: dict(etat["bulletin"])),
        patch.object(mod, "_refuser_si_importe"),
        patch.object(mod, "verifier_appartenance"),
        patch.object(mod, "salarie_generable"),
        patch.object(mod, "reimprimer_bulletin"),
        patch.object(mod, "generate_payslip") as generer,
    ):
        generer.return_value = MagicMock(status="success")
        client.generer = generer
        yield client


def _corriger(corrections, **kwargs):
    return mod.corriger_bulletin(
        CorrigerBulletinInput(payslip_id="ps-1", corrections=corrections, current_user_id="rh-1", current_user_name="RH", **kwargs)
    )


def test_corriger_une_ligne_ecrit_une_saisie_du_mois_puis_recalcule(base):
    _corriger(CorrectionsBulletin(corrections_ajoutees=(_c(),)))
    saisie = base.de("monthly_inputs", "insert")[0][2][0]
    assert saisie["correction_ligne"] == {**_c().charge_utile()}
    assert saisie["employee_id"] == "emp-1" and saisie["month"] == 8
    assert base.generer.called


def test_une_correction_refusee_n_ecrit_rien(base):
    with pytest.raises(PayslipBadRequestError):
        _corriger(CorrectionsBulletin(corrections_ajoutees=(_c(base=None, montant=2600.0),)))
    assert base.ecritures == [] and not base.generer.called


def test_retirer_une_correction_supprime_la_seule_saisie_du_bulletin(base):
    _corriger(CorrectionsBulletin(corrections_retirees=("c9",)))
    filtres = dict(base.de("monthly_inputs", "delete")[0][3])
    assert filtres["id"] == ("c9",) and filtres["employee_id"] == "emp-1" and filtres["month"] == 8


def test_la_restauration_ne_verifie_pas_les_lignes(base):
    _corriger(CorrectionsBulletin(corrections_ajoutees=(_c(ligne="brut:precarite", libelle="Prime de précarité (CDD)", base=None, montant=1.0),)), verifier_les_lignes=False)
    assert base.de("monthly_inputs", "insert")


def test_la_lecture_rend_les_lignes_et_les_corrections_en_attente():
    reponse = MagicMock(data={"payslip_data": {**DONNEES, "corrections_en_attente": [
        {**_c(ligne="brut:precarite", libelle="Prime de précarité (CDD)", base=None, montant=1.0).trace(), "saisie_id": "c3", "raison": "Ligne disparue."}
    ]}})
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = reponse
    with patch.object(lecture, "supabase", client):
        lu = lecture.lire_lignes_corrigeables("ps-1")
    modele = LignesCorrigeablesResponse(**lu)
    assert [l.code for l in modele.lignes] == ["brut:salaire_base", "cotisation:allocations_familiales"]
    assert modele.lignes[0].mode == "base_ou_taux"
    assert modele.en_attente[0].saisie_id == "c3" and modele.en_attente[0].raison == "Ligne disparue."
