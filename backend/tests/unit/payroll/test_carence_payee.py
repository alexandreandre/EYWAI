"""Carence payée une fois par an : le crédit se consomme arrêt après arrêt.

Règle des sociétés de la plasturgie (Gaëlle, 28/09/2026) : l'employeur paie les
jours de carence d'un arrêt maladie dans la limite de 3 jours par année civile,
si le salarié a un an d'ancienneté. Un arrêt de 2 jours en consomme 2, il en
reste 1 pour l'arrêt suivant ; tout repart à zéro en janvier.

Quadra, Colorplast 2026 : arrêt du 16/03 → 3 jours payés (310,78 €) ; arrêts
d'avril et d'août → rien, le crédit est épuisé.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.carence_payee import ArretDeLAnnee, jours_de_carence_payes

pytestmark = pytest.mark.unit

ENTREE = date(2021, 9, 13)


def _arret(debut, fin, type_arret="maladie"):
    return ArretDeLAnnee(debut=date.fromisoformat(debut), fin=date.fromisoformat(fin), type_arret=type_arret)


def _payes(arrets, **kw):
    params = {"jours_par_an": 3, "date_entree": ENTREE, "anciennete_min_mois": 12}
    params.update(kw)
    return {
        (a.debut.isoformat(), a.fin.isoformat()): [d.isoformat() for d in jours]
        for a, jours in jours_de_carence_payes(arrets, **params).items()
    }


def test_le_premier_arret_de_l_annee_a_ses_trois_jours_payes():
    assert _payes([_arret("2026-03-16", "2026-03-27")]) == {
        ("2026-03-16", "2026-03-27"): ["2026-03-16", "2026-03-17", "2026-03-18"]
    }


def test_les_arrets_suivants_de_l_annee_n_ont_plus_rien():
    payes = _payes(
        [
            _arret("2026-03-16", "2026-03-27"),
            _arret("2026-04-01", "2026-04-28"),
            _arret("2026-08-17", "2026-09-03"),
        ]
    )
    assert payes[("2026-04-01", "2026-04-28")] == []
    assert payes[("2026-08-17", "2026-09-03")] == []


def test_un_arret_de_deux_jours_laisse_un_jour_pour_le_suivant():
    payes = _payes([_arret("2026-02-10", "2026-02-11"), _arret("2026-05-05", "2026-05-08")])
    assert payes[("2026-02-10", "2026-02-11")] == ["2026-02-10", "2026-02-11"]
    assert payes[("2026-05-05", "2026-05-08")] == ["2026-05-05"]


def test_un_week_end_de_carence_n_est_ni_paye_ni_consomme():
    """Arrêt du vendredi : seul le vendredi est payé ; il reste 2 jours."""
    payes = _payes([_arret("2026-05-15", "2026-05-20"), _arret("2026-06-08", "2026-06-12")])
    assert payes[("2026-05-15", "2026-05-20")] == ["2026-05-15"]
    assert payes[("2026-06-08", "2026-06-12")] == ["2026-06-08", "2026-06-09"]


def test_une_prolongation_n_ouvre_pas_de_nouvelle_carence():
    payes = _payes([_arret("2026-08-17", "2026-09-03"), _arret("2026-09-03", "2026-09-18")])
    assert payes[("2026-09-03", "2026-09-18")] == []


def test_le_credit_repart_a_zero_en_janvier():
    payes = _payes([_arret("2025-11-03", "2025-11-07"), _arret("2026-01-12", "2026-01-16")])
    assert payes[("2026-01-12", "2026-01-16")] == ["2026-01-12", "2026-01-13", "2026-01-14"]


def test_moins_d_un_an_d_anciennete_rien_n_est_paye_ni_consomme():
    payes = _payes(
        [_arret("2026-03-02", "2026-03-06"), _arret("2026-10-05", "2026-10-09")],
        date_entree=date(2025, 6, 1),
    )
    assert payes[("2026-03-02", "2026-03-06")] == []
    assert payes[("2026-10-05", "2026-10-09")] == ["2026-10-05", "2026-10-06", "2026-10-07"]


def test_un_accident_du_travail_ne_consomme_pas_le_credit():
    payes = _payes([_arret("2026-02-02", "2026-02-06", "accident_travail"), _arret("2026-03-16", "2026-03-27")])
    assert payes[("2026-02-02", "2026-02-06")] == []
    assert payes[("2026-03-16", "2026-03-27")] == ["2026-03-16", "2026-03-17", "2026-03-18"]


def test_sans_credit_parametre_rien_n_est_paye():
    assert _payes([_arret("2026-03-16", "2026-03-27")], jours_par_an=0) == {
        ("2026-03-16", "2026-03-27"): []
    }


# --- Dans le calcul du maintien (réglages de Colorplast) ---

from app.modules.payroll.engine.maintien_salaire_service import calculer_maintien  # noqa: E402

from .helpers import build_test_contexte  # noqa: E402

REGLAGES_PLASTURGIE = {
    "apply_legal_maintenance": False,
    "min_seniority_months": 10,
    "employer_waiting_days": 3,
    "subrogation_mode": "never",
    "paid_waiting_days_per_year": 3,
    "paid_waiting_min_seniority_months": 12,
    "maintain_working_days": True,
}


def _maintien(debut, fin, periode, arrets_annee=(), statut="Non-Cadre", **reglages):
    contexte = build_test_contexte(
        statut=statut, salaire_base=1963.99, duree_hebdo=39.0, date_entree="2021-09-13",
        specificites_extra={"salaire_hors_hs_structurelles": True},
    )
    return calculer_maintien(
        {
            "arret_type": "maladie",
            "date_debut": debut,
            "date_fin": fin,
            "subrogation_active": True,
            "nombre_enfants": 0,
            "salaire_periode_reelle": 0.0,
            "arrets_annee": list(arrets_annee),
        },
        contexte,
        {**REGLAGES_PLASTURGIE, **reglages},
        *periode,
    )


MARS = (date(2026, 3, 1), date(2026, 3, 31))
AOUT = (date(2026, 8, 1), date(2026, 8, 31))


def test_mars_trois_jours_payes_comme_le_cabinet_sans_subrogation():
    """Cabinet : « Maintien de salaire 310,78 » = 3 × 103,59 (7 h + 0,80 h)."""
    r = _maintien("2026-03-16", "2026-03-27", MARS)
    assert r["maintien"]["maintien_verse"] == 310.78
    assert r["subrogation_active"] is False
    assert r["carence"]["carence_payee_dates"] == ["2026-03-16", "2026-03-17", "2026-03-18"]


def test_aout_rien_quand_le_credit_de_l_annee_est_epuise():
    r = _maintien(
        "2026-08-17", "2026-09-03", AOUT,
        arrets_annee=[{"debut": "2026-03-16", "fin": "2026-03-27", "type": "maladie"},
                      {"debut": "2026-04-01", "fin": "2026-04-28", "type": "maladie"}],
    )
    assert r["maintien"]["maintien_verse"] == 0
    assert "carence_payee_dates" not in r["carence"]


def test_sans_reglage_de_carence_payee_rien_ne_change():
    r = _maintien("2026-03-16", "2026-03-27", MARS, paid_waiting_days_per_year=None)
    assert r["maintien"]["maintien_verse"] == 0


def test_les_cadres_restent_hors_de_la_regle_en_attendant_sa_precision():
    r = _maintien("2026-03-16", "2026-03-27", MARS, statut="Cadre")
    assert r["maintien"]["maintien_verse"] == 0


def test_les_arrets_de_l_annee_se_lisent_dans_les_calendriers():
    from unittest.mock import MagicMock, patch

    from app.modules.payroll.documents import payslip_run_heures as run

    def jour(n, debut=None, fin=None, type_arret=None):
        entree = {"jour": n, "type": "arret_maladie" if debut else "travail"}
        if debut:
            entree.update(date_debut_arret_reel=debut, date_fin_arret_reel=fin, arret_type=type_arret)
        return entree

    lignes = [
        {"month": 3, "planned_calendar": {"calendrier_prevu": [
            jour(16, "2026-03-16", "2026-03-27", "maladie"), jour(17, "2026-03-16", "2026-03-27", "maladie"), jour(30)]}},
        {"month": 8, "planned_calendar": {"calendrier_prevu": [
            jour(17, "2026-08-17", "2026-09-03", "maladie_simple")]}},
    ]
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.lte.return_value.execute.return_value = MagicMock(data=lignes)
    with patch("app.core.database.supabase", client):
        arrets = run.arrets_de_l_annee("e1", 2026, 8)
    assert arrets == [
        {"debut": "2026-03-16", "fin": "2026-03-27", "type": "maladie"},
        {"debut": "2026-08-17", "fin": "2026-09-03", "type": "maladie_simple"},
    ]
