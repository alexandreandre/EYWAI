"""Empreinte des données d'entrée d'un bulletin : stable, sensible aux heures, aveugle aux cumuls."""

from __future__ import annotations

from copy import deepcopy

from app.modules.payroll.domain.empreinte_entrees import (
    CLE_EMPREINTE,
    MESSAGE_A_RECALCULER,
    construire_entrees,
    empreinte,
    empreinte_stockee,
    etat_a_recalculer,
    poser_empreinte,
    saisie_pour_empreinte,
)


def _entrees(**surcharges):
    base = {
        "calendriers": {
            "2026-05": {
                "prevu": [{"jour": 12, "type": "travail", "heures": 7}],
                "reel": [{"jour": 12, "type": "travail", "heures": 8}],
                "cumuls": {"brut_total": 12_000},
            }
        },
        "absences": [{"type": "conge_paye", "selected_days": ["2026-05-04"]}],
        "saisies": [{"name": "Prime", "amount": 50.0}],
        "fiche": {"salaire_de_base": 2_000, "duree_hebdomadaire": 35},
        "notes_de_frais": [],
        "parametres_societe": {"taux_at_mp": 1.2},
    }
    base.update(surcharges)
    return base


def test_les_memes_entrees_donnent_la_meme_empreinte():
    a = construire_entrees(_entrees())
    b = construire_entrees(_entrees())
    assert empreinte(a) == empreinte(b)
    assert len(empreinte(a)) == 64


def test_changer_les_heures_d_un_jour_change_l_empreinte():
    avant = empreinte(construire_entrees(_entrees()))
    change = _entrees()
    change["calendriers"]["2026-05"]["reel"][0]["heures"] = 9
    assert empreinte(construire_entrees(change)) != avant


def test_changer_les_cumuls_ne_change_pas_l_empreinte():
    avant = empreinte(construire_entrees(_entrees()))
    change = _entrees()
    change["calendriers"]["2026-05"]["cumuls"] = {"brut_total": 99_999}
    change["cumuls"] = {"heures_remunerees": 151.67}
    assert empreinte(construire_entrees(change)) == avant


def test_l_empreinte_elle_meme_n_entre_pas_dans_le_hash():
    brut = _entrees()
    brut["parametres"] = {CLE_EMPREINTE: "abc", "smic_horaire": 11.88}
    h1 = empreinte(construire_entrees(brut))
    brut["parametres"][CLE_EMPREINTE] = "def"
    assert empreinte(construire_entrees(brut)) == h1


def test_les_trois_etats_a_recalculer():
    actuelle = empreinte(construire_entrees(_entrees()))
    assert etat_a_recalculer(None, actuelle) is None
    assert etat_a_recalculer("", actuelle) is None
    assert etat_a_recalculer(actuelle, actuelle) is False
    assert etat_a_recalculer("0" * 64, actuelle) is True
    assert etat_a_recalculer(actuelle, None) is None


def test_poser_et_lire_l_empreinte_dans_parametres():
    data = {"salaire_brut": 1.0, "parametres": {"smic_horaire": 11.88}}
    valeur = empreinte(construire_entrees(_entrees()))
    pose = poser_empreinte(data, valeur)
    assert pose["parametres"]["smic_horaire"] == 11.88
    assert pose["salaire_brut"] == 1.0
    assert empreinte_stockee(pose) == valeur
    assert data.get("parametres", {}).get(CLE_EMPREINTE) is None
    # Le hash global ne dit pas quoi : le message ne nomme pas une seule cause.
    assert "fiche" in MESSAGE_A_RECALCULER and "planning" in MESSAGE_A_RECALCULER


def test_la_fenetre_couvre_le_mois_precedent_et_le_suivant():
    from app.modules.payroll.domain.empreinte_entrees import mois_de_la_fenetre

    assert mois_de_la_fenetre(2026, 5) == ((2026, 4), (2026, 5), (2026, 6))
    assert mois_de_la_fenetre(2026, 1) == ((2025, 12), (2026, 1), (2026, 2))
    assert mois_de_la_fenetre(2026, 12) == ((2026, 11), (2026, 12), (2027, 1))


def test_changer_la_fenetre_des_variables_change_l_empreinte():
    avant = empreinte(construire_entrees(_entrees()))
    change = _entrees(fenetre_variables={"debut": "2026-04-27", "fin": "2026-05-31"})
    assert empreinte(construire_entrees(change)) != avant
    meme = _entrees(fenetre_variables={"debut": "2026-04-27", "fin": "2026-05-31"})
    assert empreinte(construire_entrees(change)) == empreinte(construire_entrees(meme))


def test_construire_entrees_est_stable_quel_que_soit_l_ordre_des_saisies():
    a = _entrees(saisies=[{"name": "B", "amount": 2}, {"name": "A", "amount": 1}])
    b = _entrees(saisies=[{"name": "A", "amount": 1}, {"name": "B", "amount": 2}])
    assert empreinte(construire_entrees(a)) == empreinte(construire_entrees(b))
    assert deepcopy(a)["saisies"][0]["name"] == "B"


