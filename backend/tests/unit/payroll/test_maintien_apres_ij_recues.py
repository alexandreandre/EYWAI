"""Maintien après réception des IJ (retour d'Elsa du 13/11, plasturgie).

Sans subrogation, la convention de la plasturgie ne maintient le salaire que sur
les IJ « déclarées à l'entreprise par l'intéressé(e) ». Réglage par société :
tant que le montant des IJ du mois n'est pas saisi, ni maintien ni jours
maintenus pour la prime d'ancienneté ; la saisie du montant les rétablit.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.modules.payroll.engine.maintien_salaire_service import (
    ALERTE_MAINTIEN_EN_ATTENTE_DES_IJ,
    calculer_maintien,
    compute_jours_avec_maintien_mois,
)

pytestmark = pytest.mark.unit

SEPTEMBRE = (date(2026, 9, 1), date(2026, 9, 30))


def _ctx() -> SimpleNamespace:
    return SimpleNamespace(
        salaire_base_mensuel=2400.0,
        statut_salarie="Non-Cadre",
        baremes={
            "pss": {"annuel": 48060.0},
            "ij_plafonds": {"maladie": 42.97, "maternite_paternite": 104.02,
                            "at_mp": 240.49, "at_mp_majoree": 320.66},
        },
        contrat={
            "contrat": {"date_entree": "2015-08-01", "statut": "Non-Cadre"},
            "remuneration": {"convention_collective": {"idcc": "0292"}},
        },
    )


def _settings(**extra):
    from app.modules.maintenance_settings.application.queries import _defaults

    base = _defaults("soc").model_dump(mode="json")
    return {**base, "apply_legal_maintenance": True, "subrogation_mode": "never", **extra}


def _arret(**extra):
    return {
        "arret_type": "maladie_simple",
        "date_debut": "2026-09-01",
        "date_fin": "2026-09-30",
        "subrogation_active": False,
        "salaire_periode_reelle": 0.0,
        **extra,
    }


def test_reglage_eteint_par_defaut():
    from app.modules.maintenance_settings.application.queries import _defaults

    assert _defaults("soc").maintien_apres_ij_recues is False


def test_sans_reglage_le_maintien_est_verse_comme_avant():
    r = calculer_maintien(_arret(), _ctx(), _settings(), *SEPTEMBRE)
    assert r["maintien"]["maintien_verse"] > 0
    assert ALERTE_MAINTIEN_EN_ATTENTE_DES_IJ not in r["alertes"]


def test_ij_non_saisies_maintien_en_attente_et_alerte():
    r = calculer_maintien(_arret(), _ctx(), _settings(maintien_apres_ij_recues=True), *SEPTEMBRE)
    assert r["maintien"]["maintien_verse"] == 0
    assert r["maintien"]["maintien_applicable"] is False
    assert r["maintien"]["en_attente_des_ij"] is True
    avant = calculer_maintien(_arret(), _ctx(), _settings(), *SEPTEMBRE)
    assert r["maintien"]["maintien_en_attente"] == avant["maintien"]["maintien_verse"] > 0
    alerte = next(a for a in r["alertes"] if a.startswith(ALERTE_MAINTIEN_EN_ATTENTE_DES_IJ))
    assert "du 01/09/2026 au 30/09/2026" in alerte
    assert f"{avant['maintien']['maintien_verse']:.2f} €" in alerte


def test_ij_saisies_le_maintien_revient():
    r = calculer_maintien(
        _arret(ijss_brut_override=400.0), _ctx(), _settings(maintien_apres_ij_recues=True),
        *SEPTEMBRE,
    )
    assert r["maintien"]["maintien_verse"] > 0
    assert ALERTE_MAINTIEN_EN_ATTENTE_DES_IJ not in r["alertes"]


def test_subrogation_active_aucune_attente():
    r = calculer_maintien(
        _arret(subrogation_active=True), _ctx(),
        _settings(maintien_apres_ij_recues=True, subrogation_mode="when_maintien"), *SEPTEMBRE,
    )
    assert r["maintien"]["maintien_verse"] > 0


def test_jours_de_prime_d_anciennete_suivent_la_reception():
    reglage = _settings(maintien_apres_ij_recues=True)
    assert compute_jours_avec_maintien_mois(_arret(), _ctx(), reglage, *SEPTEMBRE) == set()
    assert compute_jours_avec_maintien_mois(
        _arret(ijss_brut_override=400.0), _ctx(), reglage, *SEPTEMBRE
    )


def test_conge_de_paternite_plasturgie_attend_aussi_les_ij():
    r = calculer_maintien(
        _arret(arret_type="paternite"), _ctx(), _settings(maintien_apres_ij_recues=True),
        *SEPTEMBRE,
    )
    assert r["maintien"]["maintien_verse"] == 0
    assert any(a.startswith(ALERTE_MAINTIEN_EN_ATTENTE_DES_IJ) for a in r["alertes"])
