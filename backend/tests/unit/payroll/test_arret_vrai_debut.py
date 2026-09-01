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
    """30/08/2026 = dimanche. Les jours non travaillés d'un arrêt ne sont pas
    typés au calendrier (un jour arret_maladie à 0 h serait déduit plein par
    calcul_brut) : la vraie fin calendaire passe par date_fin_arret_reel,
    posée à la validation — la date_fin extraite pour maintien/IJSS/prévoyance
    est ce dimanche, pas le dernier jour ouvré typé."""
    cal = [
        {"date_complete": "2026-08-28", "type": "arret_maladie",
         "arret_type": "maladie_simple", "date_fin_arret_reel": "2026-08-30"},
    ]
    arret = _extraire_arret_pour_maintien(cal, _Ctx(), date(2026, 8, 1), date(2026, 8, 31))
    assert arret["date_fin"] == "2026-08-30"


def test_date_fin_reel_anterieure_au_dernier_jour_type_est_ignoree():
    """Si un jour typé arret_maladie existe APRÈS la borne déclarée (autre
    enregistrement, prolongation), le dernier jour typé prime : on prend le max."""
    cal = [
        {"date_complete": "2026-08-28", "type": "arret_maladie",
         "arret_type": "maladie_simple", "date_fin_arret_reel": "2026-08-28"},
        {"date_complete": "2026-08-31", "type": "arret_maladie",
         "arret_type": "maladie_simple"},
    ]
    arret = _extraire_arret_pour_maintien(cal, _Ctx(), date(2026, 8, 1), date(2026, 8, 31))
    assert arret["date_fin"] == "2026-08-31"


def test_mois_ne_contenant_que_le_week_end_d_un_arret_reste_visible():
    """Débordement ven. 31/07 → dim. 02/08 : le bulletin d'août n'a aucun jour
    typé arret_maladie, seulement samedi/dimanche porteurs des bornes."""
    cal = [
        {"date_complete": "2026-08-01", "type": "weekend",
         "arret_type": "maladie_simple",
         "date_debut_arret_reel": "2026-07-31",
         "date_fin_arret_reel": "2026-08-02"},
        {"date_complete": "2026-08-02", "type": "weekend",
         "arret_type": "maladie_simple",
         "date_debut_arret_reel": "2026-07-31",
         "date_fin_arret_reel": "2026-08-02"},
    ]
    arret = _extraire_arret_pour_maintien(cal, _Ctx(), date(2026, 8, 1), date(2026, 8, 31))
    assert arret is not None
    assert arret["date_debut"] == "2026-07-31"
    assert arret["date_fin"] == "2026-08-02"


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
