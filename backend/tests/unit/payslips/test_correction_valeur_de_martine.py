"""Une correction garde ce que Martine calculait quand elle a été posée (R-185).

La correction porte une valeur absolue et se rejoue. Si le planning change
ensuite, Martine calcule autre chose, la ligne reste forcée, et rien ne le
disait. On note la valeur de Martine à la correction : si elle a bougé au
recalcul, le bulletin le dit, sans rien bloquer et sans changer un montant.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.payroll.engine.corrections_du_bulletin import lignes_corrigeables
from app.modules.payroll.engine.corrections_manuelles import CorrectionDeLigne, JournalDesCorrections
from app.modules.payslips.application import corrections as mod
from app.modules.payslips.application.dto import CorrigerBulletinInput
from app.modules.payslips.domain.anomalies_bulletin import anomalies_du_bulletin, regles_acquittables
from app.modules.payslips.domain.coherence import raisons_de_ne_pas_valider
from app.modules.payslips.domain.corrections import CorrectionsBulletin, avec_la_valeur_de_martine
from tests.unit.payslips.test_corrections import BULLETIN, FauxClient

pytestmark = pytest.mark.unit

SALAIRE = {"libelle": "Salaire de base", "quantite": 151.67, "taux": 16.0, "gain": 2426.72, "perte": None}
DONNEES = {"salaire_brut": 2426.72, "calcul_du_brut": [SALAIRE]}


def _correction(**champs):
    return CorrectionDeLigne(**{"ligne": "brut:salaire_base", "libelle": "Salaire de base", "motif": "Avenant", "base": 160.0, "saisie_id": "s1", **champs})


def test_la_valeur_de_martine_est_notee_a_la_correction():
    corrections = avec_la_valeur_de_martine(CorrectionsBulletin(corrections_ajoutees=(_correction(),)), DONNEES)
    assert corrections.corrections_ajoutees[0].martine_a_la_correction == {
        "quantite": 151.67, "taux": 16.0, "gain": 2426.72, "perte": None,
    }


def test_la_valeur_notee_voyage_dans_la_saisie_et_revient():
    corrigee = avec_la_valeur_de_martine(CorrectionsBulletin(corrections_ajoutees=(_correction(),)), DONNEES).corrections_ajoutees[0]
    saisie = corrigee.saisie_du_mois({"employee_id": "e"})
    relue = CorrectionDeLigne.depuis(saisie["correction_ligne"], saisie_id="s1")
    assert relue.martine_a_la_correction == corrigee.martine_a_la_correction


def test_une_correction_sans_valeur_notee_ne_change_pas_la_saisie():
    assert "martine_a_la_correction" not in _correction().charge_utile()


def test_une_ligne_deja_corrigee_note_la_valeur_de_martine_pas_la_correction():
    deja = {**SALAIRE, "quantite": 170.0, "gain": 2720.0, "correction": {"saisie_id": "s0"}, "valeur_calculee": {"quantite": 151.67, "taux": 16.0, "gain": 2426.72, "perte": None}}
    corrections = avec_la_valeur_de_martine(
        CorrectionsBulletin(corrections_ajoutees=(_correction(),), corrections_retirees=("s0",)),
        {"calcul_du_brut": [deja]},
    )
    assert corrections.corrections_ajoutees[0].martine_a_la_correction["gain"] == 2426.72


def _recalcul(quantite_de_martine, correction=None):
    """Martine recalcule la ligne après un changement de source, la correction se rejoue."""
    correction = correction or avec_la_valeur_de_martine(CorrectionsBulletin(corrections_ajoutees=(_correction(),)), DONNEES).corrections_ajoutees[0]
    ligne = {**SALAIRE, "quantite": quantite_de_martine, "gain": round(quantite_de_martine * 16.0, 2)}
    JournalDesCorrections([correction]).corriger(ligne, "brut", "brut:salaire_base")
    return ligne


def test_rien_a_dire_quand_martine_calcule_comme_avant():
    ligne = _recalcul(151.67)
    assert lignes_corrigeables({"calcul_du_brut": [ligne]})[0].alerte is None


def test_l_alerte_dit_quand_martine_a_change_d_avis():
    ligne = _recalcul(140.0)
    assert ligne["quantite"] == 160.0, "la correction reste appliquée"
    alerte = lignes_corrigeables({"calcul_du_brut": [ligne]})[0].alerte
    assert alerte is not None
    assert "2 240,00" in alerte and "2 426,72" in alerte
    assert "reste appliquée" in alerte


def test_seul_ce_que_la_correction_touche_compte():
    """Une correction de taux ne s'alarme pas que la quantité ait bougé."""
    correction = avec_la_valeur_de_martine(
        CorrectionsBulletin(corrections_ajoutees=(_correction(base=None, taux=18.0),)), DONNEES
    ).corrections_ajoutees[0]
    ligne = _recalcul(140.0, correction)
    assert lignes_corrigeables({"calcul_du_brut": [ligne]})[0].alerte is None


def test_une_correction_d_avant_sans_valeur_notee_ne_dit_rien():
    ligne = _recalcul(140.0, _correction())
    assert lignes_corrigeables({"calcul_du_brut": [ligne]})[0].alerte is None


def test_le_taux_d_impot_est_compare_sur_son_taux():
    impot = {
        "base": 2000.0, "taux": 8.0, "montant": 160.0,
        "correction": {"ligne": "impot", "libelle": "Impôt", "motif": "x", "taux": 8.0, "saisie_id": "s",
                       "martine_a_la_correction": {"taux": 5.0, "montant": 100.0}},
        "valeur_calculee": {"taux": 5.0, "montant": 110.0},
    }
    data = {"synthese_net": {"impot_prelevement_a_la_source": impot}}
    assert lignes_corrigeables(data)[0].alerte is None, "seule la base a bougé, pas le taux de Martine"
    impot["valeur_calculee"] = {"taux": 6.5, "montant": 130.0}
    assert "6,50" in lignes_corrigeables(data)[0].alerte


def test_la_revue_du_mois_le_signale_sans_bloquer():
    ligne = _recalcul(140.0)
    data = {"salaire_brut": ligne["gain"], "calcul_du_brut": [ligne]}
    alertes = [a for a in anomalies_du_bulletin(data) if a.rule_id == "B05"]
    assert len(alertes) == 1
    assert alertes[0].level == "AVERTISSEMENT"
    assert "B05" in regles_acquittables()
    assert raisons_de_ne_pas_valider(data) == []


def test_la_route_note_la_valeur_avant_d_ecrire():
    client = FauxClient()
    bulletin = {**BULLETIN, "payslip_data": DONNEES}
    with (
        patch.object(mod, "supabase", client),
        patch.object(mod, "_lire_bulletin", side_effect=lambda _id: dict(bulletin)),
        patch.object(mod, "_relire_en_entier", side_effect=lambda _id: dict(bulletin)),
        patch.object(mod, "_refuser_si_importe"),
        patch.object(mod, "verifier_appartenance"),
        patch.object(mod, "salarie_generable"),
        patch.object(mod, "generate_payslip", return_value=MagicMock(status="success")),
    ):
        mod.corriger_bulletin(
            CorrigerBulletinInput(
                payslip_id="ps-1",
                corrections=CorrectionsBulletin(corrections_ajoutees=(_correction(saisie_id=None),)),
                current_user_id="rh-1",
                current_user_name="RH",
            )
        )
    saisie = client.de("monthly_inputs", "insert")[0][2][0]
    assert saisie["correction_ligne"]["martine_a_la_correction"]["gain"] == 2426.72