# --- Cumuls du mois précédent -------------------------------------------------
#
# Le bulletin de M est calculé sur les cumuls de M-1 (réduction générale
# régularisée, tranches Agirc-Arrco, plafond des heures sup, base du dixième).
# Ils restent hors de l'empreinte d'entrée, que le moteur réécrit ; leur
# empreinte à part dit si M-1 a été recalculé depuis le calcul de M.


def test_l_empreinte_des_cumuls_suit_chaque_valeur():
    from app.modules.payroll.domain.empreinte_entrees import empreinte_cumuls

    cumuls = {"cumuls": {"brut_total": 6723.03, "reduction_generale_patronale": -1565.79}}
    assert empreinte_cumuls(cumuls) == empreinte_cumuls(deepcopy(cumuls))
    change = deepcopy(cumuls)
    change["cumuls"]["reduction_generale_patronale"] = -1515.79
    assert empreinte_cumuls(change) != empreinte_cumuls(cumuls)
    assert len(empreinte_cumuls(cumuls)) == 64


def test_des_cumuls_absents_valent_des_cumuls_vides():
    from app.modules.payroll.domain.empreinte_entrees import empreinte_cumuls

    assert empreinte_cumuls(None) == empreinte_cumuls({})
    assert empreinte_cumuls(None) != empreinte_cumuls({"cumuls": {"brut_total": 1.0}})


def test_poser_et_lire_l_empreinte_des_cumuls_dans_parametres():
    from app.modules.payroll.domain.empreinte_entrees import (
        CLE_EMPREINTE_CUMULS,
        empreinte_cumuls_stockee,
        poser_empreinte_cumuls,
    )

    data = {"salaire_brut": 1.0, "parametres": {CLE_EMPREINTE: "abc"}}
    pose = poser_empreinte_cumuls(data, "f" * 64)
    assert empreinte_cumuls_stockee(pose) == "f" * 64
    assert empreinte_stockee(pose) == "abc"
    assert pose["salaire_brut"] == 1.0
    assert CLE_EMPREINTE_CUMULS not in data["parametres"]
    assert empreinte_cumuls_stockee({"parametres": {}}) is None
    assert empreinte_cumuls_stockee(None) is None


def test_a_recalculer_des_que_les_entrees_ou_les_cumuls_ont_change():
    from app.modules.payroll.domain.empreinte_entrees import a_recalculer

    assert a_recalculer(False, True) is True
    assert a_recalculer(True, False) is True
    assert a_recalculer(None, True) is True
    assert a_recalculer(False, False) is False
    assert a_recalculer(False, None) is False
    assert a_recalculer(None, None) is None
    assert a_recalculer(None, False) is None


def test_une_colonne_correction_vide_ne_change_pas_l_empreinte():
    """Ajouter correction_ligne aux colonnes lues ne doit périmer aucun bulletin."""
    ancienne = {"year": 2026, "month": 9, "name": "Prime", "amount": 100}
    nouvelle = {**ancienne, "correction_ligne": None}
    assert empreinte(construire_entrees({"saisies": [ancienne]})) == empreinte(
        construire_entrees({"saisies": [saisie_pour_empreinte(nouvelle)]})
    )


def test_une_regularisation_change_l_empreinte():
    ordinaire = {"year": 2026, "month": 9, "name": "Régularisation", "amount": 0}
    regularisee = {**ordinaire, "correction_ligne": {"type": "regularisation_cotisation", "base": 10}}
    assert empreinte(construire_entrees({"saisies": [saisie_pour_empreinte(ordinaire)]})) != empreinte(
        construire_entrees({"saisies": [saisie_pour_empreinte(regularisee)]})
    )


def test_une_correction_de_ligne_change_l_empreinte():
    ordinaire = {"year": 2026, "month": 10, "name": "Correction – Salaire de base", "amount": 0}
    corrigee = {**ordinaire, "correction_ligne": {"type": "correction", "ligne": "brut:salaire_base", "base": 160.0}}
    assert empreinte(construire_entrees({"saisies": [saisie_pour_empreinte(ordinaire)]})) != empreinte(
        construire_entrees({"saisies": [saisie_pour_empreinte(corrigee)]})
    )


def test_la_valeur_calculee_d_une_ligne_corrigee_compte_au_centime():
    """Le PDF l'imprime : si Martine recalcule autrement la ligne corrigée, le bulletin est à recalculer."""
    from app.modules.payroll.domain.empreinte_entrees import ecart_au_centime

    def _bulletin(valeur):
        return {
            "salaire_brut": 2637.31,
            "net_a_payer": 2000.0,
            "calcul_du_brut": [{"libelle": "Salaire de base", "quantite": 160.0, "taux": 16.4832, "gain": 2637.31,
                                "correction": {"saisie_id": "c1"}, "valeur_calculee": {"gain": valeur}}],
        }

    assert ecart_au_centime(_bulletin(2500.0), _bulletin(2500.0)) is None
    assert ecart_au_centime(_bulletin(2500.0), _bulletin(2510.0)) is not None
