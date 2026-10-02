"""Explications des lignes qui surprennent : heures sup, absences, réduction générale."""

from __future__ import annotations

from copy import deepcopy

import pytest

from app.modules.payroll.domain.explications_lignes import poser_explications

pytestmark = pytest.mark.unit


def _bulletin(**surcharges):
    base = {
        "en_tete": {"annee": 2026, "mois": 9},
        "calcul_du_brut": [],
        "details_absences": [],
        "details_conges": [],
        "structure_cotisations": {"bloc_allegements": []},
        "cotisations_officielles": [],
        "salaire_brut": 2100.0,
        "net_a_payer": 1600.0,
    }
    base.update(surcharges)
    return base


def _ligne_hs(palier: int, quantite: float, gain: float = 100.0) -> dict:
    return {
        "libelle": f"Heures suppl. majorées à {palier}%",
        "quantite": quantite,
        "taux": 16.0 if palier == 25 else 19.2,
        "gain": gain,
        "perte": None,
    }


def test_heures_sup_semaine_par_semaine_depuis_la_compensation():
    bulletin = _bulletin(
        calcul_du_brut=[_ligne_hs(25, 16.0, 256.0)],
        compensation_semaines={
            "semaines": [
                {"annee": 2026, "semaine": 35, "total": 4.0, "majo25": 4.0, "majo50": 0.0},
                {"annee": 2026, "semaine": 36, "total": 4.0, "majo25": 4.0, "majo50": 0.0},
                {"annee": 2026, "semaine": 37, "total": 4.0, "majo25": 4.0, "majo50": 0.0},
                {"annee": 2026, "semaine": 38, "total": 4.0, "majo25": 4.0, "majo50": 0.0},
            ],
            "net25": 16.0,
            "net50": 0.0,
        },
    )
    pose = poser_explications(bulletin, duree_hebdo=39.0)
    assert pose["calcul_du_brut"][0]["gain"] == 256.0
    assert pose["calcul_du_brut"][0]["quantite"] == 16.0
    assert pose["calcul_du_brut"][0]["explication"] == (
        "16 h à 25 % : 4 h par semaine au-delà de 39 h, semaines 35 à 38"
    )


def test_heures_sup_depuis_le_detail_des_heures_sans_inventer_de_semaine():
    bulletin = _bulletin(calcul_du_brut=[_ligne_hs(25, 8.0, 128.0)])
    evenements = [
        {"date_complete": "2026-09-07", "type": "travail_hs25", "heures": 4.0},
        {"date_complete": "2026-09-14", "type": "travail_hs25", "heures": 4.0},
        {"type": "travail_hs25", "heures": 99.0},  # sans date : ignoré
    ]
    pose = poser_explications(bulletin, evenements=evenements, duree_hebdo=39.0)
    texte = pose["calcul_du_brut"][0]["explication"]
    assert "99" not in texte
    assert texte == (
        "8 h à 25 % : 4 h par semaine au-delà de 39 h, semaines 37 à 38"
    )
    assert pose["calcul_du_brut"][0]["gain"] == 128.0


def test_heures_sup_declarees_ne_reprennent_pas_les_semaines_du_planning():
    bulletin = _bulletin(
        calcul_du_brut=[_ligne_hs(25, 6.0, 96.0)],
        heures_sup_declarees={"hs25": 6.0, "hs50": 0.0, "planning": 10.0},
        compensation_semaines={
            "semaines": [
                {"annee": 2026, "semaine": 35, "total": 10.0, "majo25": 4.0, "majo50": 6.0},
            ],
            "net25": 4.0,
            "net50": 6.0,
            "heures_saisies": {"hs25": 6.0, "hs50": 0.0},
        },
    )
    pose = poser_explications(bulletin, duree_hebdo=39.0)
    texte = pose["calcul_du_brut"][0]["explication"]
    assert "semaine" not in texte.lower()
    assert "déclarées" in texte
    assert "6 h à 25 %" in texte
    assert "10 h" in texte


def test_sans_detail_semaine_aucune_semaine_inventee_et_pas_d_infobulle_vide():
    bulletin = _bulletin(calcul_du_brut=[_ligne_hs(25, 3.0, 48.0)])
    pose = poser_explications(bulletin)
    ligne = pose["calcul_du_brut"][0]
    assert ligne["gain"] == 48.0
    assert "explication" not in ligne


def test_heures_sup_somme_des_semaines_differente_pas_de_detail_faux():
    bulletin = _bulletin(calcul_du_brut=[_ligne_hs(25, 6.0, 96.0)])
    evenements = [
        {"date_complete": "2026-09-07", "type": "travail_hs25", "heures": 4.0},
        {"date_complete": "2026-09-14", "type": "travail_hs25", "heures": 4.0},
    ]
    pose = poser_explications(bulletin, evenements=evenements, duree_hebdo=39.0)
    ligne = pose["calcul_du_brut"][0]
    assert ligne["quantite"] == 6.0
    assert ligne["gain"] == 96.0
    assert "explication" not in ligne


def test_absence_type_et_dates_retenus_par_le_bulletin():
    bulletin = _bulletin(
        details_absences=[
            {
                "libelle": "Absence arrêt maladie du 01/09 au 30/09",
                "quantite": 154.0,
                "taux": 13.14,
                "gain": None,
                "perte": 2023.56,
                "is_arret_maladie": True,
            }
        ]
    )
    pose = poser_explications(bulletin)
    assert pose["details_absences"][0]["perte"] == 2023.56
    assert pose["details_absences"][0]["explication"] == (
        "Absence : arrêt maladie du 01/09 au 30/09"
    )


