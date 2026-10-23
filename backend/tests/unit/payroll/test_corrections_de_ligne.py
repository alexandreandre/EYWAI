"""Corriger une ligne : par sa base, son taux ou son montant, au centime comme le moteur."""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.codes_des_lignes import BLOC_BRUT, BLOC_COTISATIONS
from app.modules.payroll.engine.corrections_manuelles import (
    CLE_CORRECTIONS_EN_ATTENTE,
    CLE_CORRECTIONS_LIGNE,
    CLE_REGULARISATIONS_COTISATION,
    RAISON_LIGNE_ABSENTE,
    CorrectionDeLigne,
    CorrectionInvalide,
    JournalDesCorrections,
    LignesCorrigees,
    RegularisationCotisation,
    corriger_la_reduction_generale,
    corriger_le_taux_d_impot,
    corriger_les_lignes_de_cotisation,
    corriger_les_lignes_de_gain,
    poser_les_corrections_en_attente,
    ranger_correction_manuelle,
    recaler_le_sous_total,
    synchroniser_le_maintien,
)

pytestmark = pytest.mark.unit

PERIODE = {"employee_id": "e", "company_id": "c", "year": 2026, "month": 10}


def _salaire_de_base():
    return {"libelle": "Salaire de base", "quantite": 151.67, "taux": 16.4832, "gain": 2500.0, "perte": None}


def _c(**champs):
    donnees = dict(ligne="brut:salaire_base", libelle="Salaire de base", motif="Avenant", saisie_id="s1")
    donnees.update(champs)
    return CorrectionDeLigne(**donnees)


def test_une_correction_porte_une_base_ou_un_taux_ou_un_montant_jamais_les_deux():
    with pytest.raises(CorrectionInvalide):
        _c(base=160.0, montant=2600.0)
    with pytest.raises(CorrectionInvalide):
        _c(ligne="cotisation:mutuelle:x", base=10.0, montant_patronal=5.0)


@pytest.mark.parametrize(
    "champs",
    [
        {"motif": "  ", "base": 160.0},
        {"ligne": "", "base": 160.0},
        {"ligne": "ailleurs:x", "base": 160.0},
        {},
        {"taux_salarial": 0.01},
        {"ligne": "impot", "libelle": "Impôt", "taux": 120.0},
    ],
)
def test_une_correction_incomplete_ou_hors_de_sa_ligne_est_refusee(champs):
    with pytest.raises(CorrectionInvalide):
        _c(**champs)


def test_la_charge_utile_ne_porte_que_les_champs_remplis():
    assert _c(base=160.0).charge_utile() == {
        "type": "correction",
        "ligne": "brut:salaire_base",
        "libelle": "Salaire de base",
        "motif": "Avenant",
        "base": 160.0,
    }
    assert _c(base=160.0).trace()["saisie_id"] == "s1"


def test_la_saisie_du_mois_porte_la_correction_sans_montant():
    saisie = _c(base=160.0).saisie_du_mois(PERIODE)
    assert saisie["name"] == "Correction – Salaire de base"
    assert saisie["amount"] == 0 and saisie["description"] == "Avenant"
    assert saisie["correction_ligne"]["type"] == "correction"
    assert saisie["employee_id"] == "e" and saisie["month"] == 10


def test_ranger_une_correction_la_met_a_part_des_primes():
    saisies: dict = {}
    charge = _c(base=160.0).charge_utile()
    assert ranger_correction_manuelle({"id": "s1", "correction_ligne": charge}, saisies)
    assert saisies[CLE_CORRECTIONS_LIGNE] == [{**charge, "saisie_id": "s1"}]
    assert not ranger_correction_manuelle({"id": "s2", "name": "Prime", "correction_ligne": None}, saisies)


def test_ranger_une_regularisation_la_range_comme_a_l_etape_1():
    regul = RegularisationCotisation(coti_id="mutuelle", libelle="Mutuelle", motif="Tarif", montant_patronal=8.3)
    saisies: dict = {}
    assert ranger_correction_manuelle({"id": "r1", "correction_ligne": regul.charge_utile()}, saisies)
    assert saisies[CLE_REGULARISATIONS_COTISATION][0]["saisie_id"] == "r1"
    assert CLE_CORRECTIONS_LIGNE not in saisies


