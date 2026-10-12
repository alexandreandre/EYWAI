"""Maternité, paternité, adoption : saisissables à l'écran, sans maintien par défaut.

[F12] (enquête F du 10/10/2026) : l'écran n'offrait que les types d'arrêt de la
maladie ; un congé de maternité ou de paternité se saisissait « maladie
simple » et se calculait comme une maladie (carence, carence payée de la
plasturgie consommée). Le régime « parentalité » du moteur (maintien à 100 %
dès le premier jour) n'était atteint que par script.

Le maintien de salaire pendant ces congés n'est pas une obligation légale : il
dépend de la convention (L1226-1 vise la maladie et l'accident). Il devient un
réglage de société, **désactivé par défaut** : rien ne change sans décision.
Chez Comitech, Quadra ne maintenait rien (retenue « Abs. paternité », IJ
versées au salarié).
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.modules.payroll.engine.maintien_salaire_service import (
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
        contrat={"contrat": {"date_entree": "2021-08-01", "statut": "Non-Cadre"}},
    )


def _settings(**extra):
    from app.modules.maintenance_settings.application.queries import _defaults

    return {**_defaults("soc").model_dump(mode="json"), **extra}


def _conge(arret_type, settings, debut="2026-09-07", fin="2026-09-30", ctx=None):
    return calculer_maintien(
        {
            "arret_type": arret_type,
            "date_debut": debut,
            "date_fin": fin,
            "subrogation_active": True,
            "nombre_enfants": 0,
            "salaire_periode_reelle": 0.0,
        },
        ctx or _ctx(),
        settings,
        *SEPTEMBRE,
    )


def test_le_reglage_est_eteint_par_defaut():
    from app.modules.maintenance_settings.application.queries import _defaults
    from app.modules.maintenance_settings.application.commands import _DB_WRITABLE_KEYS

    assert _defaults("soc").maintain_parental_leave is False
    assert "maintain_parental_leave" in _DB_WRITABLE_KEYS


@pytest.mark.parametrize("arret_type", ["maternite", "paternite", "adoption"])
def test_sans_reglage_le_conge_n_a_pas_de_maintien_et_les_ij_vont_au_salarie(arret_type):
    r = _conge(arret_type, _settings())
    assert r["maintien"]["maintien_verse"] == 0
    assert r["maintien"]["maintien_applicable"] is False
    assert r["maintien"]["motif_non_maintien"] == (
        "Pas de maintien de salaire pendant les congés de maternité, de paternité "
        "et d'adoption : réglage de la société."
    )
    assert r["subrogation_active"] is False
    # Pas de carence : indemnités journalières dès le premier jour.
    assert r["carence"]["carence_ss_jours"] == 0
    assert r["ijss"]["nb_jours_indemnises"] == 24


def test_avec_le_reglage_le_conge_est_maintenu_a_100_pour_cent():
    r = _conge("paternite", _settings(maintain_parental_leave=True))
    assert r["maintien"]["maintien_applicable"] is True
    assert r["maintien"]["taux_maintien"] == 1.0
    assert r["maintien"]["maintien_verse"] > 0


def test_sans_reglage_aucun_jour_maintenu_pour_la_prime_d_anciennete():
    arret = {"arret_type": "maternite", "date_debut": "2026-09-07", "date_fin": "2026-09-30"}
    assert compute_jours_avec_maintien_mois(arret, _ctx(), _settings(), *SEPTEMBRE) == set()


def test_la_carence_payee_de_la_plasturgie_n_est_pas_consommee():
    from .helpers import build_test_contexte

    r = _conge(
        "paternite",
        _settings(apply_legal_maintenance=False, paid_waiting_days_per_year=3,
                  maintain_working_days=True, subrogation_mode="never"),
        ctx=build_test_contexte(salaire_base=1963.99, duree_hebdo=39.0, date_entree="2021-09-13"),
    )
    assert "carence_payee_dates" not in r["carence"]
    assert r["maintien"]["maintien_verse"] == 0


@pytest.mark.parametrize("arret_type", ["maternite", "paternite", "adoption"])
def test_l_ecran_peut_saisir_ces_types(arret_type):
    from app.modules.absences.schemas.requests import AbsenceRequestCreate

    demande = AbsenceRequestCreate(
        employee_id="e1",
        type="arret_paternite" if arret_type == "paternite" else "arret_maternite",
        arret_type=arret_type,
        date_debut=date(2026, 9, 7),
        date_fin=date(2026, 9, 30),
    )
    assert demande.arret_type == arret_type


def test_un_conge_d_adoption_se_libelle_comme_tel_au_bulletin():
    from app.modules.payroll.engine.calcul_brut import LIBELLES_ARRET, _nature_de_l_arret

    nature = _nature_de_l_arret(
        {"type": "arret_maladie", "source_absence": "arret_maternite", "arret_type": "adoption"}
    )
    assert LIBELLES_ARRET[nature] == "congé d'adoption"
