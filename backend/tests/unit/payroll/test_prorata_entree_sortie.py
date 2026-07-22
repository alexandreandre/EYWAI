from datetime import date

import pytest

from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut
from app.modules.payroll.engine.calcul_brut_forfait import (
    calculer_salaire_brut_forfait,
)
from app.modules.payroll.documents.payslip_generator_forfait import (
    _periode_de_paie_company,
)
from app.modules.payroll.documents.payslip_generator import _earliest_employment_end
from tests.unit.payroll.helpers import build_test_contexte


def test_entree_mois_horaire_proratee_sur_heures_ouvrees():
    contexte = build_test_contexte(
        salaire_base=1985.79,
        duree_hebdo=37.5,
        date_entree="2026-01-26",
    )

    resultat = calculer_salaire_brut(
        contexte, [], date(2026, 1, 1), date(2026, 1, 31), []
    )

    lignes = resultat["lignes_composants_brut"]
    base = next(l for l in lignes if l["libelle"] == "Salaire de base")
    hs = next(l for l in lignes if "structurelles" in l["libelle"])
    assert base["quantite"] == pytest.approx(35.0)
    assert base["gain"] == pytest.approx(420.70, abs=0.01)
    assert hs["quantite"] == pytest.approx(2.5)
    assert hs["gain"] == pytest.approx(37.56, abs=0.01)
    assert resultat["salaire_brut_total"] == pytest.approx(458.26, abs=0.01)


def test_entree_mois_horaire_peut_utiliser_les_heures_reelles_de_paie():
    contexte = build_test_contexte(
        salaire_base=1850.37,
        duree_hebdo=39.0,
        date_entree="2026-03-23",
        specificites_extra={
            "salaire_hors_hs_structurelles": True,
            "remuneration_mois_partiel": {
                "heures_base": 47.5,
                "heures_hs_structurelles": 3.0,
            },
        },
    )

    resultat = calculer_salaire_brut(
        contexte,
        [],
        date(2026, 3, 1),
        date(2026, 3, 31),
        [],
    )

    lignes = resultat["lignes_composants_brut"]
    base = next(l for l in lignes if l["libelle"] == "Salaire de base")
    hs_structurelles = [
        l for l in lignes if "structurelles" in l["libelle"].lower()
    ]
    assert base["quantite"] == pytest.approx(47.5)
    assert base["gain"] == pytest.approx(579.50, abs=0.01)
    assert len(hs_structurelles) == 1
    assert hs_structurelles[0]["quantite"] == pytest.approx(3.0)
    assert hs_structurelles[0]["gain"] == pytest.approx(45.75, abs=0.01)
    assert resultat["salaire_brut_total"] == pytest.approx(625.25, abs=0.01)


def test_entree_mois_horaire_peut_afficher_la_retenue_reelle_entree_sortie():
    contexte = build_test_contexte(
        salaire_base=1850.37,
        duree_hebdo=39.0,
        date_entree="2026-04-07",
        specificites_extra={
            "salaire_hors_hs_structurelles": True,
            "jours_feries_anciennete_min_mois": 3,
            "remuneration_mois_partiel": {
                "heures_base": 151.67,
                "heures_hs_structurelles": 17.33,
                "retenue_entree_sortie_heures": 30.5,
                "heures_hs_exonerees": 19.28,
                "montant_hs_exonerees": 294.02,
            },
        },
    )

    resultat = calculer_salaire_brut(
        contexte,
        [
            {"date_complete": "2026-04-06", "type": "ferie", "heures": 7.0},
            {"date_complete": "2026-04-30", "type": "travail_hs25", "heures": 5.0},
        ],
        date(2026, 4, 1),
        date(2026, 4, 30),
        [],
    )

    lignes = resultat["lignes_composants_brut"]
    base = next(l for l in lignes if l["libelle"] == "Salaire de base")
    retenue = next(l for l in lignes if l["libelle"] == "Absence pour entrée ou sortie")
    assert base["quantite"] == pytest.approx(151.67)
    assert base["gain"] == pytest.approx(1850.37, abs=0.01)
    assert retenue["quantite"] == pytest.approx(30.5)
    assert retenue["perte"] == pytest.approx(372.10, abs=0.01)
    assert resultat["salaire_brut_total"] == pytest.approx(1818.80, abs=0.01)
    assert resultat["total_heures_supp"] == pytest.approx(19.28)
    assert resultat["remuneration_brute_heures_supp"] == pytest.approx(
        294.02, abs=0.01
    )


