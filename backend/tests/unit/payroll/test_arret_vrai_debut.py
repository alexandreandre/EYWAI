"""Arrêt maladie multi-mois : le maintien doit être compté depuis le VRAI début
de l'arrêt (déclaré), pas depuis le 1er jour d'arrêt du mois courant — sinon un
arrêt long (maintien épuisé) se voit appliquer un maintien à tort.

Cf. LEWIS BASTER : arrêt depuis le 23/09/2025 ; en janvier 2026 le maintien
(100 j pour ~15 ans d'ancienneté) est épuisé → déduction pleine, pas de maintien.
"""

from datetime import date

from app.modules.payroll.documents.payslip_run_heures import (
    _extraire_arret_pour_maintien,
)


class _Ctx:
    contrat = {"contrat": {"temps_travail": {}}}


def test_arret_utilise_le_vrai_debut_si_declare():
    cal = [
        {"date_complete": "2026-01-05", "type": "arret_maladie",
         "arret_type": "maladie_simple", "date_debut_arret_reel": "2025-09-23"},
        {"date_complete": "2026-01-31", "type": "arret_maladie",
         "arret_type": "maladie_simple", "date_debut_arret_reel": "2025-09-23"},
    ]
    arret = _extraire_arret_pour_maintien(cal, _Ctx(), date(2026, 1, 1), date(2026, 1, 31))
    assert arret["date_debut"] == "2025-09-23"  # vrai début, pas le 05/01
    assert arret["date_fin"] == "2026-01-31"


def test_arret_fallback_premier_jour_du_mois_sans_vrai_debut():
    # Comportement inchangé quand le vrai début n'est pas déclaré (non-régression).
    cal = [
        {"date_complete": "2026-01-05", "type": "arret_maladie",
         "arret_type": "maladie_simple"},
    ]
    arret = _extraire_arret_pour_maintien(cal, _Ctx(), date(2026, 1, 1), date(2026, 1, 31))
    assert arret["date_debut"] == "2026-01-05"


def test_arret_finissant_un_dimanche_conserve_le_dimanche_en_date_fin():
    """30/08/2026 = dimanche. Depuis l'expansion calendaire (spec 2026-09-01),
    les week-ends d'un arrêt sont typés arret_maladie : la date_fin extraite
    pour maintien/IJSS/prévoyance est ce dimanche, pas le dernier jour ouvré."""
    cal = [
        {"date_complete": "2026-08-28", "type": "arret_maladie",
         "arret_type": "maladie_simple"},
        {"date_complete": "2026-08-29", "type": "arret_maladie",
         "arret_type": "maladie_simple"},
        {"date_complete": "2026-08-30", "type": "arret_maladie",
         "arret_type": "maladie_simple"},
    ]
    arret = _extraire_arret_pour_maintien(cal, _Ctx(), date(2026, 8, 1), date(2026, 8, 31))
    assert arret["date_fin"] == "2026-08-30"


from app.modules.payroll.engine.temps_travail_mois import compute_temps_retenu_mois


def test_prorata_arret_plein_mois_sans_pointage_ratio_zero():
    """Arrêt tout le mois, aucun pointage, maintien épuisé (jours_maintien vide) :
    la présence retenue (pour proratiser la prime d'ancienneté) doit être 0 —
    surtout PAS le repli 'plein_mois' (ratio 1.0)."""
    cal = [{"jour": d, "type": "arret_maladie"} for d in range(1, 32)]
    res = compute_temps_retenu_mois(
        mode="heures_contrat", calendrier_saisie=cal, duree_hebdo=35.0,
        date_debut=date(2026, 1, 1), date_fin=date(2026, 1, 31),
        jours_maintien=set(), actual_hours_raw=[], sans_pointage_policy="plein_mois",
    )
    assert res.ratio == 0.0


def test_prorata_mois_normal_sans_pointage_conserve_repli_plein_mois():
    """Non-régression : mois normal sans pointage (pas d'arrêt) → repli plein_mois (1.0)."""
    cal = [{"jour": d, "type": "travail", "heures": 0} for d in range(1, 32)]
    res = compute_temps_retenu_mois(
        mode="heures_contrat", calendrier_saisie=cal, duree_hebdo=35.0,
        date_debut=date(2026, 1, 1), date_fin=date(2026, 1, 31),
        actual_hours_raw=[], sans_pointage_policy="plein_mois",
    )
    assert res.ratio == 1.0
