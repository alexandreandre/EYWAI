"""Mois d'entrée ou de sortie : les heures que l'horaire prévoit sur les jours sous contrat.

Quadra paie un mois incomplet sur l'horaire du salarié : la somme des heures
prévues les jours couverts par le contrat, partagée entre la base (35/39) et
les heures sup structurelles. Septembre 2026, bulletins de la gestionnaire :

- CDD sorti le mardi 15/09 (horaire 8,5 h du lundi au jeudi, 5 h le vendredi) :
  « SALAIRE DE BASE 1er AU 15-09 » 77,63 h + 8,87 h = 86,50 h, la somme du
  planning du 1er au 15 ; nous payions 11 jours × 7,80 = 85,80 h.
- CDD entré le lundi 28/09 (horaire d'hiver 8,5/8,5/8/8,5/5,5) : 22,44 h +
  2,56 h = 25,00 h, lundi + mardi + mercredi ; nous payions 3 × 7,80 = 23,40 h.
- Entrée le lundi 28/09 sur l'horaire 8,5/5 : 22,89 h + 2,61 h = 25,50 h.

Les heures sup structurelles sont tronquées au centième (25,50 × 4/39 =
2,6154 → 2,61, et non 2,62) : c'est ce qui redonne les trois bulletins.

Garde-fous : le planning ne sert que s'il fait la durée du contrat (un 35 h
planifié à 7,8 h/jour garde l'ancien calcul), et un jour sous contrat non
travaillé au planning (congé, férié, « repos » posé par erreur) compte pour
l'horaire de son jour de semaine, comme dans un mois plein.
"""

from __future__ import annotations

import calendar
from datetime import date

import pytest

from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut
from app.modules.payroll.engine.heures_prevues import (
    heures_prevues_sous_contrat,
    repartir_heures_du_contrat,
)

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

#: Lundi → jeudi 8,5 h, vendredi 5 h : 39 h.
HORAIRE_8_5_ET_5 = {0: 8.5, 1: 8.5, 2: 8.5, 3: 8.5, 4: 5.0}
#: Horaire d'hiver 8,5/8,5/8/8,5/5,5 : 39 h.
HORAIRE_HIVER = {0: 8.5, 1: 8.5, 2: 8.0, 3: 8.5, 4: 5.5}


def _mois(annee, mois, horaire, autres=None):
    """Planning d'un mois : l'horaire chaque jour, sauf les jours de `autres`."""
    autres = autres or {}
    jours = []
    for jour in range(1, calendar.monthrange(annee, mois)[1] + 1):
        if jour in autres:
            type_jour, heures = autres[jour]
        else:
            heures = horaire.get(date(annee, mois, jour).weekday(), 0.0)
            type_jour = "travail" if heures > 0 else "weekend"
        jours.append(
            {"annee": annee, "mois": mois, "jour": jour, "type": type_jour,
             "heures_prevues": heures}
        )
    return jours


def _repos(*jours):
    return {j: ("repos", 0.0) for j in jours}


# ---------------------------------------------------------------------------
# Heures prévues sur les jours sous contrat
# ---------------------------------------------------------------------------


def test_sortie_le_15_septembre_somme_du_planning():
    jours = _mois(2026, 9, HORAIRE_8_5_ET_5)
    assert heures_prevues_sous_contrat(
        jours, date(2026, 9, 1), date(2026, 9, 15), 39.0
    ) == 86.5


def test_entree_le_28_septembre_horaire_lu_sur_le_mois_suivant():
    """Lundi, mardi, mercredi : 8,5 + 8,5 + 8. Jeudi et vendredi n'existent
    qu'en octobre : sans eux on ne saurait pas que le planning fait 39 h."""
    jours = _mois(2026, 9, HORAIRE_HIVER, _repos(*range(1, 28))) + _mois(
        2026, 10, HORAIRE_HIVER
    )
    assert heures_prevues_sous_contrat(
        jours, date(2026, 9, 28), date(2026, 9, 30), 39.0
    ) == 25.0


def test_entree_en_fin_de_mois_sans_le_mois_suivant_repli():
    jours = _mois(2026, 9, HORAIRE_HIVER, _repos(*range(1, 28)))
    assert heures_prevues_sous_contrat(
        jours, date(2026, 9, 28), date(2026, 9, 30), 39.0
    ) is None


def test_conge_et_ferie_sous_contrat_comptent_a_l_horaire_du_jour():
    """Sortie le vendredi 24/07 : le férié du 14 et un congé le 16 sont des
    jours du mois, payés puis retirés à part, comme dans un mois plein."""
    jours = _mois(
        2026, 7, HORAIRE_8_5_ET_5,
        {14: ("ferie", 0.0), 16: ("conges_payes", 0.0)},
    )
    assert heures_prevues_sous_contrat(
        jours, date(2026, 7, 1), date(2026, 7, 24), 39.0
    ) == 139.0


