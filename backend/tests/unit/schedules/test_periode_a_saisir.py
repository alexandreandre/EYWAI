"""La période à saisir pour la paie d'un mois : l'union du mois civil et de la
fenêtre des variables, jugée jour par jour, dans les bornes du contrat."""

from __future__ import annotations

import calendar
from datetime import date

import pytest

from app.modules.schedules.domain.periode_a_saisir import (
    JourASaisir,
    libelle_plages,
    periode_a_saisir,
    plages,
    raisons_en_clair,
)

pytestmark = pytest.mark.unit

FENETRE_JUILLET = (date(2026, 6, 22), date(2026, 7, 26))  # Colorplast : S26–S30


def _mois(annee: int, mois: int, *, reel_jusqu_au: int | None, heures: float = 8.0):
    """Prévu complet (travail en semaine, repos le week-end) ; réel jusqu'au jour donné."""
    prevu, reel = [], []
    for jour in range(1, calendar.monthrange(annee, mois)[1] + 1):
        d = date(annee, mois, jour)
        if d.weekday() >= 5:
            prevu.append({"jour": jour, "type": "repos", "heures_prevues": 0.0})
            continue
        prevu.append({"jour": jour, "type": "travail", "heures_prevues": heures})
        if reel_jusqu_au is not None and jour <= reel_jusqu_au:
            reel.append({"jour": jour, "type": "travail", "heures_faites": heures})
    return prevu, reel


def test_michel_juillet_2026_bloque_sur_juin_et_informe_sur_la_fin_de_juillet():
    """État du test au 20/09 : juin sans réel, juillet saisi du 1er au 24."""
    periode = periode_a_saisir(
        annee=2026,
        mois=7,
        fenetre=FENETRE_JUILLET,
        calendriers={
            (2026, 6): _mois(2026, 6, reel_jusqu_au=None),
            (2026, 7): _mois(2026, 7, reel_jusqu_au=24),
        },
        date_entree=date(2020, 1, 15),
    )

    assert (periode.debut, periode.fin) == (date(2026, 6, 22), date(2026, 7, 31))
    assert periode.statut == "a_saisir"
    assert [j.jour.isoformat() for j in periode.bloquants] == [
        "2026-06-22",
        "2026-06-23",
        "2026-06-24",
        "2026-06-25",
        "2026-06-26",
        "2026-06-29",
        "2026-06-30",
    ]
    assert [j.jour.day for j in periode.informatifs] == [27, 28, 29, 30, 31]
    assert {j.motif for j in periode.manquants} == {"prevu_sans_reel"}


def test_une_fois_juin_saisi_juillet_est_saisi_avec_cinq_informatifs():
    periode = periode_a_saisir(
        annee=2026,
        mois=7,
        fenetre=FENETRE_JUILLET,
        calendriers={
            (2026, 6): _mois(2026, 6, reel_jusqu_au=30),
            (2026, 7): _mois(2026, 7, reel_jusqu_au=24),
        },
    )

    assert periode.statut == "saisi"
    assert len(periode.informatifs) == 5


def test_rien_a_saisir_avant_l_embauche_ni_apres_la_sortie():
    # Un salarié qui pointe (juin saisi) ; juillet reste vide.
    calendriers = {
        (2026, 6): _mois(2026, 6, reel_jusqu_au=30),
        (2026, 7): _mois(2026, 7, reel_jusqu_au=None),
    }

    entrant = periode_a_saisir(
        annee=2026, mois=7, fenetre=FENETRE_JUILLET, calendriers=calendriers, date_entree=date(2026, 7, 6)
    )
    sortant = periode_a_saisir(
        annee=2026, mois=7, fenetre=FENETRE_JUILLET, calendriers=calendriers, date_sortie=date(2026, 7, 15)
    )

    assert min(j.jour for j in entrant.manquants) == date(2026, 7, 6)
    assert max(j.jour for j in sortant.manquants) == date(2026, 7, 15)


