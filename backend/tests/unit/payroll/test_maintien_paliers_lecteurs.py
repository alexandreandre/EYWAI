"""Sous le barème, les autres lecteurs du maintien suivent les paliers.

Plusieurs arrêts dans le mois, jours maintenus de la prime d'ancienneté,
complément de prévoyance (conception du 24/10/2026). Initiales seulement.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.maintien_salaire_service import (
    calculer_maintien,
    compute_jours_avec_maintien_mois,
)

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

JUIN = (date(2026, 6, 1), date(2026, 6, 30))
SEPTEMBRE = (date(2026, 9, 1), date(2026, 9, 30))
BAREME = {
    "bareme_convention": "plasturgie_0292",
    "subrogation_mode": "never",
    "maintain_working_days": True,
    "deduire_ijss_sans_subrogation": True,
}
MANUELS = {"maintain_100_percent": True, "custom_duration_days": 57, "apply_legal_maintenance": True}
CHAINE = [("2026-05-04", "2026-05-31"), ("2026-06-01", "2026-06-30"),
          ("2026-07-01", "2026-07-31"), ("2026-08-01", "2026-08-31"),
          ("2026-09-01", "2026-09-30")]


def _sg():
    return build_test_contexte(
        salaire_base=1952.60, duree_hebdo=39.0, date_entree="2003-07-15",
        specificites_extra={"salaire_hors_hs_structurelles": True},
    )


def _arret(debut, fin, connus, **extra):
    return {
        "arret_type": "maladie_simple", "date_debut": debut, "date_fin": fin,
        "subrogation_active": False, "nombre_enfants": 0, "salaire_periode_reelle": 0.0,
        "arrets_connus": [{"debut": d, "fin": f, "type": "maladie_simple"} for d, f in connus],
        **extra,
    }


def test_deux_arrets_qui_couvrent_juin_valent_le_salaire_du_mois():
    connus = [CHAINE[0], ("2026-06-01", "2026-06-15"), ("2026-06-16", "2026-06-30")]
    arret = _arret("2026-06-01", "2026-06-30", connus, ijss_brut_override=1235.70, arrets_du_mois=[
        {"date_debut": "2026-06-01", "date_fin": "2026-06-15", "arret_type": "maladie_simple"},
        {"date_debut": "2026-06-16", "date_fin": "2026-06-30", "arret_type": "maladie_simple"},
    ])
    m = calculer_maintien(arret, _sg(), dict(BAREME), *JUIN)["maintien"]
    assert [(p["du"], p["au"], p["jours"], p["valeur"]) for p in m["paliers"]] == [
        ("2026-06-01", "2026-06-15", 11, 1115.74),
        ("2026-06-16", "2026-06-30", 11, 1115.74),
    ]
    assert (m["maintien_cible"], m["ijss_deduites"], m["maintien_verse"]) == (2231.48, 1235.70, 995.78)
    assert m["regle_retenue"] == "convention"


def test_la_prime_d_anciennete_suit_les_jours_de_la_regle_retenue():
    # IJ validées à 41,19 €/jour : le barème l'emporte sur le versé (218,96 contre 172,66).
    arret = _arret("2026-09-01", "2026-09-30", CHAINE, ijss_brut_override=1235.70)
    jours = compute_jours_avec_maintien_mois(arret, _sg(), {**BAREME, **MANUELS}, *SEPTEMBRE)
    assert jours == set(range(1, 16))  # 75 % jusqu'au 15/09 ; le légal n'est pas retenu


def test_la_prevoyance_lit_le_taux_de_chaque_jour_retenu():
    reglages = {**BAREME, **MANUELS, "provident_maintenance_rate": 0.8,
                "provident_cadre_only": False, "provident_relay_days": 1}
    arret = _arret("2026-09-01", "2026-09-30", CHAINE, ijss_brut_override=1235.70)
    r = calculer_maintien(arret, _sg(), reglages, *SEPTEMBRE)
    assert r["maintien"]["regle_retenue"] == "convention"
    # Du 16 au 30/09, plus de maintien : la prévoyance complète ; avant, 75 % suffit.
    assert r["prevoyance"]["nb_jours"] == 15
    assert r["prevoyance"]["montant"] > 0


def test_sans_bareme_la_prime_et_la_prevoyance_d_avant():
    sans = {k: v for k, v in {**BAREME, **MANUELS}.items() if k != "bareme_convention"}
    arret = _arret("2026-09-01", "2026-09-30", CHAINE)
    avant = compute_jours_avec_maintien_mois(arret, _sg(), sans, *SEPTEMBRE)
    assert compute_jours_avec_maintien_mois(arret, _sg(), {**sans, "bareme_convention": None}, *SEPTEMBRE) == avant
