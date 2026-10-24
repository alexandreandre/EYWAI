"""Ce que le suivi IJSS montre de la déduction d'un arrêt sans subrogation.

La déduction se lit sur le bulletin actuel (clés posées par le moteur sur le
maintien) : la ligne du suivi peut dater d'avant un changement de réglage.
"""

from __future__ import annotations

import pytest

from app.modules.ijss_tracking.domain.deduction_affichee import (
    deduction_du_bulletin,
    montant_applique_sans_effet,
)

pytestmark = pytest.mark.unit


def _bulletin(maintien: dict) -> dict:
    return {"bloc_maintien": {"maintien": maintien}}


def test_une_deduction_donne_son_montant_sa_source_et_ses_jours():
    pdata = _bulletin(
        {"ijss_deduites": 687.12, "ijss_deduites_source": "validees", "nb_jours_maintien": 19}
    )
    assert deduction_du_bulletin(pdata) == {
        "ijss_deduites": 687.12,
        "ijss_deduites_source": "validees",
        "nb_jours_maintenus": 19,
    }


def test_sans_deduction_rien_n_est_affiche():
    assert deduction_du_bulletin(_bulletin({"nb_jours_maintien": 19})) == {
        "ijss_deduites": None,
        "ijss_deduites_source": None,
        "nb_jours_maintenus": None,
    }
    assert deduction_du_bulletin({})["ijss_deduites"] is None
    assert deduction_du_bulletin(None)["ijss_deduites"] is None


def test_le_montant_applique_est_sans_effet_quand_le_garanti_est_verse_en_entier():
    sans_deduction = deduction_du_bulletin(_bulletin({"nb_jours_maintien": 19}))
    assert montant_applique_sans_effet(
        subrogation_active=False, applique=True, bulletin_connu=True, deduction=sans_deduction
    )


def test_pas_de_sans_effet_quand_une_deduction_joue_ou_sans_subrogation_vraie():
    avec = deduction_du_bulletin(_bulletin({"ijss_deduites": 10.0, "nb_jours_maintien": 3}))
    sans = deduction_du_bulletin({})
    assert not montant_applique_sans_effet(
        subrogation_active=False, applique=True, bulletin_connu=True, deduction=avec
    )
    # Arrêt subrogé : les IJSS entrent au bulletin, le montant a un effet.
    assert not montant_applique_sans_effet(
        subrogation_active=True, applique=True, bulletin_connu=True, deduction=sans
    )
    # Rien appliqué, ou bulletin introuvable : on ne dit rien de faux.
    assert not montant_applique_sans_effet(
        subrogation_active=False, applique=False, bulletin_connu=True, deduction=sans
    )
    assert not montant_applique_sans_effet(
        subrogation_active=False, applique=True, bulletin_connu=False, deduction=sans
    )


def test_le_tableau_relit_le_bulletin_actuel(monkeypatch):
    """La ligne du suivi porte la déduction du bulletin, et le sans-effet après retour au garanti."""
    from app.modules.ijss_tracking.application import service

    ligne = {
        "id": "L1",
        "employee_id": "E1",
        "line_status": "pending",
        "subrogation_active": False,
        "ijss_theorique": 831.78,
        "ijss_subrogees_bulletin": 831.78,
        "applied_to_payslip_at": "2026-10-24T10:00:00+00:00",
        "applied_ijss_brut": 500.0,
        "ijss_brut_validated": 500.0,
    }
    bulletins = {
        "E1": {
            "payslip_data": _bulletin(
                {"ijss_deduites": 413.04, "ijss_deduites_source": "validees", "nb_jours_maintien": 19}
            )
        }
    }
    monkeypatch.setattr(service.repo, "get_or_create_period", lambda *a: {"id": "P1"})
    monkeypatch.setattr(service, "_recompute_period", lambda p: p)
    monkeypatch.setattr(service.repo, "list_expected_lines", lambda pid: [ligne])
    monkeypatch.setattr(service.repo, "list_received_lines", lambda pid: [])
    monkeypatch.setattr(service, "_fetch_employees", lambda cid: [{"id": "E1", "first_name": "A", "last_name": "B"}])
    monkeypatch.setattr(service, "_bulletins_du_mois", lambda c, y, m: bulletins)

    ligne_avec = service.get_period_dashboard("C1", 2026, 10)["rows"][0]
    assert ligne_avec["ijss_deduites"] == 413.04
    assert ligne_avec["nb_jours_maintenus"] == 19
    assert ligne_avec["applique_sans_effet"] is False

    # Le réglage est revenu au garanti entier : le bulletin n'a plus de déduction.
    bulletins["E1"] = {"payslip_data": _bulletin({"nb_jours_maintien": 19})}
    ligne_sans = service.get_period_dashboard("C1", 2026, 10)["rows"][0]
    assert ligne_sans["ijss_deduites"] is None
    assert ligne_sans["applique_sans_effet"] is True