def test_un_mois_sans_planning_attend_ses_jours_ouvres_pas_le_week_end():
    periode = periode_a_saisir(
        annee=2026,
        mois=7,
        fenetre=FENETRE_JUILLET,
        calendriers={(2026, 7): _mois(2026, 7, reel_jusqu_au=31)},  # pas de ligne pour juin
    )

    juin = [j for j in periode.manquants if j.jour.month == 6]
    assert [j.jour.day for j in juin] == [22, 23, 24, 25, 26, 29, 30]
    assert {j.motif for j in juin} == {"planning_absent"}
    assert all(j.bloquant for j in juin)


def test_un_forfait_jour_est_juge_sur_le_mois_civil_seul():
    prevu = [{"jour": j, "type": "travail", "heures_prevues": 1} for j in range(1, 32)]
    reel = [{"jour": j, "heures_faites": 1} for j in range(1, 32)]

    periode = periode_a_saisir(
        annee=2026, mois=7, fenetre=FENETRE_JUILLET, calendriers={(2026, 7): (prevu, reel)}, forfait=True
    )

    assert periode.fenetre == (date(2026, 7, 1), date(2026, 7, 31))
    assert periode.statut == "saisi" and not periode.manquants


def test_en_mode_mois_calendaire_il_n_y_a_pas_d_informatif():
    periode = periode_a_saisir(
        annee=2026,
        mois=7,
        fenetre=(date(2026, 7, 1), date(2026, 7, 31)),
        calendriers={(2026, 7): _mois(2026, 7, reel_jusqu_au=24)},
    )

    assert not periode.informatifs
    assert [j.jour.day for j in periode.bloquants] == [27, 28, 29, 30, 31]


def test_une_fin_avancee_rend_la_derniere_semaine_informative():
    periode = periode_a_saisir(
        annee=2026,
        mois=7,
        fenetre=(date(2026, 6, 22), date(2026, 7, 19)),
        calendriers={
            (2026, 6): _mois(2026, 6, reel_jusqu_au=30),
            (2026, 7): _mois(2026, 7, reel_jusqu_au=17),
        },
    )

    assert periode.statut == "saisi"
    assert [j.jour.day for j in periode.informatifs] == [20, 21, 22, 23, 24, 27, 28, 29, 30, 31]


def test_les_motifs_distinguent_prevu_sans_heures_et_reel_a_zero():
    prevu = [
        {"jour": 1, "type": "travail", "heures_prevues": None},
        {"jour": 2, "type": "travail", "heures_prevues": 8.0},
    ]
    reel = [{"jour": 2, "type": "travail", "heures_faites": 0.0}]

    periode = periode_a_saisir(
        annee=2026,
        mois=7,
        fenetre=(date(2026, 7, 1), date(2026, 7, 2)),
        calendriers={(2026, 7): (prevu, reel)},
        date_sortie=date(2026, 7, 2),
    )

    assert [(j.jour.day, j.motif) for j in periode.manquants] == [
        (1, "prevu_sans_heures"),
        (2, "reel_a_zero"),
    ]


def test_les_plages_regroupent_les_jours_consecutifs():
    jours = [date(2026, 6, 22), date(2026, 6, 23), date(2026, 6, 24), date(2026, 6, 26), date(2026, 7, 1)]

    assert plages(jours) == [
        (date(2026, 6, 22), date(2026, 6, 24)),
        (date(2026, 6, 26), date(2026, 6, 26)),
        (date(2026, 7, 1), date(2026, 7, 1)),
    ]
    assert libelle_plages(jours) == "22/06–24/06, 26/06, 01/07"


# --- Heures saisies un jour d'arrêt : la période porte ses conflits ---


