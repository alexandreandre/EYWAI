"""Règle « Par jour travaillé » : les jours se comptent dans le calendrier du salarié."""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll_variables.domain.jours_travailles import (
    compter_jours_travailles,
    index_calendrier,
)
from app.modules.payroll_variables.domain.rules import compute_rule_amount

pytestmark = pytest.mark.unit


def _semaine():
    """Lundi 5 au dimanche 11/10/2026 : 5 jours de 7 h prévus, week-end en repos."""
    prevu = index_calendrier(
        2026,
        10,
        [{"jour": j, "type": "travail", "heures_prevues": 7} for j in range(5, 10)]
        + [
            {"jour": 10, "type": "weekend", "heures_prevues": 0},
            {"jour": 11, "type": "weekend"},
        ],
    )
    return prevu


def test_sans_heures_reelles_les_jours_prevus_comptent():
    assert (
        compter_jours_travailles(
            _semaine(), {}, set(), date(2026, 10, 5), date(2026, 10, 11)
        )
        == 5
    )


def test_une_absence_validee_retire_le_jour_prevu():
    absences = {date(2026, 10, 7)}
    assert (
        compter_jours_travailles(
            _semaine(), {}, absences, date(2026, 10, 5), date(2026, 10, 11)
        )
        == 4
    )


def test_les_heures_reelles_priment_sur_le_prevu():
    reel = index_calendrier(
        2026,
        10,
        [
            {"jour": 5, "type": "travail", "heures_faites": 0},  # pas venu
            {"jour": 6, "type": "travail", "heures_faites": 3.5},
            {"jour": 10, "type": "travail", "heures_faites": 6},  # samedi travaillé
        ],
    )
    assert (
        compter_jours_travailles(
            _semaine(), reel, set(), date(2026, 10, 5), date(2026, 10, 11)
        )
        == 5
    )


def test_seuil_d_heures():
    reel = index_calendrier(2026, 10, [{"jour": 6, "heures_faites": 3.5}])
    assert (
        compter_jours_travailles(
            _semaine(), reel, set(), date(2026, 10, 5), date(2026, 10, 11), min_heures=6
        )
        == 4
    )


def test_bornes_de_la_fenetre():
    assert (
        compter_jours_travailles(
            _semaine(), {}, set(), date(2026, 10, 7), date(2026, 10, 8)
        )
        == 2
    )


def test_montant_par_jour():
    assert compute_rule_amount("per_worked_day", 7.5, None, 18) == 135.0


def test_un_panier_genere_sans_type_de_prime_est_non_soumis():
    from app.modules.payroll_variables.application.generate_monthly import (
        _bonus_type_meta,
    )

    label, social, taxable, catalog_id, _, _ = _bonus_type_meta(
        {"label": "Panier repas", "rule_type": "per_worked_day", "conditions": {}}
    )
    assert (label, social, taxable, catalog_id) == (
        "Panier repas",
        False,
        False,
        "indemnite_panier_repas",
    )
    _, social, taxable, catalog_id, _, _ = _bonus_type_meta(
        {"label": "Prime d'équipe", "rule_type": "per_worked_day", "conditions": {}}
    )
    assert (social, taxable, catalog_id) == (True, True, None)


def test_la_situation_du_repas_de_la_regle_passe_a_la_saisie():
    from app.modules.payroll_variables.application.generate_monthly import _bonus_type_meta

    *_, situation = _bonus_type_meta(
        {
            "label": "Panier repas",
            "rule_type": "per_worked_day",
            "conditions": {"situation_repas": "sur_lieu_travail"},
        }
    )
    assert situation == "sur_lieu_travail"


# --- Badge oublié hors du prévu (L19, 26/11) ---------------------------------
#
# Constat LEWIS, octobre 2026 : un dimanche (« weekend » au prévu) avec des
# heures saisies par erreur et sans heure d'arrivée prenait le poste de sa
# semaine : un panier compté en trop. Seul un jour prévu travaillé reprend le
# poste de sa semaine ; un week-end, un férié, un jour non planifié ne le
# reprend jamais : il n'est pas compté et il est dit à la RH.

from app.modules.payroll_variables.domain.jours_travailles import (  # noqa: E402
    detail_jours_travailles,
)

PLAGES = [{"de": "03:30", "a": "04:30"}, {"de": "11:30", "a": "12:30"}]
LUNDI, DIMANCHE = date(2026, 10, 5), date(2026, 10, 11)


def _reel_semaine_badgee(**en_plus):
    """Du lundi 5 au vendredi 9/10 badgés au poste de 4 h, plus les jours donnés."""
    reel = {
        date(2026, 10, j): {"jour": j, "type": "travail", "heures_faites": 7, "debut": "03:50"}
        for j in range(5, 10)
    }
    reel.update(en_plus)
    return reel


@pytest.mark.parametrize(
    "prevu_du_jour",
    [
        {"jour": 11, "type": "weekend"},
        {"jour": 11, "type": "ferie", "heures_prevues": 0},
        {"jour": 11, "type": "repos", "heures_prevues": 0},
        None,
    ],
    ids=["week-end", "ferie", "repos", "non-planifie"],
)
def test_un_jour_hors_du_prevu_ne_reprend_pas_le_poste_de_sa_semaine(prevu_du_jour):
    prevu = _semaine()
    if prevu_du_jour is None:
        prevu.pop(DIMANCHE)
    else:
        prevu[DIMANCHE] = prevu_du_jour
    reel = _reel_semaine_badgee()
    reel[DIMANCHE] = {"jour": 11, "type": "travail", "heures_faites": 7}

    d = detail_jours_travailles(prevu, reel, set(), LUNDI, DIMANCHE, plages_debut=PLAGES)

    assert d["jours"] == 5
    assert d["repris_de_la_semaine"] == []
    assert d["sans_heure_de_debut"] == 1
    assert d["dates_sans_heure_de_debut"] == ["2026-10-11"]


def test_un_jour_prevu_travaille_reprend_toujours_le_poste_de_sa_semaine():
    reel = _reel_semaine_badgee()
    reel[date(2026, 10, 7)] = {"jour": 7, "type": "travail", "heures_faites": 7}

    d = detail_jours_travailles(_semaine(), reel, set(), LUNDI, DIMANCHE, plages_debut=PLAGES)

    assert d["jours"] == 5
    assert d["repris_de_la_semaine"] == ["2026-10-07"]
    assert d["dates_sans_heure_de_debut"] == []
