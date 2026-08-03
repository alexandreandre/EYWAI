"""Congés payés saisis dans le planning → compteurs de congés.

Les congés payés ne sont pas posés en demande d'absence : ils sont saisis jour
par jour dans le planning de paie. Le module congés ne les lisait pas, si bien
que les compteurs ne se décrémentaient jamais.

Deux garde-fous indissociables du branchement :

* la reprise des soldes, importée des bulletins de mai 2026, encode déjà tous
  les congés pris jusqu'à sa date de référence — les recompter les déduirait
  deux fois ;
* un jour déjà couvert par une demande d'absence validée ne doit pas être
  compté une seconde fois.
"""

from __future__ import annotations

from datetime import date

from app.modules.absences.domain.planning_cp import (
    extract_planning_cp_days,
    merge_planning_cp_days,
)


# --- lecture du calendrier de paie -------------------------------------------


def test_extraction_des_jours_de_conges_du_calendrier():
    calendrier = {
        "periode": {"annee": 2026, "mois": 6},
        "calendrier_prevu": [
            {"jour": 1, "type": "travail"},
            {"jour": 2, "type": "conges_payes"},
            {"jour": 3, "type": "conges_payes"},
            {"jour": 4, "type": "repos"},
            {"jour": 5, "type": "absence_non_remuneree"},
        ],
    }
    assert extract_planning_cp_days(calendrier) == ["2026-06-02", "2026-06-03"]


def test_extraction_sans_calendrier_ne_casse_pas():
    assert extract_planning_cp_days(None) == []
    assert extract_planning_cp_days({}) == []
    assert extract_planning_cp_days({"calendrier_prevu": "pas une liste"}) == []


def test_extraction_ignore_un_jour_hors_du_mois():
    calendrier = {
        "periode": {"annee": 2026, "mois": 2},
        "calendrier_prevu": [
            {"jour": 30, "type": "conges_payes"},
            {"jour": 27, "type": "conges_payes"},
        ],
    }
    assert extract_planning_cp_days(calendrier) == ["2026-02-27"]


# --- fusion avec les demandes d'absence --------------------------------------


def test_les_jours_du_planning_deviennent_des_conges_pris():
    validated = []
    result = merge_planning_cp_days(
        validated,
        {"emp-1": ["2026-06-02", "2026-06-03"]},
        cutoffs={},
    )
    assert len(result) == 1
    assert result[0]["employee_id"] == "emp-1"
    assert result[0]["type"] == "conge_paye"
    assert result[0]["status"] == "validated"
    assert result[0]["selected_days"] == ["2026-06-02", "2026-06-03"]


def test_les_jours_anterieurs_a_la_reprise_sont_ignores():
    """La reprise du 31/05 encode déjà les congés pris avant cette date."""
    result = merge_planning_cp_days(
        [],
        {"emp-1": ["2026-05-20", "2026-05-31", "2026-06-01"]},
        cutoffs={"emp-1": date(2026, 5, 31)},
    )
    assert result[0]["selected_days"] == ["2026-06-01"]


def test_sans_reprise_tous_les_jours_comptent():
    result = merge_planning_cp_days(
        [], {"emp-1": ["2026-01-05", "2026-06-01"]}, cutoffs={"emp-1": None}
    )
    assert result[0]["selected_days"] == ["2026-01-05", "2026-06-01"]


def test_un_jour_deja_pose_en_demande_nest_pas_compte_deux_fois():
    validated = [
        {
            "employee_id": "emp-1",
            "type": "conge_paye",
            "status": "validated",
            "selected_days": ["2026-06-02"],
        }
    ]
    result = merge_planning_cp_days(
        validated, {"emp-1": ["2026-06-02", "2026-06-03"]}, cutoffs={}
    )
    assert len(result) == 2
    assert result[1]["selected_days"] == ["2026-06-03"]


def test_les_demandes_existantes_sont_preservees():
    validated = [
        {
            "employee_id": "emp-1",
            "type": "arret_maladie",
            "status": "validated",
            "selected_days": ["2026-06-10"],
        }
    ]
    result = merge_planning_cp_days(validated, {}, cutoffs={})
    assert result == validated


def test_aucun_jour_restant_najoute_pas_de_ligne_vide():
    result = merge_planning_cp_days(
        [], {"emp-1": ["2026-05-20"]}, cutoffs={"emp-1": date(2026, 5, 31)}
    )
    assert result == []


def test_les_jours_sont_dedoublonnes_et_ordonnes():
    result = merge_planning_cp_days(
        [], {"emp-1": ["2026-06-03", "2026-06-02", "2026-06-03"]}, cutoffs={}
    )
    assert result[0]["selected_days"] == ["2026-06-02", "2026-06-03"]