def test_semaine_marquee_repos_sous_contrat_compte_a_l_horaire():
    """Embauche le 14/09, planning resté « repos » jusqu'au 20 : la semaine
    sous contrat compte pour l'horaire, pas pour zéro."""
    jours = _mois(2026, 9, HORAIRE_8_5_ET_5, _repos(*range(1, 21)))
    assert heures_prevues_sous_contrat(
        jours, date(2026, 9, 14), date(2026, 9, 30), 39.0
    ) == 103.5


def test_planning_qui_ne_fait_pas_la_duree_du_contrat_repli():
    """Un 35 h planifié à 7,8 h par jour : le planning ne dit pas le contrat."""
    jours = _mois(2026, 9, {d: 7.8 for d in range(5)})
    assert heures_prevues_sous_contrat(
        jours, date(2026, 9, 1), date(2026, 9, 15), 35.0
    ) is None


def test_temps_partiel_deux_jours_par_semaine():
    """14 h : lundi et vendredi 7 h. Du 1er au 24/07 : 3 lundis, 4 vendredis."""
    jours = _mois(2026, 7, {0: 7.0, 4: 7.0})
    assert heures_prevues_sous_contrat(
        jours, date(2026, 7, 1), date(2026, 7, 24), 14.0
    ) == 49.0


def test_sans_planning_repli():
    assert heures_prevues_sous_contrat(
        [], date(2026, 9, 1), date(2026, 9, 15), 39.0
    ) is None


# ---------------------------------------------------------------------------
# Partage base / heures sup structurelles
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "total, duree, attendu",
    [
        (25.5, 39.0, (22.89, 2.61)),  # 2,6154 tronqué
        (25.0, 39.0, (22.44, 2.56)),
        (86.5, 39.0, (77.63, 8.87)),
        (47.5, 39.0, (42.63, 4.87)),
        (70.2, 39.0, (63.0, 7.2)),  # 7,2 exact, pas 7,19
        (135.0, 37.5, (126.0, 9.0)),
        (105.0, 35.0, (105.0, 0.0)),
        (49.0, 14.0, (49.0, 0.0)),
    ],
)
def test_partage_base_et_heures_sup_structurelles(total, duree, attendu):
    assert repartir_heures_du_contrat(total, duree) == attendu


# ---------------------------------------------------------------------------
# Le bulletin
# ---------------------------------------------------------------------------


def _ligne(resultat, fragment):
    return next(
        l for l in resultat["lignes_composants_brut"] if fragment in l["libelle"]
    )


def _lignes(resultat, fragment):
    return [
        (l["libelle"], l["quantite"], l.get("gain"), l.get("perte"))
        for l in resultat["lignes_composants_brut"]
        if fragment in l["libelle"]
    ]


def test_sortie_le_15_septembre_comme_quadra():
    contexte = build_test_contexte(
        salaire_base=1867.06, duree_hebdo=39.0, date_entree="2026-04-07",
        date_fin_contrat="2026-09-15",
        specificites_extra={"salaire_hors_hs_structurelles": True},
    )
    resultat = calculer_salaire_brut(
        contexte, [], date(2026, 9, 1), date(2026, 9, 30), [],
        jours_prevus=_mois(2026, 9, HORAIRE_8_5_ET_5),
    )
    base = _ligne(resultat, "Salaire de base")
    hs = _ligne(resultat, "structurelles majorées")
    assert (base["quantite"], base["gain"]) == (77.63, 955.63)
    assert (hs["quantite"], hs["gain"]) == (8.87, 136.49)
    assert _ligne(resultat, "SOUS-TOTAL")["gain"] == 1092.12
    assert resultat["heures_base_remunerees"] == 77.63


def test_entree_le_28_septembre_comme_quadra():
    contexte = build_test_contexte(
        salaire_base=2192.67, duree_hebdo=39.0, date_entree="2026-09-28",
        date_fin_contrat="2026-12-18",
    )
    jours = _mois(2026, 9, HORAIRE_HIVER, _repos(*range(1, 28))) + _mois(
        2026, 10, HORAIRE_HIVER
    )
    resultat = calculer_salaire_brut(
        contexte, [], date(2026, 9, 1), date(2026, 9, 30), [], jours_prevus=jours
    )
    base = _ligne(resultat, "Salaire de base")
    hs = _ligne(resultat, "structurelles majorées")
    assert (base["quantite"], base["gain"]) == (22.44, 283.87)
    assert (hs["quantite"], hs["gain"]) == (2.56, 40.48)
    assert resultat["salaire_brut_total"] == 324.35