def test_entree_sortie_meme_mois_horaire_proratee_sur_jours_ouvres():
    contexte = build_test_contexte(
        salaire_base=1949.04,
        duree_hebdo=37.5,
        date_entree="2026-01-05",
        date_fin_contrat="2026-01-26",
        specificites_extra={"salaire_hors_hs_structurelles": True},
    )

    resultat = calculer_salaire_brut(
        contexte, [], date(2026, 1, 1), date(2026, 1, 31), []
    )

    lignes = resultat["lignes_composants_brut"]
    base = next(l for l in lignes if l["libelle"] == "Salaire de base")
    hs = next(l for l in lignes if "structurelles" in l["libelle"])
    assert base["quantite"] == pytest.approx(112.0)
    assert base["gain"] == pytest.approx(1439.26, abs=0.01)
    assert hs["quantite"] == pytest.approx(8.0)
    assert hs["gain"] == pytest.approx(128.51, abs=0.01)


def test_entree_mois_forfait_deduit_jours_ouvres_avant_embauche():
    contexte = build_test_contexte(
        salaire_base=3167.0,
        statut="Cadre",
        date_entree="2026-04-14",
    )

    resultat = calculer_salaire_brut_forfait(
        contexte, [], date(2026, 4, 1), date(2026, 4, 30)
    )

    ligne = next(
        l
        for l in resultat["lignes_composants_brut"]
        if l["libelle"] == "Absence pour entrée ou sortie"
    )
    assert ligne["quantite"] == pytest.approx(9.0)
    assert ligne["taux"] == pytest.approx(143.9545, abs=0.0001)
    assert ligne["perte"] == pytest.approx(1295.59, abs=0.01)
    assert resultat["salaire_brut_total"] == pytest.approx(1871.41, abs=0.01)


def test_generateur_forfait_transmet_la_periode_de_paie_company():
    assert _periode_de_paie_company(
        {"paie_jour_de_fin": 31, "paie_occurrence": -1}
    ) == {"jour_de_fin": 31, "occurrence": -1}


def test_fin_contrat_la_plus_tot_est_retenue_pour_le_prorata():
    assert (
        _earliest_employment_end("2026-01-26", "2026-02-28")
        == "2026-01-26"
    )


def test_absences_reduisent_les_hs_sur_la_periode_partielle():
    contexte = build_test_contexte(
        salaire_base=1949.04,
        duree_hebdo=37.5,
        date_entree="2026-01-05",
        date_fin_contrat="2026-01-26",
        specificites_extra={"salaire_hors_hs_structurelles": True},
    )
    calendrier = [
        {
            "date_complete": f"2026-01-{jour:02d}",
            "type": "arret_maladie",
            "heures": 7.0,
        }
        for jour in (14, 15, 16, 19, 20, 21, 22, 23)
    ]
    calendrier.append(
        {
            "date_complete": "2026-01-26",
            "type": "absence_non_remuneree",
            "heures": 4.2,
        }
    )

    resultat = calculer_salaire_brut(
        contexte, calendrier, date(2026, 1, 1), date(2026, 1, 31), []
    )

    reduction = next(
        l
        for l in resultat["lignes_composants_brut"]
        if l.get("is_reduction_hs")
    )
    assert reduction["quantite"] == pytest.approx(4.3)