def _arret_septembre(heures_sur: dict[int, float]):
    """Arrêt sur tous les jours ouvrés de septembre 2026 ; heures réelles sur certains jours."""
    prevu, reel = [], []
    for jour in range(1, 31):
        if date(2026, 9, jour).weekday() >= 5:
            prevu.append({"jour": jour, "type": "weekend", "heures_prevues": 0.0})
            continue
        prevu.append({"jour": jour, "type": "arret_maladie", "heures_prevues": 0.0})
        reel.append({"jour": jour, "type": "travail", "heures_faites": heures_sur.get(jour, 0.0)})
    return prevu, reel


def test_la_periode_porte_les_jours_en_conflit_de_toute_l_union():
    """Fenêtre 24/08 → 27/09 : un conflit d'août dans la fenêtre compte, un
    conflit de fin septembre aussi (mois civil), un conflit d'août hors union non."""
    aout_prevu, aout_reel = _mois(2026, 8, reel_jusqu_au=31, heures=7.0)
    for entree in aout_prevu:
        if entree["jour"] in (20, 25):
            entree.update(type="arret_maladie", heures_prevues=0.0)

    periode = periode_a_saisir(
        annee=2026,
        mois=9,
        fenetre=(date(2026, 8, 24), date(2026, 9, 27)),
        calendriers={
            (2026, 8): (aout_prevu, aout_reel),
            (2026, 9): _arret_septembre({7: 9.0, 8: 7.25, 29: 8.0}),
        },
        date_entree=date(2020, 1, 15),
    )

    assert [(c.annee, c.mois, c.jour, c.heures_saisies) for c in periode.conflits] == [
        (2026, 8, 25, 7.0),
        (2026, 9, 7, 9.0),
        (2026, 9, 8, 7.25),
        (2026, 9, 29, 8.0),
    ]
    # Un conflit n'est pas un jour à saisir : le statut ne dépend que des manquants.
    assert periode.statut == "saisi"


def test_un_conflit_hors_contrat_ne_compte_pas():
    periode = periode_a_saisir(
        annee=2026,
        mois=9,
        fenetre=(date(2026, 9, 1), date(2026, 9, 30)),
        calendriers={(2026, 9): _arret_septembre({7: 9.0, 28: 8.0})},
        date_entree=date(2026, 9, 8),
    )

    assert [c.jour for c in periode.conflits] == [28]


def test_une_periode_sans_conflit_a_une_liste_vide():
    periode = periode_a_saisir(
        annee=2026,
        mois=7,
        fenetre=FENETRE_JUILLET,
        calendriers={
            (2026, 6): _mois(2026, 6, reel_jusqu_au=30),
            (2026, 7): _mois(2026, 7, reel_jusqu_au=31),
        },
    )

    assert periode.conflits == ()


def test_un_samedi_couvert_par_un_arret_valide_compte_dans_la_periode():
    prevu, reel = _arret_septembre({})
    reel.append({"jour": 12, "type": "travail", "heures_faites": 5.0})  # samedi

    periode = periode_a_saisir(
        annee=2026,
        mois=9,
        fenetre=(date(2026, 9, 1), date(2026, 9, 30)),
        calendriers={(2026, 9): (prevu, reel)},
        absences_validees=[
            {
                "type": "arret_maladie",
                "status": "validated",
                "selected_days": [f"2026-09-{j:02d}" for j in range(1, 31)],
            }
        ],
    )

    assert [(c.jour, c.type_prevu, c.heures_saisies) for c in periode.conflits] == [
        (12, "arret_maladie", 5.0)
    ]


def test_une_entree_apres_la_cloture_des_variables_ne_bloque_pas_les_jours_hors_fenetre():
    """Entrée le 21/09, fenêtre close le 20/09 : les 21–30 hors fenêtre ne refusent pas."""
    fenetre = (date(2026, 8, 24), date(2026, 9, 20))
    periode = periode_a_saisir(
        annee=2026,
        mois=9,
        fenetre=fenetre,
        calendriers={
            (2026, 8): _mois(2026, 8, reel_jusqu_au=31),
            (2026, 9): _mois(2026, 9, reel_jusqu_au=None),
        },
        date_entree=date(2026, 9, 21),
    )

    assert periode.statut == "saisi"
    assert not periode.bloquants
    assert all(j.jour >= date(2026, 9, 21) for j in periode.manquants)
    assert [j.jour.day for j in periode.informatifs] == [21, 22, 23, 24, 25, 28, 29, 30]