def test_entree_le_28_septembre_horaire_8_5_et_5_comme_quadra():
    contexte = build_test_contexte(
        salaire_base=1867.06, duree_hebdo=39.0, date_entree="2026-09-28",
        specificites_extra={"salaire_hors_hs_structurelles": True},
    )
    jours = _mois(2026, 9, HORAIRE_8_5_ET_5, _repos(*range(1, 28))) + _mois(
        2026, 10, HORAIRE_8_5_ET_5
    )
    resultat = calculer_salaire_brut(
        contexte, [], date(2026, 9, 1), date(2026, 9, 30), [], jours_prevus=jours
    )
    base = _ligne(resultat, "Salaire de base")
    hs = _ligne(resultat, "structurelles majorées")
    assert (base["quantite"], base["gain"]) == (22.89, 281.78)
    assert (hs["quantite"], hs["gain"]) == (2.61, 40.16)
    assert resultat["salaire_brut_total"] == 321.94


def test_mois_complet_inchange_avec_le_planning():
    contexte = build_test_contexte(
        salaire_base=1867.06, duree_hebdo=39.0, date_entree="2022-01-03",
        specificites_extra={"salaire_hors_hs_structurelles": True},
    )
    resultat = calculer_salaire_brut(
        contexte, [], date(2026, 9, 1), date(2026, 9, 30), [],
        jours_prevus=_mois(2026, 9, HORAIRE_8_5_ET_5),
    )
    assert _ligne(resultat, "Salaire de base")["quantite"] == 151.67
    assert _ligne(resultat, "structurelles majorées")["quantite"] == 17.33


def test_planning_hors_contrat_garde_les_jours_ouvres():
    """Un 35 h planifié à 7,8 h : 11 jours × 7 h, comme avant."""
    contexte = build_test_contexte(
        salaire_base=1823.03, duree_hebdo=35.0, date_entree="2026-04-07",
        date_fin_contrat="2026-09-15",
    )
    resultat = calculer_salaire_brut(
        contexte, [], date(2026, 9, 1), date(2026, 9, 30), [],
        jours_prevus=_mois(2026, 9, {d: 7.8 for d in range(5)}),
    )
    assert _ligne(resultat, "Salaire de base")["quantite"] == 77.0


def test_la_surcharge_du_mois_prime_sur_le_planning():
    contexte = build_test_contexte(
        salaire_base=1867.06, duree_hebdo=39.0, date_entree="2026-04-07",
        date_fin_contrat="2026-09-15",
        specificites_extra={
            "salaire_hors_hs_structurelles": True,
            "remuneration_mois_partiel": {"heures_base": 70.0},
        },
    )
    resultat = calculer_salaire_brut(
        contexte, [], date(2026, 9, 1), date(2026, 9, 30), [],
        jours_prevus=_mois(2026, 9, HORAIRE_8_5_ET_5),
    )
    assert _ligne(resultat, "Salaire de base")["quantite"] == 70.0
    # Heures sup non surchargées : l'ancien calcul, 11 jours × 0,80.
    assert _ligne(resultat, "structurelles majorées")["quantite"] == 8.8


def test_les_absences_ne_bougent_pas():
    """Entrée le 20/04, sortie le 15/05, fériés du 8 et du 14 non payés
    (moins de trois mois) : mêmes retenues, avec ou sans le planning. Seules
    les heures payées changent."""

    def resultat(jours_prevus):
        contexte = build_test_contexte(
            salaire_base=1850.37, duree_hebdo=39.0, date_entree="2026-04-20",
            date_fin_contrat="2026-05-15",
            specificites_extra={"salaire_hors_hs_structurelles": True,
                                "jours_feries_anciennete_min_mois": 3},
        )
        return calculer_salaire_brut(
            contexte,
            [{"date_complete": j, "type": "ferie", "heures": 7.8}
             for j in ("2026-05-08", "2026-05-14")],
            date(2026, 5, 1), date(2026, 5, 31), [],
            date_debut_variables=date(2026, 4, 20),
            date_fin_variables=date(2026, 5, 24),
            jours_prevus=jours_prevus,
        )

    feries = {1: ("ferie", 0.0), 8: ("ferie", 0.0), 14: ("ferie", 0.0),
              25: ("ferie", 0.0)}
    avant = resultat(None)
    apres = resultat(_mois(2026, 5, HORAIRE_8_5_ET_5, feries))
    for fragment in ("jour férié non payé", "Réduction HS structurelles"):
        assert _lignes(apres, fragment) == _lignes(avant, fragment) != []
    # 5 + 34 + 5 + 25,5 + 8,5 + 5 = 83 h du 1er au 15/05 (11 jours × 7,80 avant).
    assert _ligne(avant, "Salaire de base")["quantite"] == 77.0
    assert _ligne(apres, "Salaire de base")["quantite"] == 74.49
    assert _ligne(apres, "structurelles majorées")["quantite"] == 8.51