def test_absence_d_un_seul_jour():
    bulletin = _bulletin(
        details_absences=[
            {
                "libelle": "Absence injustifiée du 15/09 (base)",
                "quantite": 7.0,
                "perte": 92.0,
            }
        ]
    )
    pose = poser_explications(bulletin)
    assert pose["details_absences"][0]["explication"] == (
        "Absence : injustifiée du 15/09"
    )


def test_conges_payes_avec_les_dates_du_bulletin():
    bulletin = _bulletin(
        details_conges=[
            {
                "libelle": "Absence congés payés (2,00 j : 12/09, 13/09)",
                "quantite": 14.0,
                "perte": 184.0,
            }
        ]
    )
    pose = poser_explications(bulletin)
    assert pose["details_conges"][0]["explication"] == (
        "Absence : congés payés 12/09, 13/09"
    )


def test_indemnite_compensatrice_de_fin_de_contrat_n_est_pas_une_absence():
    bulletin = _bulletin(
        details_conges=[
            {
                "libelle": "Indemnité compensatrice de congés payés (CDD)",
                "quantite": None,
                "gain": 150.02,
            }
        ]
    )
    pose = poser_explications(bulletin)
    texte = pose["details_conges"][0]["explication"]
    assert "Absence" not in texte
    assert texte == "Congés acquis et non pris, payés à la fin du contrat"
    assert pose["details_conges"][0]["gain"] == 150.02


def test_absence_ne_recompose_pas_une_plage_continue_sur_des_trous():
    bulletin = _bulletin(
        details_conges=[
            {
                "libelle": "Absence congés payés (4,00 j : 13/07, 15/07→17/07, 21/07)",
                "quantite": 28.0,
                "perte": 368.0,
            }
        ]
    )
    pose = poser_explications(bulletin)
    texte = pose["details_conges"][0]["explication"]
    assert "du 13/07 au 21/07" not in texte
    assert texte == "Absence : congés payés 13/07, 15/07→17/07, 21/07"
    assert pose["details_conges"][0]["perte"] == 368.0


def test_reduction_generale_regularisation_depuis_janvier():
    ligne = {
        "libelle": "Réduction générale de cotisations patronales",
        "coti_id": "reduction_generale",
        "montant_patronal": -180.0,
        "base": 2100.0,
    }
    bulletin = _bulletin(
        en_tete={"annee": 2026, "mois": 3},
        structure_cotisations={"bloc_allegements": [ligne]},
        cotisations_officielles=[
            {"code": "exonerations", "libelle": "EXO", "lignes": [dict(ligne)]}
        ],
    )
    pose = poser_explications(bulletin, reduction_deja=420.0)
    assert pose["structure_cotisations"]["bloc_allegements"][0]["montant_patronal"] == -180.0
    assert pose["structure_cotisations"]["bloc_allegements"][0]["explication"] == (
        "Réduction générale : régularisation depuis janvier"
    )
    assert pose["cotisations_officielles"][0]["lignes"][0]["explication"] == (
        "Réduction générale : régularisation depuis janvier"
    )


def test_janvier_sans_regularisation_n_explique_pas_la_reduction():
    ligne = {
        "libelle": "Réduction générale de cotisations patronales",
        "coti_id": "reduction_generale",
        "montant_patronal": -200.0,
    }
    bulletin = _bulletin(
        en_tete={"annee": 2026, "mois": 1},
        structure_cotisations={"bloc_allegements": [ligne]},
    )
    pose = poser_explications(bulletin, reduction_deja=0.0)
    assert "explication" not in pose["structure_cotisations"]["bloc_allegements"][0]


def test_mois_suivant_sans_reduction_deja_appliquee_n_est_pas_une_regularisation():
    ligne = {
        "libelle": "Réduction générale de cotisations patronales",
        "coti_id": "reduction_generale",
        "montant_patronal": -90.0,
    }
    bulletin = _bulletin(
        en_tete={"annee": 2026, "mois": 2},
        structure_cotisations={"bloc_allegements": [ligne]},
    )
    pose = poser_explications(bulletin, reduction_deja=0.0)
    assert "explication" not in pose["structure_cotisations"]["bloc_allegements"][0]


def test_les_montants_restent_identiques():
    origine = _bulletin(
        calcul_du_brut=[_ligne_hs(25, 4.0, 64.0), _ligne_hs(50, 2.0, 38.4)],
        details_absences=[
            {"libelle": "Absence arrêt maladie du 08/09 au 12/09", "perte": 460.0, "quantite": 35.0}
        ],
        compensation_semaines={
            "semaines": [
                {"annee": 2026, "semaine": 37, "total": 6.0, "majo25": 4.0, "majo50": 2.0},
            ],
            "net25": 4.0,
            "net50": 2.0,
        },
        structure_cotisations={
            "bloc_allegements": [
                {
                    "libelle": "Réduction générale de cotisations patronales",
                    "coti_id": "reduction_generale",
                    "montant_patronal": -12.5,
                }
            ]
        },
        salaire_brut=1999.99,
        net_a_payer=1500.01,
    )
    avant = deepcopy(origine)
    pose = poser_explications(deepcopy(origine), duree_hebdo=39.0, reduction_deja=100.0)

    def sans_explication(obj):
        if isinstance(obj, dict):
            return {k: sans_explication(v) for k, v in obj.items() if k != "explication"}
        if isinstance(obj, list):
            return [sans_explication(x) for x in obj]
        return obj

    assert sans_explication(pose) == avant
    assert pose["salaire_brut"] == 1999.99
    assert pose["net_a_payer"] == 1500.01