def test_le_journal_ne_se_pose_que_s_il_y_a_des_corrections():
    assert JournalDesCorrections.depuis({}) is None
    assert JournalDesCorrections.depuis({CLE_CORRECTIONS_LIGNE: []}) is None
    journal = JournalDesCorrections.depuis({CLE_CORRECTIONS_LIGNE: [_c(base=160.0).trace()]})
    assert journal is not None and [e["saisie_id"] for e in journal.en_attente()] == ["s1"]


def test_la_base_corrigee_fait_suivre_le_montant_au_centime():
    journal = JournalDesCorrections([_c(base=160.0)])
    ligne = _salaire_de_base()
    effet = journal.corriger(ligne, BLOC_BRUT, "brut:salaire_base")
    assert ligne["quantite"] == 160.0
    assert ligne["gain"] == round(160.0 * 16.4832, 2)
    assert ligne["libelle"] == "Salaire de base"
    assert ligne["valeur_calculee"] == {"quantite": 151.67, "taux": 16.4832, "gain": 2500.0, "perte": None}
    assert ligne["correction"]["motif"] == "Avenant" and ligne["correction"]["saisie_id"] == "s1"
    assert effet.famille == "brut:salaire_base"
    assert effet.quantite == pytest.approx(8.33)
    assert effet.brut == pytest.approx(round(160.0 * 16.4832, 2) - 2500.0)
    assert journal.en_attente() == []


def test_une_retenue_corrigee_par_son_taux_baisse_le_brut():
    ligne = {"libelle": "Absence non rémunérée du 16/03/26", "quantite": 7.0, "taux": 16.0, "gain": None, "perte": 112.0}
    journal = JournalDesCorrections([_c(ligne="brut:absence_non_remuneree:16-03-26", libelle=ligne["libelle"], taux=17.0)])
    effet = journal.corriger(ligne, BLOC_BRUT, "brut:absence_non_remuneree:16-03-26")
    assert ligne["perte"] == 119.0 and ligne["gain"] is None
    assert effet.brut == -7.0 and effet.quantite == 0.0


def test_une_ligne_au_forfait_se_corrige_par_son_montant():
    ligne = {"libelle": "Prime de précarité (CDD)", "quantite": None, "taux": 0.1, "gain": 1100.0, "perte": None}
    journal = JournalDesCorrections([_c(ligne="brut:precarite", libelle=ligne["libelle"], montant=1000.0)])
    journal.corriger(ligne, BLOC_BRUT, "brut:precarite")
    assert ligne["gain"] == 1000.0 and ligne["taux"] == 0.1


def test_une_correction_qui_ne_convient_plus_a_sa_ligne_reste_en_attente():
    ligne = {"libelle": "Prime de précarité (CDD)", "quantite": None, "taux": 0.1, "gain": 1100.0, "perte": None}
    journal = JournalDesCorrections([_c(ligne="brut:precarite", libelle=ligne["libelle"], base=10.0)])
    assert journal.corriger(ligne, BLOC_BRUT, "brut:precarite") is None
    assert ligne["gain"] == 1100.0 and "correction" not in ligne
    attente = journal.en_attente()
    assert attente[0]["saisie_id"] == "s1" and "son montant" in attente[0]["raison"]


def test_une_correction_dont_la_ligne_n_existe_plus_reste_en_attente():
    journal = JournalDesCorrections([_c(base=160.0)])
    journal.corriger({"libelle": "Avantages en nature", "gain": 1.0}, BLOC_BRUT, "brut:avantages_en_nature")
    assert journal.en_attente() == [{**_c(base=160.0).trace(), "raison": RAISON_LIGNE_ABSENTE}]


