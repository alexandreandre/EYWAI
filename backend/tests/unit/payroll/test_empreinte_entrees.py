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
    assert MESSAGE_A_RECALCULER.startswith("Le calendrier ou les absences")


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
