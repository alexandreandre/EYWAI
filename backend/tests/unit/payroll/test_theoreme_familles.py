"""Chaque famille de gain se corrige, à 0, à une grande valeur et en négatif (R-182).

Au niveau de la ligne : le moteur pose la correction et garde la valeur de
Martine. La couverture est vérifiée : une famille ajoutée à l'inventaire sans
exemple ici fait rougir le test.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.codes_des_lignes import (
    _MOTIFS_DE_GAIN,
    BLOC_BRUT,
    code_de_ligne_de_gain,
    famille_du_code,
    mode_de_correction,
)
from app.modules.payroll.engine.corrections_du_bulletin import lignes_corrigeables
from app.modules.payroll.engine.corrections_manuelles import CorrectionDeLigne, JournalDesCorrections

pytestmark = pytest.mark.unit

#: Un libellé réel par famille d'inventaire.
LIBELLES = {
    "salaire_base": "Salaire de base",
    "hs_structurelles": "Heures suppl. structurelles majorées à 25%",
    "heures_sup": "Heures suppl. majorées à 25%",
    "heures_complementaires": "Heures complémentaires majorées à 10%",
    "absence_entree_sortie": "Absence pour entrée ou sortie",
    "absence_injustifiee": "Absence injustifiée du 12/10/26",
    "absence_non_remuneree": "Absence non rémunérée du 12/10/26",
    "absence_evenement_familial": "Absence événement familial du 12/10/26",
    "absence_ferie_non_paye": "Abs. jour férié non payé du 12/10/26",
    "absence_maladie": "Absence maladie du 12/10/26",
    "reduction_hs_absence": "Heures sup. du contrat non faites (absence)",
    "reduction_hs_evenement_familial": "Heures sup. du contrat non faites (événement familial)",
    "maintien_evenement_familial": "Maintien de salaire (événement familial)",
    "maintien_employeur": "Maintien de salaire employeur",
    "complement_absence_integrale": "Complément retenue absence intégrale du mois",
    "retenue_absence_integrale": "Retenue absence intégrale du mois limitée au salaire mensuel",
    "retenue_absence_mois_complet": "Absence sur tout le mois : retenue ramenée au salaire du mois",
    "lissage_modulation": "Lissage modulation",
    "absence_conges_payes": "Absence congés payés du 12/10/26",
    "indemnite_conges_payes": "Indemnité de congés payés (octobre)",
    "iccp": "Indemnité compensatrice de congés payés",
    "precarite": "Prime de précarité (CDD)",
    "ifm": "Indemnité de fin de mission (intérim)",
    "avantages_en_nature": "Avantages en nature",
    "prime_anciennete": "Prime d'ancienneté 5 ans",
    "rappel_salaire": "Rappel de salaire septembre",
    "reintegration": "Réintégration mutuelle",
    "heures_nuit": "Heures de nuit majorées à 20%",
    "pause_remuneree": "Pause rémunérée (planning)",
}
VALEURS = [0.0, 99999.99, -50.0, 42.5]


def _familles_de_l_inventaire():
    return {famille for famille, _ in _MOTIFS_DE_GAIN}


def test_chaque_famille_de_l_inventaire_a_son_exemple():
    assert set(LIBELLES) == _familles_de_l_inventaire()


@pytest.mark.parametrize("famille", sorted(LIBELLES))
def test_le_libelle_donne_la_famille(famille):
    assert famille_du_code(code_de_ligne_de_gain({"libelle": LIBELLES[famille], "gain": 1.0})) == f"brut:{famille}"


def _poser(ligne, correction):
    journal = JournalDesCorrections([correction])
    journal.corriger(ligne, BLOC_BRUT, correction.ligne)
    return journal


@pytest.mark.parametrize("famille", sorted(LIBELLES))
@pytest.mark.parametrize("valeur", VALEURS)
def test_une_ligne_au_montant_prend_la_valeur(famille, valeur):
    ligne = {"libelle": LIBELLES[famille], "gain": 120.0}
    code = code_de_ligne_de_gain(ligne)
    mode, _ = mode_de_correction(BLOC_BRUT, ligne, code)
    assert mode == "montant"
    journal = _poser(ligne, CorrectionDeLigne(ligne=code, libelle=ligne["libelle"], motif="Essai", montant=valeur, saisie_id="s"))
    assert ligne["gain"] == valeur
    assert ligne["valeur_calculee"]["gain"] == 120.0
    assert journal.en_attente() == []


@pytest.mark.parametrize("famille", sorted(LIBELLES))
@pytest.mark.parametrize("valeur", VALEURS)
def test_une_ligne_quantite_taux_prend_la_base(famille, valeur):
    ligne = {"libelle": LIBELLES[famille], "quantite": 10.0, "taux": 12.0, "gain": 120.0, "perte": None}
    code = code_de_ligne_de_gain(ligne)
    mode, _ = mode_de_correction(BLOC_BRUT, ligne, code)
    assert mode == "base_ou_taux"
    _poser(ligne, CorrectionDeLigne(ligne=code, libelle=ligne["libelle"], motif="Essai", base=valeur, saisie_id="s"))
    assert ligne["quantite"] == valeur
    assert ligne["gain"] == round(valeur * 12.0, 2)
    assert ligne["valeur_calculee"]["quantite"] == 10.0


def test_une_retenue_garde_son_champ_et_se_relit_sur_le_bulletin():
    ligne = {"libelle": LIBELLES["absence_maladie"], "quantite": 7.0, "taux": 15.0, "gain": None, "perte": 105.0}
    code = code_de_ligne_de_gain(ligne)
    _poser(ligne, CorrectionDeLigne(ligne=code, libelle=ligne["libelle"], motif="Essai", base=3.5, saisie_id="s"))
    assert ligne["perte"] == 52.5
    assert ligne["gain"] is None
    lue = lignes_corrigeables({"calcul_du_brut": [ligne]})[0]
    assert lue.retenue and lue.montant == 52.5 and lue.correction["saisie_id"] == "s"