def test_une_ligne_deja_corrigee_ne_l_est_pas_deux_fois():
    journal = JournalDesCorrections([_c(base=160.0), _c(base=170.0, saisie_id="s2")])
    ligne = _salaire_de_base()
    journal.corriger(ligne, BLOC_BRUT, "brut:salaire_base")
    assert journal.corriger(ligne, BLOC_BRUT, "brut:salaire_base") is None
    assert ligne["quantite"] == 160.0
    assert [e["saisie_id"] for e in journal.en_attente()] == ["s2"]


def test_une_cotisation_corrigee_par_sa_base_garde_son_taux():
    ligne = {"coti_id": "securite_sociale_maladie", "libelle": "Maladie", "base": 2000.0,
             "taux_salarial": 0.0, "taux_patronal": 0.07, "montant_salarial": 0.0, "montant_patronal": 140.0}
    journal = JournalDesCorrections([_c(ligne="cotisation:securite_sociale_maladie", libelle="Maladie", base=2100.0)])
    effet = journal.corriger(ligne, BLOC_COTISATIONS, "cotisation:securite_sociale_maladie")
    assert ligne["montant_patronal"] == 147.0 and ligne["montant_salarial"] == 0.0 and ligne["base"] == 2100.0
    assert ligne["valeur_calculee"]["montant_patronal"] == 140.0
    assert (effet.salarial, effet.patronal) == (0.0, 7.0)


def test_une_mutuelle_se_corrige_par_son_montant():
    ligne = {"coti_id": "mutuelle", "libelle": "Mutuelle", "base": None, "taux_salarial": None,
             "taux_patronal": None, "montant_salarial": 20.0, "montant_patronal": 30.0}
    code = "cotisation:mutuelle:mutuelle"
    journal = JournalDesCorrections([_c(ligne=code, libelle="Mutuelle", montant_salarial=22.5)])
    effet = journal.corriger(ligne, BLOC_COTISATIONS, code)
    assert ligne["montant_salarial"] == 22.5 and ligne["montant_patronal"] == 30.0
    assert effet.salarial == 2.5


def test_les_lignes_corrigees_corrigent_chaque_ligne_a_son_entree():
    lignes = LignesCorrigees(JournalDesCorrections([_c(base=160.0)]), BLOC_BRUT)
    lignes.append(_salaire_de_base())
    lignes.extend([{"libelle": "Avantages en nature", "quantite": None, "taux": None, "gain": 120.0, "perte": None}])
    assert lignes[0]["quantite"] == 160.0 and "correction" not in lignes[1]
    assert lignes.effet.corrigees == 1
    assert lignes.effet.quantite("brut:salaire_base") == pytest.approx(8.33)
    assert lignes.effet.quantite("brut:heures_sup") == 0.0


def test_sans_journal_les_lignes_corrigees_sont_une_liste_ordinaire():
    ligne = _salaire_de_base()
    lignes = LignesCorrigees(None, BLOC_BRUT)
    lignes.append(ligne)
    lignes += [dict(ligne)]
    assert list(lignes) == [_salaire_de_base(), _salaire_de_base()]
    assert lignes.effet.corrigees == 0


def test_deux_lignes_de_meme_code_se_corrigent_chacune_par_son_numero():
    vd = {"coti_id": "vieillesse_deplafonnee", "libelle": "Vieillesse déplafonnée", "base": 2500.0,
          "taux_salarial": 0.004, "taux_patronal": 0.0202, "montant_salarial": 10.0, "montant_patronal": 50.5}
    code = "cotisation:vieillesse_deplafonnee#2"
    lignes = LignesCorrigees(
        JournalDesCorrections([_c(ligne=code, libelle="Vieillesse déplafonnée", base=2600.0)]), BLOC_COTISATIONS
    )
    lignes.extend([dict(vd), dict(vd)])
    assert lignes[0]["base"] == 2500.0 and lignes[1]["base"] == 2600.0