# --- Ce que le moteur lira : un réel vide ou à 0 h compte, l'absence de réel non ---
#
# Le moteur lit le réel d'un mois dès qu'une heure y est pointée
# (`planning_repli.mois_sans_pointage`) : un jour « travail » vide ou à 0 h
# vaut alors 0 h contre 8 h prévues, et la compensation entre semaines en
# fait une semaine à −39 h qui efface les heures sup du mois. Sans aucune
# heure pointée, le prévu fait foi. Constat du 02/10/2026 (septembre 2026).

FENETRE_SEPTEMBRE = (date(2026, 8, 24), date(2026, 9, 20))  # S35–S38


def _septembre_pointe(*, s35: float | None, s37_importee: bool):
    """Août et septembre pointés à 8 h ; S35 (24–28/08) selon `s35`, S37 (07–11/09) selon l'import.

    `s35` : heures réelles de S35 (None = lignes créées à vide, 0.0 = zéro saisi).
    """
    aout_prevu, aout_reel = _mois(2026, 8, reel_jusqu_au=31)
    for entree in aout_reel:
        if 24 <= entree["jour"] <= 28:
            entree["heures_faites"] = s35
    sept_prevu, sept_reel = _mois(2026, 9, reel_jusqu_au=20)
    if not s37_importee:
        sept_reel = [e for e in sept_reel if not 7 <= e["jour"] <= 11]
    return {(2026, 8): (aout_prevu, aout_reel), (2026, 9): (sept_prevu, sept_reel)}


def test_une_semaine_a_vide_et_une_semaine_jamais_importee_bloquent_la_fenetre():
    periode = periode_a_saisir(
        annee=2026,
        mois=9,
        fenetre=FENETRE_SEPTEMBRE,
        calendriers=_septembre_pointe(s35=None, s37_importee=False),
        date_entree=date(2018, 2, 1),
    )

    assert periode.statut == "a_saisir"
    assert libelle_plages(j.jour for j in periode.bloquants) == "24/08–28/08, 07/09–11/09"
    assert {j.motif for j in periode.bloquants} == {"prevu_sans_reel"}
    assert [j.jour.day for j in periode.informatifs] == [21, 22, 23, 24, 25, 28, 29, 30]


def test_une_semaine_saisie_a_zero_heure_bloque_comme_reel_a_zero():
    periode = periode_a_saisir(
        annee=2026,
        mois=9,
        fenetre=FENETRE_SEPTEMBRE,
        calendriers=_septembre_pointe(s35=0.0, s37_importee=True),
    )

    assert [(j.jour.isoformat(), j.motif) for j in periode.bloquants] == [
        (f"2026-08-{jour}", "reel_a_zero") for jour in range(24, 29)
    ]


def test_un_salarie_qui_pointe_avant_la_fenetre_doit_saisir_la_fenetre():
    """Pointé du 1er au 21/08, plus rien ensuite : un oubli d'import, pas un salarié sans pointage."""
    aout_prevu, aout_reel = _mois(2026, 8, reel_jusqu_au=21)
    periode = periode_a_saisir(
        annee=2026,
        mois=9,
        fenetre=FENETRE_SEPTEMBRE,
        calendriers={
            (2026, 8): (aout_prevu, aout_reel),
            (2026, 9): _mois(2026, 9, reel_jusqu_au=None),
        },
    )

    assert libelle_plages(j.jour for j in periode.bloquants) == (
        "24/08–28/08, 31/08–04/09, 07/09–11/09, 14/09–18/09"
    )


