"""Maintien de salaire : l'ancienneté se lit à la date d'ancienneté de la fiche.

La condition d'un an d'ancienneté et la durée des tranches (L1226-1,
D1226-1 et D1226-2) s'apprécient sur l'ancienneté dans l'entreprise, que la
convention ou le contrat peut reprendre. Le moteur lit déjà la date
d'ancienneté de la fiche (`seniority_reference_date`, à défaut la date
d'ancienneté de la DSN, à défaut l'entrée) pour la prime d'ancienneté et les
fériés ; le maintien, la carence payée et la subrogation lisaient la seule
date d'entrée du contrat. Cas construit de l'enquête : entrée au contrat le
01/03/2026, ancienneté reprise au 01/03/2021 → « Ancienneté inférieure au
minimum requis », maintien 0 € au lieu de 1 633,14 €.

`prior_service_months` n'est pas lu : sur 221 fiches il porte l'ancienneté
totale, pas la reprise (défaut connu).
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
ARRET = {
    "arret_type": "maladie_simple",
    "date_debut": "2026-09-01",
    "date_fin": "2026-09-30",
    "subrogation_active": False,
    "nombre_enfants": 0,
    "salaire_periode_reelle": 0.0,
}


def _ctx(seniority_reference_date: str | None = "2021-03-01") -> SimpleNamespace:
    return SimpleNamespace(
        salaire_base_mensuel=2400.0,
        statut_salarie="Non-Cadre",
        baremes={"pss": {"annuel": 48060.0}, "ij_plafonds": {"maladie": 42.97}},
        contrat={
            "contrat": {
                "date_entree": "2026-03-01",
                "seniority_reference_date": seniority_reference_date,
                "statut": "Non-Cadre",
            }
        },
    )


def _settings(**overrides):
    base = {
        "apply_legal_maintenance": True,
        "min_seniority_months": 12,
        "employer_waiting_days": 7,
        "no_seniority_condition": False,
    }
    base.update(overrides)
    return base


def test_le_maintien_lit_la_date_d_anciennete_reprise():
    r = calculer_maintien(dict(ARRET), _ctx(), _settings(), *SEPTEMBRE)
    assert r["maintien"]["maintien_applicable"] is True
    assert r["maintien"]["maintien_verse"] > 0
    assert r["anciennete_mois"] == 66


def test_sans_date_d_anciennete_le_maintien_lit_l_entree():
    r = calculer_maintien(dict(ARRET), _ctx(None), _settings(), *SEPTEMBRE)
    assert r["maintien"]["maintien_applicable"] is False
    assert r["anciennete_mois"] == 6


def test_les_jours_maintenus_de_la_prime_lisent_la_meme_anciennete():
    jours = compute_jours_avec_maintien_mois(dict(ARRET), _ctx(), _settings(), *SEPTEMBRE)
    # Carence employeur de 7 jours, puis maintien du 08 au 30/09.
    assert jours == set(range(8, 31))


def test_la_carence_payee_lit_la_meme_anciennete():
    # Réglage de la plasturgie : 3 jours de carence payés par an après un an
    # d'ancienneté, rien d'autre.
    reglage = _settings(
        apply_legal_maintenance=False,
        paid_waiting_days_per_year=3,
        paid_waiting_min_seniority_months=12,
        employer_waiting_days=3,
        min_seniority_months=10,
    )
    r = calculer_maintien(dict(ARRET), _ctx(), reglage, *SEPTEMBRE)
    assert r["carence"]["carence_payee_dates"] == ["2026-09-01", "2026-09-02", "2026-09-03"]


def test_la_subrogation_deduite_a_la_validation_lit_la_meme_anciennete():
    from app.modules.absences.application.queries import compute_subrogation_for_absence

    absence = {"arret_type": "maladie_simple", "selected_days": ["2026-09-01", "2026-09-30"]}
    fiche = {"hire_date": "2026-03-01", "seniority_reference_date": "2021-03-01"}
    reglage = {"subrogation_mode": "when_maintien", "min_seniority_months": 12}
    assert compute_subrogation_for_absence(absence, fiche, reglage) is True
    fiche_sans_reprise = {"hire_date": "2026-03-01"}
    assert compute_subrogation_for_absence(absence, fiche_sans_reprise, reglage) is False


def test_l_apercu_du_maintien_transmet_la_date_d_anciennete():
    from app.modules.absences.application.queries import _employee_payload_for_contexte

    payload = _employee_payload_for_contexte(
        {"hire_date": "2026-03-01", "seniority_reference_date": "2021-03-01"}
    )
    assert payload["seniority_reference_date"] == "2021-03-01"


def test_une_date_d_anciennete_posterieure_a_l_entree_ne_reduit_pas_l_anciennete():
    # Date de la fiche ou de la DSN postérieure à l'entrée (quelques jours
    # d'écart sur un CDD, ou une saisie à revoir) : l'ancienneté retenue reste
    # la plus favorable, comme pour les fériés ; jamais moins que l'entrée.
    ctx = _ctx("2026-08-01")
    ctx.contrat["contrat"]["date_entree"] = "2021-03-01"
    r = calculer_maintien(dict(ARRET), ctx, _settings(), *SEPTEMBRE)
    assert r["anciennete_mois"] == 66

    ctx_dsn = _ctx(None)
    ctx_dsn.contrat["contrat"]["date_entree"] = "2021-03-01"
    ctx_dsn.contrat["specificites_paie"] = {"dsn_anciennete": {"date_anciennete": "2026-08-01"}}
    r = calculer_maintien(dict(ARRET), ctx_dsn, _settings(), *SEPTEMBRE)
    assert r["anciennete_mois"] == 66


def test_la_subrogation_garde_l_entree_si_la_date_d_anciennete_est_posterieure():
    from app.modules.absences.application.queries import compute_subrogation_for_absence

    absence = {"arret_type": "maladie_simple", "selected_days": ["2026-09-01", "2026-09-30"]}
    fiche = {"hire_date": "2021-03-01", "seniority_reference_date": "2026-08-01"}
    reglage = {"subrogation_mode": "when_maintien", "min_seniority_months": 12}
    assert compute_subrogation_for_absence(absence, fiche, reglage) is True