def test_une_passe_de_pipeline_corrige_les_lignes_nees_apres_et_laisse_les_autres():
    deja = _salaire_de_base()
    JournalDesCorrections([_c(base=160.0)]).corriger(deja, BLOC_BRUT, "brut:salaire_base")
    maintien = {"libelle": "Maintien de salaire employeur", "quantite": None, "taux": None, "gain": 300.0,
                "perte": None, "is_maintien_employeur": True}
    journal = JournalDesCorrections(
        [_c(ligne="brut:maintien_employeur", libelle="Maintien de salaire employeur", montant=250.0, saisie_id="s2")]
    )
    effet = corriger_les_lignes_de_gain([deja, maintien], journal)
    assert maintien["gain"] == 250.0 and effet.corrigees == 1 and effet.sur_le_brut("brut:maintien_employeur") == -50.0
    resultats = {"maintien": {"maintien_verse": 300.0}}
    synchroniser_le_maintien(resultats, [deja, maintien])
    assert resultats["maintien"]["maintien_verse"] == 250.0


def test_le_sous_total_suit_le_salaire_de_base_corrige():
    base = {"libelle": "Salaire de base", "quantite": 151.67, "taux": 12.2503, "gain": 1858.01, "perte": None}
    hs = {"libelle": "Heures suppl. structurelles majorées à 25%", "quantite": 17.33, "taux": 15.3129, "gain": 265.37, "perte": None}
    sous_total = {"libelle": "SOUS-TOTAL SALAIRE CONTRACTUEL", "quantite": 169.0, "taux": None, "gain": 2123.38,
                  "perte": None, "is_sous_total": True}
    lignes = [base, hs, sous_total]
    recaler_le_sous_total(lignes)
    assert sous_total["gain"] == 2123.38  # rien de corrigé : intact
    JournalDesCorrections([_c(base=160.0)]).corriger(base, BLOC_BRUT, "brut:salaire_base")
    recaler_le_sous_total(lignes)
    assert sous_total["gain"] == round(base["gain"] + 265.37, 2)
    assert sous_total["quantite"] == round(160.0 + 17.33, 2)


def _rg(montant=-300.0):
    return {"coti_id": "reduction_generale", "libelle": "Réduction générale de cotisations patronales",
            "base": 2000.0, "taux_salarial": None, "taux_patronal": 0.15, "montant_salarial": 0.0,
            "montant_patronal": montant, "valeur_cumulative_a_enregistrer": 2700.0}


def test_la_reduction_generale_corrigee_enregistre_ce_qui_est_applique():
    journal = JournalDesCorrections(
        [_c(ligne="cotisation:reduction_generale", libelle="Réduction générale de cotisations patronales",
            montant_patronal=-250.0)]
    )
    ligne = corriger_la_reduction_generale(_rg(), journal, reduction_deja=2400.0)
    assert ligne["montant_patronal"] == -250.0
    assert ligne["valeur_cumulative_a_enregistrer"] == 2650.0
    assert ligne["valeur_calculee"]["montant_patronal"] == -300.0


def test_une_reduction_de_l_annee_negative_est_refusee():
    journal = JournalDesCorrections(
        [_c(ligne="cotisation:reduction_generale", libelle="Réduction générale de cotisations patronales",
            montant_patronal=150.0)]
    )
    with pytest.raises(CorrectionInvalide):
        corriger_la_reduction_generale(_rg(), journal, reduction_deja=100.0)


def test_sans_correction_la_reduction_est_intacte():
    assert corriger_la_reduction_generale(_rg(), None, 2400.0) == _rg()
    assert corriger_la_reduction_generale(None, JournalDesCorrections([]), 0.0) is None


def test_le_taux_d_impot_du_mois_se_corrige():
    journal = JournalDesCorrections(
        [_c(ligne="impot", libelle="Impôt sur le revenu prélevé à la source", motif="Taux DGFiP du mois", taux=7.5)]
    )
    taux, trace = corriger_le_taux_d_impot(5.2, 2000.0, journal)
    assert taux == 7.5
    assert trace["valeur_calculee"] == {"taux": 5.2, "montant": 104.0}
    assert trace["correction"]["taux"] == 7.5 and trace["correction"]["saisie_id"] == "s1"
    assert journal.en_attente() == []