def test_un_salarie_qui_ne_pointe_jamais_n_a_rien_a_saisir():
    """Société qui ne pointe pas : sans aucune heure réelle, le prévu fait foi."""
    periode = periode_a_saisir(
        annee=2026,
        mois=9,
        fenetre=FENETRE_SEPTEMBRE,
        calendriers={
            (2026, 8): _mois(2026, 8, reel_jusqu_au=None),
            (2026, 9): _mois(2026, 9, reel_jusqu_au=None),
        },
    )

    assert periode.statut == "saisi"
    assert periode.manquants == ()


def test_des_lignes_reelles_a_vide_ne_font_pas_un_salarie_qui_pointe():
    """Des entrées réelles sans heures (créées à vide par une saisie) : le moteur
    les ignore tant qu'aucune heure n'est pointée, le juge aussi."""
    prevu, _ = _mois(2026, 9, reel_jusqu_au=None)
    reel = [{"jour": e["jour"], "type": e["type"], "heures_faites": None} for e in prevu]

    periode = periode_a_saisir(
        annee=2026,
        mois=9,
        fenetre=(date(2026, 9, 1), date(2026, 9, 30)),
        calendriers={(2026, 9): (prevu, reel)},
    )

    assert periode.statut == "saisi"
    assert periode.manquants == ()


def test_un_zero_saisi_reste_a_saisir_meme_sans_aucune_heure_pointee():
    """0 h saisie un jour travaillé : le moteur paierait le prévu sans le dire."""
    prevu, _ = _mois(2026, 9, reel_jusqu_au=None)
    reel = [{"jour": 9, "type": "travail", "heures_faites": 0.0}]

    periode = periode_a_saisir(
        annee=2026,
        mois=9,
        fenetre=(date(2026, 9, 1), date(2026, 9, 30)),
        calendriers={(2026, 9): (prevu, reel)},
    )

    assert [(j.jour.day, j.motif) for j in periode.bloquants] == [(9, "reel_a_zero")]


def test_absence_repos_ferie_et_ecole_ne_sont_jamais_a_saisir():
    sept_prevu, sept_reel = _mois(2026, 9, reel_jusqu_au=20)
    types = {
        7: "conges_payes",
        8: "arret_maladie",
        9: "absence_non_remuneree",
        10: "ferie",
        11: "ecole",
        14: "repos",
        15: "rtt",
    }
    for entree in sept_prevu:
        if entree["jour"] in types:
            entree.update(type=types[entree["jour"]], heures_prevues=0.0)
    sept_reel = [e for e in sept_reel if e["jour"] not in types]

    periode = periode_a_saisir(
        annee=2026,
        mois=9,
        fenetre=(date(2026, 9, 1), date(2026, 9, 20)),
        calendriers={(2026, 9): (sept_prevu, sept_reel)},
    )

    assert periode.bloquants == ()


def test_une_sortie_dans_la_fenetre_n_attend_rien_apres_le_dernier_jour():
    periode = periode_a_saisir(
        annee=2026,
        mois=9,
        fenetre=FENETRE_SEPTEMBRE,
        calendriers=_septembre_pointe(s35=8.0, s37_importee=False),
        date_entree=date(2026, 8, 24),
        date_sortie=date(2026, 9, 9),
    )

    assert libelle_plages(j.jour for j in periode.bloquants) == "07/09–09/09"
    assert periode.informatifs == ()


def test_les_raisons_se_disent_en_clair_dans_un_ordre_fixe():
    jours = [
        JourASaisir(date(2026, 8, 24), True, "reel_a_zero"),
        JourASaisir(date(2026, 9, 7), True, "prevu_sans_reel"),
        JourASaisir(date(2026, 9, 8), True, "prevu_sans_reel"),
    ]

    assert raisons_en_clair(jours) == "heures réelles non saisies, 0 h au réel un jour travaillé"
    assert raisons_en_clair([JourASaisir(date(2026, 9, 1), True, "planning_absent")]) == (
        "pas de planning"
    )
    assert raisons_en_clair([]) == ""