def test_sans_correction_le_taux_d_impot_est_celui_de_martine():
    assert corriger_le_taux_d_impot(5.2, 2000.0, None) == (5.2, None)
    assert corriger_le_taux_d_impot(5.2, 2000.0, JournalDesCorrections([_c(base=160.0)])) == (5.2, None)


def test_les_corrections_en_attente_vont_sur_le_bulletin_et_seulement_elles():
    bulletin: dict = {}
    poser_les_corrections_en_attente(bulletin, None)
    poser_les_corrections_en_attente(bulletin, JournalDesCorrections([]))
    assert CLE_CORRECTIONS_EN_ATTENTE not in bulletin
    poser_les_corrections_en_attente(bulletin, JournalDesCorrections([_c(base=160.0)]))
    assert bulletin[CLE_CORRECTIONS_EN_ATTENTE][0]["saisie_id"] == "s1"


# --- Le journal ne se consomme pas : idempotent et jamais silencieux --------


def _maladie():
    return {"coti_id": "securite_sociale_maladie", "libelle": "Maladie", "base": 2000.0,
            "taux_salarial": 0.0, "taux_patronal": 0.07, "montant_salarial": 0.0, "montant_patronal": 140.0}


def test_un_second_calcul_avec_le_meme_journal_corrige_ses_lignes_a_l_identique():
    journal = JournalDesCorrections([_c(base=160.0)])
    premier = LignesCorrigees(journal, BLOC_BRUT, [_salaire_de_base()])
    second = LignesCorrigees(journal, BLOC_BRUT, [_salaire_de_base()])
    assert second[0] == premier[0] and second[0]["quantite"] == 160.0
    assert second.effet.corrigees == 1 and second.effet.quantite("brut:salaire_base") == pytest.approx(8.33)
    assert journal.en_attente() == []


def test_un_second_calcul_retrouve_le_taux_d_impot_et_la_reduction_generale():
    rg = "cotisation:reduction_generale"
    journal = JournalDesCorrections([
        _c(ligne="impot", libelle="Impôt sur le revenu prélevé à la source", taux=7.5, saisie_id="i1"),
        _c(ligne=rg, libelle="Réduction générale de cotisations patronales", montant_patronal=-250.0, saisie_id="r1"),
    ])
    assert corriger_le_taux_d_impot(5.2, 2000.0, journal) == corriger_le_taux_d_impot(5.2, 2000.0, journal)
    assert corriger_le_taux_d_impot(5.2, 2000.0, journal)[0] == 7.5
    premiere = corriger_la_reduction_generale(_rg(), journal, reduction_deja=2400.0)
    seconde = corriger_la_reduction_generale(_rg(), journal, reduction_deja=2400.0)
    assert seconde == premiere and seconde["montant_patronal"] == -250.0
    assert journal.en_attente() == []


def test_une_ligne_qui_porte_sa_correction_ne_la_prend_pas_deux_fois():
    journal = JournalDesCorrections([_c(base=160.0)])
    lignes = LignesCorrigees(journal, BLOC_BRUT, [_salaire_de_base()])
    effet = corriger_les_lignes_de_gain(lignes, journal)
    assert effet.corrigees == 0
    assert lignes[0]["valeur_calculee"] == {"quantite": 151.67, "taux": 16.4832, "gain": 2500.0, "perte": None}


def test_un_second_calcul_ne_pose_jamais_l_autre_correction_de_la_meme_ligne():
    journal = JournalDesCorrections([_c(base=160.0), _c(base=170.0, saisie_id="s2")])
    LignesCorrigees(journal, BLOC_BRUT, [_salaire_de_base()])
    second = LignesCorrigees(journal, BLOC_BRUT, [_salaire_de_base()])
    assert second[0]["quantite"] == 160.0 and second[0]["correction"]["saisie_id"] == "s1"
    attente = journal.en_attente()
    assert [e["saisie_id"] for e in attente] == ["s2"] and "autre correction" in attente[0]["raison"]


def test_une_ligne_de_gain_retouchee_apres_son_entree_retrouve_sa_correction():
    journal = JournalDesCorrections([_c(base=160.0)])
    lignes = LignesCorrigees(journal, BLOC_BRUT, [_salaire_de_base()])
    lignes[0]["gain"] = 2600.0  # le calcul retouche la ligne après son entrée
    effet = corriger_les_lignes_de_gain(lignes, journal)
    voulu = round(160.0 * 16.4832, 2)
    assert lignes[0]["gain"] == voulu and lignes[0]["quantite"] == 160.0
    # La valeur retouchée est désormais celle de Martine ; le reste de son calcul est gardé.
    assert lignes[0]["valeur_calculee"] == {"quantite": 151.67, "taux": 16.4832, "gain": 2600.0, "perte": None}
    assert effet.corrigees == 1 and effet.sur_le_brut("brut:salaire_base") == round(voulu - 2600.0, 2)
    assert effet.quantite("brut:salaire_base") == 0.0


def test_une_cotisation_retouchee_apres_son_entree_retrouve_sa_correction():
    code = "cotisation:securite_sociale_maladie"
    journal = JournalDesCorrections([_c(ligne=code, libelle="Maladie", base=2100.0)])
    lignes = LignesCorrigees(journal, BLOC_COTISATIONS, [_maladie()])
    lignes[0]["montant_patronal"] = 150.0
    effet = corriger_les_lignes_de_cotisation(lignes, journal)
    assert lignes[0]["montant_patronal"] == 147.0 and lignes[0]["base"] == 2100.0
    assert lignes[0]["valeur_calculee"]["montant_patronal"] == 150.0
    assert lignes[0]["valeur_calculee"]["base"] == 2000.0
    assert (effet.salarial, effet.patronal) == (0.0, -3.0)


def test_une_correction_posee_par_un_calcul_abandonne_finit_en_attente():
    journal = JournalDesCorrections([_c(base=160.0)])
    LignesCorrigees(journal, BLOC_BRUT, [_salaire_de_base()])  # calcul abandonné
    bulletin = {"calcul_du_brut": [{"libelle": "Avantages en nature", "quantite": None, "taux": None,
                                    "gain": 120.0, "perte": None}]}
    poser_les_corrections_en_attente(bulletin, journal)
    assert bulletin[CLE_CORRECTIONS_EN_ATTENTE] == [{**_c(base=160.0).trace(), "raison": RAISON_LIGNE_ABSENTE}]


def test_une_correction_que_le_bulletin_porte_n_est_pas_en_attente():
    journal = JournalDesCorrections([_c(base=160.0)])
    lignes = LignesCorrigees(journal, BLOC_BRUT, [_salaire_de_base()])
    bulletin = {"calcul_du_brut": list(lignes)}
    poser_les_corrections_en_attente(bulletin, journal)
    assert CLE_CORRECTIONS_EN_ATTENTE not in bulletin


def test_une_correction_posee_sur_un_autre_doublon_que_le_sien_finit_en_attente():
    code = "cotisation:mutuelle:mutuelle"
    mutuelle = {"coti_id": "mutuelle", "libelle": "Mutuelle", "base": None, "taux_salarial": None,
                "taux_patronal": None, "montant_salarial": 20.0, "montant_patronal": 30.0}
    journal = JournalDesCorrections([_c(ligne=f"{code}#2", libelle="Mutuelle", montant_salarial=22.5)])
    lignes = LignesCorrigees(journal, BLOC_COTISATIONS, [dict(mutuelle), dict(mutuelle)])
    assert lignes[1]["montant_salarial"] == 22.5
    # Le bulletin range les deux mutuelles dans l'autre ordre : la ligne corrigée y devient la première.
    bulletin = {"cotisations_officielles": [{"lignes": [lignes[1], lignes[0]]}]}
    poser_les_corrections_en_attente(bulletin, journal)
    attente = bulletin[CLE_CORRECTIONS_EN_ATTENTE]
    assert [e["ligne"] for e in attente] == [f"{code}#2"] and attente[0]["raison"] != RAISON_LIGNE_ABSENTE
